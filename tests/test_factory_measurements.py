import mujoco as mj
import numpy as np
import pytest
from vivacity.factory import FactoryBackend,FactorySettings

def test_power_work_torque_and_snapshot_ledger_match_engine():
    b=FactoryBackend();w=b.create_world(FactorySettings(carton_count=1).model_dump());b.apply_action(w,{'infeed':.09})
    net=positive=0.
    for _ in range(100):
        b.step(w);p=w.data.actuator_force*w.data.actuator_velocity
        net+=float(p.sum())*.002;positive+=float(np.maximum(p,0).sum())*.002
    values=b.observe(w)['measurements']
    assert values['mechanical_work_j']==pytest.approx(net)
    assert values['positive_actuator_work_j']==pytest.approx(positive)
    assert values['actuator_power_w']==pytest.approx(float(p.sum()))
    assert values['robot']['joint_torque_nm']==w.data.qfrc_actuator[:7].tolist()
    assert values['electrical_energy_j'] is None
    assert values['dynamics_time_s']==pytest.approx(w.data.time-.002)
    assert b.snapshot(b.fork(b.snapshot(w)))==b.snapshot(w)

def test_contact_measurements_match_native_contact_force():
    b=FactoryBackend();w=b.create_world(FactorySettings(carton_count=1).model_dump());b.step(w,300)
    value=b.observe(w)['measurements'];forces=[]
    for i in range(w.data.ncon):
        force=np.zeros(6);mj.mj_contactForce(w.model,w.data,i,force)
        if force[0]>1e-5:forces.append(float(force[0]))
    np.testing.assert_allclose([c['normal_force_n'] for c in value['contacts']],forces)
    assert value['objects'][0]['contact_count']>0
    assert value['objects'][0]['principal_inertia_kg_m2']==w.model.body_inertia[w.model.body('target').id].tolist()

def test_free_fall_acceleration_and_energy_are_consistent():
    b=FactoryBackend();w=b.create_world(FactorySettings(carton_count=1).model_dump());adr=w.model.jnt_qposadr[w.model.joint('cube_free').id]
    w.data.qpos[adr:adr+3]=[1.5,-.5,.5];mj.mj_forward(w.model,w.data)
    initial=b.observe(w)['measurements']['objects'][0]
    b.step(w,100);final=b.observe(w)['measurements']['objects'][0]
    np.testing.assert_allclose(final['linear_acceleration_m_s2'],[0,0,-9.81],atol=.001)
    assert final['kinetic_energy_j']+final['potential_energy_j']==pytest.approx(initial['potential_energy_j'],rel=.005)
    assert final['contact_count']==0
