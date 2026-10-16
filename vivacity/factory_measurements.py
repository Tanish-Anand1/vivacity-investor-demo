"""Engine samples and explicitly derived mechanical quantities in SI units."""
import mujoco as mj
import numpy as np


def measure(world):
    m,d=world.model,world.data
    contacts=[];finger_force=0.
    for i,c in enumerate(d.contact[:d.ncon]):
        force=np.zeros(6);mj.mj_contactForce(m,d,i,force)
        if force[0]<=1e-5:continue
        bodies=[m.body(int(m.geom_bodyid[g])).name for g in (c.geom1,c.geom2)]
        carton=any(name=='target' or name.startswith('carton_') for name in bodies)
        if carton and any(name in ('left_finger','right_finger') for name in bodies):finger_force+=float(force[0])
        contacts.append({'bodies':bodies,'geoms':[m.geom(g).name for g in (c.geom1,c.geom2)],
                         'position_m':c.pos.tolist(),'normal_force_n':float(force[0]),
                         'force_on_geom2_world_n':(c.frame.reshape(3,3).T@force[:3]).tolist()})
    objects=[]
    for i in range(world.config['carton_count']):
        name='target' if i==0 else f'carton_{i}';body=m.body(name).id
        joint=m.joint('cube_free' if i==0 else name+'_free').id;dof=int(m.jnt_dofadr[joint])
        velocity=np.zeros(6);mj.mj_objectVelocity(m,d,mj.mjtObj.mjOBJ_BODY,body,velocity,0)
        mass=float(m.body_mass[body]);principal=d.ximat[body].reshape(3,3).T@velocity[:3]
        kinetic=.5*mass*float(velocity[3:]@velocity[3:])+.5*float((principal**2)@m.body_inertia[body])
        potential=-mass*float(m.opt.gravity@(d.xipos[body]-np.array([0,0,-.8])))
        geom=m.geom('cube' if i==0 else name).id
        objects.append({'id':name,'center_of_mass_m':d.xipos[body].tolist(),'mass_kg':mass,
                        'principal_inertia_kg_m2':m.body_inertia[body].tolist(),'friction':m.geom_friction[geom].tolist(),
                        'linear_acceleration_m_s2':d.qacc[dof:dof+3].tolist(),
                        'kinetic_energy_j':kinetic,'potential_energy_j':potential,
                        'contact_count':sum(name in c['bodies'] for c in contacts)})
    power=d.actuator_force*d.actuator_velocity
    return {'schema_version':'vivacity.factory-measurements/1.0','state_time_s':float(d.time),
            'dynamics_time_s':getattr(world,'force_time',float(d.time)),
            'robot':{'joint_position_rad':d.qpos[:7].tolist(),'joint_velocity_rad_s':d.qvel[:7].tolist(),
                     'joint_acceleration_rad_s2':d.qacc[:7].tolist(),'joint_torque_nm':d.qfrc_actuator[:7].tolist(),
                     'gripper_contact_normal_force_n':finger_force},
            'objects':objects,'contacts':contacts,'actuator_power_w':float(np.sum(power)),
            'robot_actuator_power_w':float(np.sum(power[:8])),
            'mechanical_work_j':world.work_integrals['net'],
            'positive_actuator_work_j':world.work_integrals['positive'],
            'robot_mechanical_work_j':world.work_integrals['robot'],
            'electrical_energy_j':None,
            'scope':'MuJoCo mechanical estimates; no motor efficiency model or measured electrical consumption'}
