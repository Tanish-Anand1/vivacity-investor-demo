import mujoco as mj
import numpy as np
import pytest

from vivacity.inverse_dynamics import ConstrainedInverseDynamics, ControllerInfeasible
from vivacity.wrench_dynamics import WrenchInverseDynamics, contact_basis, friction_facets


def motor_scene(limit=10.):
    model = mj.MjModel.from_xml_string(f'''<mujoco><option timestep=".001"/>
    <worldbody><body pos="0 0 1"><joint name="hinge" axis="0 1 0" range="-70 70"/>
    <geom type="capsule" fromto="0 0 0 .5 0 0" size=".025" mass="1"/>
    </body></worldbody><actuator><motor joint="hinge" ctrlrange="-{limit} {limit}"/>
    </actuator></mujoco>''')
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    return model, data


@pytest.mark.parametrize('controller_class', [WrenchInverseDynamics, ConstrainedInverseDynamics])
def test_joint_stop_barrier_brakes_before_the_native_limit(controller_class):
    model = mj.MjModel.from_xml_string('''<mujoco><option gravity="0 0 0"/>
    <worldbody><body><joint name="slide" type="slide" axis="1 0 0" range="0 1"/>
    <geom type="sphere" size=".05" mass="1"/></body></worldbody>
    <actuator><motor joint="slide" ctrlrange="-30 30"/></actuator></mujoco>''')
    data = mj.MjData(model)
    data.qpos[0], data.qvel[0] = .98, .5
    mj.mj_forward(model, data)
    result = controller_class(model).compute(data, np.array([1.]),
        torque_reference=np.array([30.]), torque_weight=100.)
    # At this speed a non-braking command would cross the upper joint limit.
    # This fails when NumPy/native-enum membership skips the barrier on Linux.
    assert result.acceleration[0] <= -6.25+.001
    assert result.commands[0] <= -6.25+.001
    assert .98+.08*.5+.5*.08**2*result.acceleration[0] <= 1.+1e-5


def test_wrench_solver_holds_load_through_bounded_motor_and_restores_memory():
    model, data = motor_scene()
    control = WrenchInverseDynamics(model)
    target = data.qpos.copy()
    for _ in range(300):
        solution = control.compute(data, target, torque_weight=.0001)
        assert solution.constraint_violation < .0001
        data.ctrl[:] = solution.commands
        mj.mj_step(model, data)
        mj.mj_forward(model, data)
    assert abs(data.qpos[0]) < .001
    assert abs(data.ctrl[0]) == pytest.approx(9.81*.25, rel=.02)
    branch = WrenchInverseDynamics(model)
    branch.restore(control.snapshot())
    np.testing.assert_array_equal(control.compute(data, target).commands,
                                  branch.compute(data, target).commands)


def test_unpowered_load_falls_or_reports_infeasibility():
    model, data = motor_scene(.1)
    control = WrenchInverseDynamics(model)
    target = data.qpos.copy()
    for _ in range(300):
        try:
            solution = control.compute(data, target)
        except ControllerInfeasible:
            break
        assert abs(solution.commands[0]) <= .10001
        data.ctrl[:] = solution.commands
        mj.mj_step(model, data)
        mj.mj_forward(model, data)
    assert abs(data.qpos[0]) > .1


def test_passive_spring_retracts_without_impossible_actuator_braking_constraints():
    model = mj.MjModel.from_xml_string('''<mujoco><option timestep=".001" integrator="implicitfast"/>
    <worldbody><body name="driven"><joint name="drive" type="slide" axis="1 0 0" range="-1 1"/>
    <geom type="sphere" size=".02" mass="1"/></body>
    <body name="passive" pos="1 0 1"><joint name="spring" type="slide" axis="0 0 -1"
      range="0 .05" stiffness="500" damping="3" armature=".005"/>
      <geom type="sphere" size=".02" mass=".11"/></body></worldbody>
    <actuator><motor joint="drive" ctrlrange="-10 10"/></actuator></mujoco>''')
    data = mj.MjData(model)
    data.qpos[1], data.qvel[1] = .0024736346886078645, .09222354642241679
    mj.mj_forward(model, data)
    # This natural deceleration violates a constant-acceleration 80 ms barrier,
    # but the changing spring force stops the passive joint inside its range.
    assert data.qacc[1] < 2*(0-data.qpos[1]-.08*data.qvel[1])/.08**2
    solver = WrenchInverseDynamics(model)
    solution = solver.compute(data, data.qpos.copy())
    assert solution.acceleration[1] == pytest.approx(data.qacc[1], abs=.0001)
    for _ in range(500):
        data.ctrl[:] = solver.compute(data, np.zeros(model.nq)).commands
        mj.mj_step(model, data)
        mj.mj_forward(model, data)
        assert 0 <= data.qpos[1] <= .05
    assert data.qpos[1] == pytest.approx(.11*9.81/500, abs=.00001)


