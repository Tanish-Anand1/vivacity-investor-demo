from copy import deepcopy

import mujoco as mj
import numpy as np
import pytest

from vivacity.execution_checkpoint import (CheckpointBundle, CheckpointStore,
                                          ImmutableModelArtifact, IncompatibleCheckpoint, capture, restore)
from vivacity.storage import Store


class MemoryController:
    version = 'test.integrating-controller/1'

    def __init__(self, model):
        self.integral = 0.
        self.previous = 0.

    def snapshot(self):
        return {'integral': self.integral, 'previous': self.previous}

    def restore(self, state):
        self.integral, self.previous = state['integral'], state['previous']

    def step(self, model, data, rng):
        self.integral += (.3-data.qpos[0])*.001
        self.previous = 2*(.3-data.qpos[0])+.4*self.integral+rng.normal(0, .001)
        data.ctrl[:] = self.previous
        mj.mj_step(model, data)


def fixture():
    model = mj.MjModel.from_xml_string('''<mujoco><size nuserdata="2"/>
    <option timestep=".001"/><worldbody>
      <body name="marker" mocap="true" pos="0 0 2"><geom size=".01" contype="0" conaffinity="0"/></body>
      <body name="rotor" pos="0 0 1"><joint name="joint" axis="0 1 0"/>
        <geom type="capsule" fromto="0 0 0 .5 0 0" size=".025" mass="1"/></body>
    </worldbody><actuator><general joint="joint" dyntype="filter" dynprm=".02"/></actuator></mujoco>''')
    data = mj.MjData(model)
    data.userdata[:] = [2., 3.]
    data.xfrc_applied[model.body('rotor').id, 0] = .1
    data.mocap_pos[:] = [1., 2., 3.]
    controller, rng = MemoryController(model), np.random.default_rng(71)
    for _ in range(75):
        controller.step(model, data, rng)
    return model, data, controller, rng


def snap(model, data, controller, rng, **kwargs):
    defaults = dict(world_version='world-v1', task_state={'phase': 'moving', 'counter': 75},
                    perception_state={'track': {'pose': [1., 2., 3.], 'age': 2}},
                    order_ledger={'item-a': {'stage': 'collect'}},
                    next_frame_seq=1, steps_completed=75)
    defaults.update(kwargs)
    return capture(model, data, controller, rng=rng, **defaults)


def test_restart_restores_model_full_state_controller_rng_and_continuation():
    model, data, controller, rng = fixture()
    model.opt.gravity[:] = [0., 0., -7.]
    model.geom_friction[0] = [.6, .003, .0002]
    original = snap(model, data, controller, rng)
    branch_model, branch_data, branch_controller, branch_rng = restore(original, MemoryController)
    assert branch_model.opt.gravity.tolist() == [0., 0., -7.]
    assert branch_model.geom_friction[0].tolist() == [.6, .003, .0002]
    np.testing.assert_array_equal(branch_data.act, data.act)
    np.testing.assert_array_equal(branch_data.ctrl, data.ctrl)
    np.testing.assert_array_equal(branch_data.qacc_warmstart, data.qacc_warmstart)
    np.testing.assert_array_equal(branch_data.xfrc_applied, data.xfrc_applied)
    np.testing.assert_array_equal(branch_data.mocap_pos, data.mocap_pos)
    np.testing.assert_array_equal(branch_data.userdata, data.userdata)
    for _ in range(200):
        controller.step(model, data, rng)
        branch_controller.step(branch_model, branch_data, branch_rng)
    np.testing.assert_array_equal(branch_data.qpos, data.qpos)
    np.testing.assert_array_equal(branch_data.qvel, data.qvel)
    assert controller.snapshot() == branch_controller.snapshot()
    assert rng.bit_generator.state == branch_rng.bit_generator.state
    branch_model.opt.gravity[2] = -2.
    branch_data.ctrl[0] = 99.
    branch_controller.integral = 99.
    assert model.opt.gravity[2] == -7.
    assert data.ctrl[0] != 99. and controller.integral != 99.
    assert original.checkpoint.task_state['counter'] == 75


