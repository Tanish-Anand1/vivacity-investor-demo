import gc
from copy import deepcopy
import inspect

import mujoco as mj
import numpy as np
import pytest

from training.locomotion_contract import commands, observation
from training.native_locomotion import NativeLocomotion, Settings


@pytest.fixture(params=['h1','g1','apollo'])
def env(request):
    item=NativeLocomotion(request.param,Settings(duration_s=.1))
    yield item
    del item
    gc.collect()


def test_complete_mapping_steps_real_native_physics_and_reward_is_measured(env):
    model,data,contract=env.model,env.data,env.contract
    assert contract.action_size=={'h1':23,'g1':43,'apollo':36}[env.identity]
    assert env.observe().shape==(contract.observation_size,)
    assert contract.manifest['trained_policy'] is None
    before=data.qpos.copy()
    output=env.step(np.zeros(model.nu))
    assert data.time==pytest.approx(.02)
    assert not np.array_equal(before,data.qpos)
    assert env.state['steps_completed']==env.controller.steps==10
    actual=output['measurements']
    error=np.array(actual['local_linear_velocity_m_s'])[:2]-env.settings.command[:2]
    assert output['reward_terms']['velocity_tracking']==pytest.approx(np.exp(-(error @ error)/.25))
    assert output['reward']==pytest.approx(sum(output['reward_terms'].values())*.02)
    assert not output['task_success']
    assert actual['equality_constraints']==actual['mocap_bodies']==0
    assert actual['actuator_force_fraction']<=1.00001
    for action in (-np.ones(model.nu), np.ones(model.nu)):
        control=commands(contract,action,data.qpos[contract.qadr],data.qvel[contract.dofs])
        assert np.all(control>=model.actuator_ctrlrange[:,0])
        assert np.all(control<=model.actuator_ctrlrange[:,1])


def test_malformed_action_is_atomic_and_actor_cannot_read_scene_coordinates(env):
    before=env.snapshot()
    for invalid in (np.zeros(env.model.nu-1),np.full(env.model.nu,np.nan),np.full(env.model.nu,1.01)):
        with pytest.raises(ValueError,match='action'):
            env.step(invalid)
        assert env.snapshot().checkpoint.integration_state==before.checkpoint.integration_state
        assert env.controller.snapshot()==before.checkpoint.controller_state
    # Moving only the absolute root position at reset changes evaluator state,
    # but no absolute position appears in the actor observation.
    observed=env.observe()
    env.data.qpos[:3]+=[.4,-.2,.1]
    mj.mj_forward(env.model,env.data)
    np.testing.assert_array_equal(env.observe(),observed)
    assert 'model' not in inspect.signature(observation).parameters
    assert 'data' not in inspect.signature(observation).parameters


def test_full_checkpoint_restores_action_memory_and_independent_native_continuation(env):
    env.step(np.zeros(env.model.nu))
    saved=env.snapshot()
    branch=NativeLocomotion.from_checkpoint(saved)
    action=np.linspace(-.1,.1,env.model.nu)
    first,second=env.step(action),branch.step(action)
    np.testing.assert_array_equal(env.data.qpos,branch.data.qpos)
    np.testing.assert_array_equal(env.data.qvel,branch.data.qvel)
    np.testing.assert_array_equal(first['observation'],second['observation'])
    assert first['reward']==second['reward']
    assert env.controller.snapshot()==branch.controller.snapshot()
    env.step(np.zeros(env.model.nu))
    branch.step(np.full(env.model.nu,.25))
    assert not np.array_equal(env.data.qpos,branch.data.qpos)
    branch.controller.last_action[0]=.5
    assert env.controller.last_action[0]!=.5
    branch.model.opt.gravity[2]=-5.
    assert env.model.opt.gravity[2]==-9.81
    with pytest.raises(ValueError,match='immutable model changed'):
        branch.snapshot()
    changed=deepcopy(saved.checkpoint.task_state['contract_sha256'])
    saved.checkpoint.task_state['contract_sha256']='0'*64
    with pytest.raises(ValueError,match='contract changed'):
        NativeLocomotion.from_checkpoint(saved)
    saved.checkpoint.task_state['contract_sha256']=changed
    del branch


def test_time_limit_never_counts_as_task_success(env):
    while env.state['status']=='running':
        result=env.step(np.zeros(env.model.nu))
    assert env.state['status'] in ('time_limit','failed')
    assert not result['task_success']
    before=env.data.qpos.copy()
    with pytest.raises(RuntimeError,match='terminal trial'):
        env.step(np.zeros(env.model.nu))
    np.testing.assert_array_equal(env.data.qpos,before)


def test_deliberately_unstable_initial_condition_is_a_measured_failure(env):
    # Only the initial condition is edited. Native integration determines the
    # following state; no pose is overwritten by the environment's step.
    env.data.qpos[3:7]=[np.sqrt(.5),np.sqrt(.5),0.,0.]
    mj.mj_forward(env.model,env.data)
    result=env.step(np.zeros(env.model.nu))
    assert result['terminated'] and not result['truncated']
    assert result['failure']=='fallen'
    assert result['measurements']['tilt_rad']>.7
    assert not result['task_success']


@pytest.mark.parametrize('change',[{'command':(1.,0.,0.)},{'command':(0.,float('nan'),0.)},
    {'command':(0.,0.)},{'duration_s':float('inf')},{'duration_s':0.},
    {'control_steps':0},{'control_steps':True},{'seed':-1}])
def test_settings_reject_invalid_experiments(change):
    with pytest.raises(ValueError):
        Settings(**change)