@pytest.mark.parametrize('dim', [1, 3, 4, 6])
def test_contact_basis_maps_native_measured_wrench_to_generalized_force(dim):
    model = mj.MjModel.from_xml_string(f'''<mujoco><option cone="elliptic"/>
    <default><geom condim="{dim}" friction=".8 .01 .002"/></default>
    <worldbody><geom type="plane" size="2 2 .1"/>
    <body pos="0 0 .049"><freejoint/><geom type="sphere" size=".05" mass="1"/>
    </body></worldbody></mujoco>''')
    data = mj.MjData(model)
    data.qvel[:] = [.1, -.05, 0., .3, -.2, .5]
    mj.mj_forward(model, data)
    total = np.zeros(model.nv)
    for basis in contact_basis(model, data):
        assert basis.dim == dim
        force = np.zeros(6)
        mj.mj_contactForce(model, data, basis.contact_index, force)
        total += basis.jacobian.T @ force[:dim]
    np.testing.assert_allclose(total, data.qfrc_constraint, atol=1e-8)


def test_friction_facets_keep_torque_units_and_zero_coefficients():
    facets, zeros = friction_facets([.8, .8, .01, 0., .002])
    assert np.all(facets @ np.array([10., 1., 1., .01, 0., .001]) >= 0)
    assert np.min(facets @ np.array([10., 0., 0., .11, 0., 0.])) < 0
    assert zeros.tolist() == [4]


def test_released_contact_cannot_supply_predicted_support_and_native_separation_occurs():
    model = mj.MjModel.from_xml_string('''<mujoco><option timestep=".001"/>
    <worldbody><geom type="plane" size="2 2 .1"/>
    <body pos="0 0 .0499"><joint name="slide" type="slide" axis="0 0 1" range="0 .2"/>
    <geom type="sphere" size=".05" mass="1" condim="6"/></body></worldbody>
    <actuator><motor joint="slide" ctrlrange="-40 40"/></actuator></mujoco>''')
    data = mj.MjData(model)
    mj.mj_forward(model,data)
    solver = WrenchInverseDynamics(model)
    assert data.ncon > 0
    original_contacts = data.contact[:data.ncon].dist.copy()
    result = solver.compute(data,np.array([.02]),torque_weight=.0001,
        unloaded_contact_indices=range(data.ncon))
    np.testing.assert_allclose(result.wrenches,0.,atol=1e-6)
    assert result.actuator_forces[0] > 9.81
    np.testing.assert_array_equal(data.contact[:data.ncon].dist,original_contacts)
    for _ in range(350):
        result = solver.compute(data,np.array([.02]),torque_weight=.0001,
            unloaded_contact_indices=range(data.ncon))
        data.ctrl[:] = result.commands
        mj.mj_step(model,data)
        mj.mj_forward(model,data)
    assert data.qpos[0] > .015
    assert data.ncon == 0
    with pytest.raises(ValueError,match='current native contacts'):
        solver.compute(data,np.array([.02]),unloaded_contact_indices=[-1])


def test_clearance_constraint_stops_a_driven_slider_before_obstacle():
    model = mj.MjModel.from_xml_string('''<mujoco><option timestep=".001" gravity="0 0 0"/>
    <worldbody><geom name="wall" type="box" pos=".4 0 0" size=".05 .5 .5"/>
    <body><joint name="slide" type="slide" axis="1 0 0" range="0 1" damping="2"/>
    <geom name="robot" type="sphere" size=".05" mass="1"/></body></worldbody>
    <actuator><motor joint="slide" ctrlrange="-30 30"/></actuator></mujoco>''')
    data = mj.MjData(model)
    control = WrenchInverseDynamics(model)
    minimum = 1.
    for _ in range(1200):
        mj.mj_forward(model, data)
        result = control.compute(data, np.array([.5]), torque_weight=.0001,
            clearance_pairs=[(model.geom('robot').id, model.geom('wall').id, .01)])
        data.ctrl[:] = result.commands
        mj.mj_step(model, data)
        minimum = min(minimum, .3-data.qpos[0])
    assert data.qpos[0] > .2
    assert minimum >= .009


def test_impossible_support_acceleration_is_rejected():
    model, data = motor_scene(.1)
    control = WrenchInverseDynamics(model)
    with pytest.raises(ControllerInfeasible):
        control.compute(data, data.qpos.copy(), acceleration_limits=[(np.ones((1, 1)), [0.], [0.])])


@pytest.mark.parametrize('position,velocity', [(0., 10.), (1.1, 0.)])
def test_servo_damping_remains_inside_the_total_actuator_force_limit(position, velocity):
    model = mj.MjModel.from_xml_string('''<mujoco><worldbody>
    <body><joint name="hinge" actuatorfrcrange="-2 2"/>
    <geom type="sphere" size=".1" mass="1"/></body></worldbody>
    <actuator><position joint="hinge" kp="500" kv="5" ctrlrange="-1 1"/></actuator></mujoco>''')
    data = mj.MjData(model)
    data.qpos[0] = position
    data.qvel[0] = velocity
    mj.mj_forward(model, data)
    controller = WrenchInverseDynamics(model)
    result = controller.compute(data, np.array([1.]), torque_reference=[100.], command_reference=[1.], torque_weight=1e6)
    data.ctrl[:] = result.commands
    mj.mj_forward(model, data)
    np.testing.assert_allclose(data.qfrc_actuator, result.actuator_forces, atol=1e-8)
    assert abs(data.qfrc_actuator[0]) <= 2.00001
    assert model.dof_damping[0] == 0.
    assert result.commands[0] == pytest.approx(1., abs=1e-5)