def test_transactional_frames_restart_owner_and_independent_fork(tmp_path):
    fixture_values = fixture()
    bundle = snap(*fixture_values)
    path = tmp_path/'checkpoints.sqlite3'
    store = CheckpointStore(Store(path))
    run = store.create('owner-a', 'world-v1')
    frame = {'qpos': fixture_values[1].qpos.tolist(), 'phase': 'moving'}
    store.commit(run, 'owner-a', bundle, [frame], expected_checkpoint_id=None)
    restarted = CheckpointStore(Store(path))
    loaded = restarted.load(run, 'owner-a')
    assert loaded.checkpoint == bundle.checkpoint
    assert loaded.model_binary == bundle.model_binary
    assert restarted.frames(run, 'owner-a') == [{'seq': 0, 'frame': frame}]
    for operation in (lambda: restarted.load(run, 'owner-b'),
                      lambda: restarted.frames(run, 'owner-b'),
                      lambda: restarted.fork(run, 'owner-b')):
        with pytest.raises(KeyError):
            operation()
    branch = restarted.fork(run, 'owner-a')
    forked = restarted.load(branch, 'owner-a')
    assert forked.checkpoint.parent_checkpoint_id == bundle.checkpoint.id
    assert forked.checkpoint.integration_state == bundle.checkpoint.integration_state
    assert forked.checkpoint.next_frame_seq == 0
    assert restarted.frames(branch, 'owner-a') == []
    assert restarted.frames(run, 'owner-a') == [{'seq': 0, 'frame': frame}]


def test_bad_batch_and_stale_writer_cannot_publish_frames(tmp_path):
    values = fixture()
    bundle = snap(*values)
    store = CheckpointStore(Store(tmp_path/'atomic.sqlite3'))
    run = store.create('owner', 'world-v1')
    with pytest.raises(ValueError, match='cursor'):
        store.commit(run, 'owner', bundle, [{'a': 1}, {'b': 2}], expected_checkpoint_id=None)
    assert store.frames(run, 'owner') == []
    store.commit(run, 'owner', bundle, [{'a': 1}], expected_checkpoint_id=None)
    with pytest.raises(ValueError, match='stale'):
        store.commit(run, 'owner', bundle, [], expected_checkpoint_id=None)
    assert store.frames(run, 'owner') == [{'seq': 0, 'frame': {'a': 1}}]
    assert store.load(run, 'owner').checkpoint.id == bundle.checkpoint.id


@pytest.mark.parametrize('field,value,match', [
    ('simulator_version', 'incompatible', 'simulator'),
    ('controller_version', 'incompatible', 'controller'),
    ('state_spec', 1, 'specification'),
    ('integration_state', [0.], 'does not match'),
    ('previous_action', [999.], 'action'),
])
def test_incompatible_checkpoints_fail_closed(field, value, match):
    original = snap(*fixture())
    invalid = CheckpointBundle(original.checkpoint.model_copy(update={field: value}), original.model_binary)
    with pytest.raises(IncompatibleCheckpoint, match=match):
        restore(invalid, MemoryController)


def test_corrupt_model_and_nonfinite_memory_rejected():
    original = snap(*fixture())
    with pytest.raises(IncompatibleCheckpoint, match='checksum'):
        restore(CheckpointBundle(original.checkpoint, original.model_binary+b'corruption'), MemoryController)
    with pytest.raises(ValueError):
        snap(*fixture(), task_state={'loss': float('nan')})


@pytest.mark.parametrize('generator', ['PCG64','PCG64DXSM','Philox','SFC64','MT19937'])
def test_supported_random_generators_preserve_integer_state(generator):
    model,data,controller,_ = fixture()
    rng = np.random.Generator(getattr(np.random,generator)(187))
    rng.normal(size=19)
    saved = snap(model,data,controller,rng)
    _,_,_,continued = restore(saved,MemoryController)
    np.testing.assert_array_equal(rng.normal(size=50),continued.normal(size=50))


@pytest.mark.parametrize('field', ['gravity', 'friction', 'gain', 'inertia'])
def test_reused_model_artifact_rejects_unversioned_configuration_changes(field):
    model, data, controller, rng = fixture()
    artifact = ImmutableModelArtifact(model)
    first = snap(model, data, controller, rng, model_artifact=artifact)
    controller.step(model, data, rng)
    second = snap(model, data, controller, rng, model_artifact=artifact)
    assert first.model_binary is second.model_binary
    assert first.checkpoint.model_sha256 == second.checkpoint.model_sha256
    if field == 'gravity':
        model.opt.gravity[2] = -8.
    elif field == 'friction':
        model.geom_friction[0, 0] = .2
    elif field == 'gain':
        model.actuator_gainprm[0, 0] = 2.
    else:
        model.body_inertia[2, 0] *= 1.2
    with pytest.raises(IncompatibleCheckpoint, match='new world version'):
        snap(model, data, controller, rng, model_artifact=artifact)
