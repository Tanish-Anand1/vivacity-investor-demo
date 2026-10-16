"""Small reproducible MuJoCo benchmarks, independent of robot task success.

Analytical cases validate numerical mechanisms at stated conditions/tolerances;
they do not certify material calibration or arbitrary robotic scenes.
"""
import hashlib
import time
import uuid
import math
import mujoco as mj
import numpy as np


def run_benchmarks():
    tic = time.perf_counter()
    cases = []
    steps_total = 0

    def run(name, xml, steps, metric, tolerance, units, configure=None):
        nonlocal steps_total
        model = mj.MjModel.from_xml_string(xml)
        data = mj.MjData(model)
        if configure:
            configure(model, data)
        mj.mj_forward(model, data)
        initial = data.qpos.copy()
        initial_velocity = data.qvel.copy()
        for _ in range(steps):
            mj.mj_step(model, data)
        mj.mj_forward(model, data)
        measured, expected, detail = metric(model, data)
        error = float(abs(measured-expected))
        steps_total += steps
        cases.append({'name': name, 'passed': bool(np.isfinite(error) and error<=tolerance),
                      'measured': float(measured), 'reference': float(expected), 'absolute_error': error,
                      'tolerance': tolerance, 'units': units, 'reference_definition': detail,
                      'simulation_steps': steps, 'simulation_time_s': float(data.time),
                      'model_sha256': hashlib.sha256(xml.encode()).hexdigest(),
                      'initial_qpos': initial.tolist(), 'final_qpos': data.qpos.tolist(),
                      'initial_qvel': initial_velocity.tolist(), 'mjcf': xml,
                      'solver': {'timestep_s': float(model.opt.timestep), 'iterations': int(model.opt.iterations),
                                 'integrator': int(model.opt.integrator)}})
        return model, data

    sphere = '<worldbody><body name="sample" pos="0 0 2"><freejoint/><geom type="sphere" size=".05" mass="1"/></body></worldbody>'
    run('Free-fall position', '<mujoco><option timestep=".001" integrator="RK4" gravity="0 0 -9.81"/>'+sphere+'</mujoco>',
        300, lambda m,d: (d.qpos[2], 2.-.5*9.81*d.time**2, 'z=z0−½gt², no contact or air'), 1e-7, 'm')
    run('Free-fall velocity', '<mujoco><option timestep=".001" integrator="RK4" gravity="0 0 -9.81"/>'+sphere+'</mujoco>',
        300, lambda m,d: (d.qvel[2], -9.81*d.time, 'vz=−gt, no contact or air'), 1e-7, 'm/s')
    floor = '<geom name="floor" type="plane" size="2 2 .1" friction=".3 .005 .0001"/>'
    sample = '<body name="sample" pos="0 0 .05"><freejoint/><geom type="box" size=".05 .05 .05" mass="1" friction=".3 .005 .0001" condim="3" solref=".004 1"/></body>'
    xml = '<mujoco><option timestep=".001" integrator="implicitfast"/><worldbody>'+floor+sample+'</worldbody></mujoco>'

    def normal_force(m,d):
        total = 0.
        for i in range(d.ncon):
            f = np.zeros(6); mj.mj_contactForce(m,d,i,f); total += f[0]
        return total, 9.81, 'Static support: total normal force = mg (1 kg)'
    run('Static contact force', xml, 1000, normal_force, .01, 'N')

    def slide_setup(m,d):
        for _ in range(500): mj.mj_step(m,d)
        d.time = 0.; d.qpos[0] = 0.; d.qvel[:] = 0.; d.qvel[0] = 2.
    run('Coulomb sliding', xml, 200,
        lambda m,d: (d.qpos[0], 2*d.time-.5*.3*9.81*d.time**2, 'x=v0t−½μgt², μ=.3, v0=2 m/s, flat box'), .008, 'm', slide_setup)

    pendulum = '''<mujoco><option timestep=".001" integrator="RK4"/><worldbody><body><joint type="hinge" axis="0 1 0" damping="0"/>
    <inertial pos="0 0 -.5" mass="1" diaginertia=".083333333333 .083333333333 .00001"/>
    <geom type="capsule" fromto="0 0 0 0 0 -1" size=".005" contype="0" conaffinity="0"/></body></worldbody></mujoco>'''
    run('Small-angle pendulum', pendulum, 300,
        lambda m,d: (d.qpos[0], .01*math.cos(math.sqrt(9.81*.5/(1/3))*d.time), 'Uniform rod L=1 m; θ≈θ0cos(√(3g/2L)t), θ0=.01 rad'), 1e-6, 'rad',
        lambda m,d: d.qpos.__setitem__(0,.01))

    drag = '''<mujoco><option timestep=".001" gravity="0 0 0" density="1.225" viscosity="0" integrator="implicitfast"/>
    <worldbody><body><freejoint/><geom type="box" size=".05 .05 .05" mass="1"/></body></worldbody></mujoco>'''
    k = 2*1.225*.05*.05
    run('Native quadratic drag', drag, 1000,
        lambda m,d: (d.qvel[0], 2/(1+2*k*d.time), 'MuJoCo inertia-box drag: dv/dt=−2ρryrzv²/m, ρ=1.225, r=.05, m=1'), 1e-5, 'm/s',
        lambda m,d: d.qvel.__setitem__(0,2.))

    # Controlled native ellipsoid pair. The reference is another executed run,
    # not a claimed analytical fluid/restitution law.
    ellipsoid = '''<mujoco><option timestep=".001" gravity="0 0 0" density="{density}" wind="5 0 0" integrator="implicitfast"/>
    <worldbody><body><freejoint/><geom type="box" size=".025 .025 .025" mass=".02" fluidshape="ellipsoid" fluidcoef=".5 .25 1.5 0 0"/></body></worldbody></mujoco>'''
    outcomes = []
    for density in (0., 1.225):
        m = mj.MjModel.from_xml_string(ellipsoid.format(density=density)); d = mj.MjData(m)
        for _ in range(500): mj.mj_step(m,d)
        outcomes.append(float(d.qpos[0])); steps_total += 500
    displacement = outcomes[1]-outcomes[0]
    cases.append({'name': 'Ellipsoid wind intervention', 'passed': bool(displacement>.001),
                  'measured': displacement, 'reference': 0., 'absolute_error': None, 'tolerance': None,
                  'units': 'm', 'reference_definition': 'Controlled pair: +5 m/s wind must move the body farther in +X than zero-density vacuum.',
                  'simulation_steps': 1000, 'vacuum_position_m': outcomes[0], 'air_position_m': outcomes[1],
                  'model_sha256': hashlib.sha256(ellipsoid.encode()).hexdigest()})

    # Repeat an integrated trajectory; no wall clock or IDs enter the checksum.
    vectors = []
    for _ in range(2):
        m = mj.MjModel.from_xml_string(drag); d = mj.MjData(m); d.qvel[0] = 2.
        for _ in range(250): mj.mj_step(m,d)
        vectors.append(np.r_[d.qpos,d.qvel]); steps_total += 250
    drift = float(np.max(np.abs(vectors[0]-vectors[1])))
    cases.append({'name': 'Fixed-state repeatability', 'passed': drift==0., 'measured': drift,
                  'reference': 0., 'absolute_error': drift, 'tolerance': 0., 'units': 'state component',
                  'reference_definition': 'Two fresh MjData instances, identical XML and initial velocity, 250 steps each.',
                  'simulation_steps': 500, 'state_sha256': hashlib.sha256(vectors[0].tobytes()).hexdigest()})
    return {'schema_version': 'vivacity.physics-validation/1.0', 'id': str(uuid.uuid4()),
            'created_unix_s': time.time(), 'engine': 'MuJoCo', 'engine_version': mj.__version__,
            'seed': 7, 'readiness': 'benchmark_tested' if all(c['passed'] for c in cases) else 'benchmark_failure',
            'passed': sum(c['passed'] for c in cases), 'total': len(cases), 'cases': cases,
            'performance': {'wall_seconds': time.perf_counter()-tic, 'simulation_steps': steps_total},
            'scope': 'Mechanism benchmarks at explicit conditions, not validation of every robot/world or physical calibration. Pendulum is a small-angle approximation; wind is a controlled numerical intervention. Restitution, rolling, motor energy and real-world measurements are not certified.'}
