import json
import mujoco as mj
import numpy as np
import pytest
from vivacity.factory import FactoryBackend, FactorySettings, LAYOUT


@pytest.fixture
def backend():return FactoryBackend()


def test_model_and_actual_roller_actuators(backend):
    w=backend.create_world(FactorySettings().model_dump())
    assert w.model.nu>60
    assert w.model.opt.timestep==.002
    assert w.model.body('target').mass[0]==pytest.approx(.06)
    assert backend.observe(w)['time']==0


def test_rollers_move_free_carton_by_contact_and_station_stop(backend):
    w=backend.create_world(FactorySettings(carton_count=1).model_dump())
    initial=w.data.body('target').xpos.copy()
    backend.apply_action(w,{'infeed':.09})
    contact_observed=False
    for _ in range(4500):
        backend.step(w)
        contact_observed |= any('cube' in (w.model.geom(c.geom1).name,w.model.geom(c.geom2).name) for c in w.data.contact[:w.data.ncon])
        if w.data.body('target').xpos[1]>=-.27:
            backend.apply_action(w,{'infeed':0})
            backend.step(w,250)
            break
    assert w.data.body('target').xpos[1]>initial[1]+.6
    assert backend.evaluate(w,{})['reached_station']
    assert abs(w.data.body('target').xpos[0]-.5)<.025
    assert w.data.body('target').xpos[2]>.015
    assert contact_observed


def test_no_motor_no_conveyor_transport(backend):
    w=backend.create_world(FactorySettings(carton_count=1).model_dump())
    backend.step(w,1500)
    assert w.data.body('target').xpos[1]==pytest.approx(-.94,abs=.01)


def test_full_snapshot_fork_and_deterministic_replay(backend):
    w=backend.create_world(FactorySettings(carton_count=1).model_dump())
    backend.apply_action(w,{'infeed':.08});backend.step(w,300)
    state=backend.snapshot(w);a=backend.fork(state);b=backend.fork(state)
    assert a.data is not b.data
    assert state['state_spec']==int(mj.mjtState.mjSTATE_INTEGRATION)
    backend.step(a,500);assert b.data.time==w.data.time
    backend.step(b,500)
    np.testing.assert_array_equal(a.data.qpos,b.data.qpos)
    np.testing.assert_array_equal(a.data.ctrl,w.data.ctrl)
    backend.restore(a,state)
    assert backend.snapshot(a)==state


def test_settings_and_drive_reject_invalid_values(backend):
    with pytest.raises(ValueError):FactorySettings(carton_count=5000)
    with pytest.raises(ValueError):FactorySettings(conveyor_speed_m_s=float('nan'))
    w=backend.create_world(FactorySettings().model_dump())
    with pytest.raises(ValueError):backend.apply_action(w,{'infeed':1.})
    with pytest.raises(ValueError):backend.apply_action(w,{'made_up':.1})
