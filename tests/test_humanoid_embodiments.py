import gc

import mujoco as mj
import numpy as np
import pytest

from vivacity.cabinet_mechanism import CabinetConfig, append_cabinet, measure
from vivacity.humanoid_embodiments import FEET, compile_embodiment
from vivacity.stance_control import StanceController
from vivacity.humanoid_ik import site_pose


@pytest.fixture(params=['g1', 'apollo', 'h1'])
def embodiment(request):
    model, data, manifest = compile_embodiment(request.param)
    yield request.param, model, data, manifest
    del data, model
    gc.collect()


def test_complete_model_has_native_joint_mapping_force_limits_and_declared_tooling(embodiment):
    identity, model, data, manifest = embodiment
    assert model.nu == {'g1':43, 'apollo':36, 'h1':23}[identity]
    assert model.neq == model.nmocap == 0
    assert len(set(model.actuator_trnid[:, 0])) == model.nu
    assert model.jnt_type[0] == mj.mjtJoint.mjJNT_FREE
    assert all(model.actuator_ctrllimited)
    assert manifest['mobility_policy'] is None and not manifest['task_acceptance']
    assert len(manifest['tooling']) == (0 if identity == 'g1' else 2)
    assert manifest['robot_mass_kg'] > 30.
    for joint in manifest['joints']:
        if joint['limited']:
            angle = data.qpos[joint['qpos_address']]
            assert joint['range'][0]-1e-8 <= angle <= joint['range'][1]+1e-8, {
                'joint':joint, 'actual':float(angle),
                'reset_key':float(model.key_qpos[0,joint['qpos_address']]),
                'adjustments':manifest['initial_pose_adjustments'],
                'type_matches_hinge':bool(model.jnt_type[model.joint(joint['name']).id] == mj.mjtJoint.mjJNT_HINGE),
            }
    floor = model.geom('floor').id
    assert min((contact.dist for contact in data.contact[:data.ncon]
                if floor in (contact.geom1, contact.geom2)), default=0.) >= -1e-6
    for contact in data.contact[:data.ncon]:
        names = (model.geom(contact.geom1).name or '', model.geom(contact.geom2).name or '')
        if any('_service_' in name for name in names):
            assert contact.dist >= -1e-6, names
    if identity == 'h1':
        # A policy accepting only ten lower-body actions must not be assigned.
        assert model.nu != 10 and any('shoulder' in value['joint'] for value in manifest['actuators'])


def test_bounded_stance_steps_native_physics_and_checkpoint_restores_commands(embodiment):
    identity, model, data, manifest = embodiment
    controller = StanceController(model, identity)
    for _ in range(300):
        before = data.qpos.copy()
        command = controller.compute(data)
        np.testing.assert_array_equal(data.qpos, before)
        assert np.all(command >= model.actuator_ctrlrange[:, 0]-1e-8)
        assert np.all(command <= model.actuator_ctrlrange[:, 1]+1e-8)
        data.ctrl[:] = command
        mj.mj_step(model, data)
    state_type = mj.mjtState.mjSTATE_INTEGRATION
    state = np.empty(mj.mj_stateSize(model, state_type))
    mj.mj_getState(model, data, state, state_type)
    native = np.empty(mj.mj_sizeModel(model), dtype=np.uint8)
    mj.mj_saveModel(model, buffer=native)
    fork_model = mj.MjModel.from_binary_path('snapshot.mjb', {'snapshot.mjb':native.tobytes()})
    fork = mj.MjData(fork_model)
    mj.mj_setState(fork_model, fork, state, state_type)
    mj.mj_forward(fork_model, fork)
    restored = StanceController(fork_model, identity)
    restored.restore(controller.snapshot())
    for _ in range(30):
        # Forward aligns all derived native state at the snapshot boundary.
        mj.mj_forward(model, data)
        mj.mj_forward(fork_model, fork)
        data.ctrl[:] = controller.compute(data)
        fork.ctrl[:] = restored.compute(fork)
        mj.mj_step(model, data)
        mj.mj_step(fork_model, fork)
    np.testing.assert_array_equal(data.qpos, fork.qpos)
    assert controller.snapshot() == restored.snapshot()
    assert data.qpos[2] > .9*model.key_qpos[0, 2]
    assert 2*np.arccos(np.clip(abs(data.qpos[3]), 0, 1)) < .1


def test_apollo_cabinet_compiles_with_both_visible_tools_and_free_cartridge_identities():
    config = CabinetConfig()
    model, data, manifest = compile_embodiment('apollo', append_scene=lambda root:append_cabinet(root, config))
    assert model.nu == 36
    assert model.joint('service_door_hinge').type[0] == mj.mjtJoint.mjJNT_HINGE
    assert model.joint('service_old_free').type[0] == mj.mjtJoint.mjJNT_FREE
    assert model.joint('service_replacement_free').type[0] == mj.mjtJoint.mjJNT_FREE
    assert not measure(model, data, config)['mechanism_ready']
    assert model.neq == model.nmocap == 0
    # Apollo's default disabled contacts must not disable added tooling/fixtures.
    for name in ('service_door_panel', 'service_old_shell', 'l_service_positive_pad', 'r_service_negative_pad'):
        assert model.geom(name).contype[0] == model.geom(name).conaffinity[0] == 1
    initial = data.qpos.copy()
    rotation = np.array([[0,0,-1],[-1,0,0],[0,1,0.]])
    for side, position in (('r',[.52,-.18,1.1]), ('l',[.52,.145,1.165])):
        joints = [f'{side}_{part}' for part in ('shoulder_aa','shoulder_ie','shoulder_fe','elbow_fe',
                                              'wrist_roll','wrist_yaw','wrist_pitch')]
        planned = site_pose(model, data.qpos, side+'_service_tcp', joints, position, rotation)
        assert planned.feasible and planned.position_error_m < .005
        np.testing.assert_array_equal(data.qpos, initial)
        impossible = site_pose(model, data.qpos, side+'_service_tcp', joints, [3.,0.,1.1], rotation)
        assert not impossible.feasible
    controller = StanceController(model, 'apollo')
    for _ in range(300):
        data.ctrl[:] = controller.compute(data)
        mj.mj_step(model, data)
    assert data.qpos[2] > .95
    assert not measure(model, data, config)['mechanism_ready']


def test_posture_weight_override_preserves_default_and_rejects_invalid_before_mutation(embodiment):
    identity,model,data,_ = embodiment
    original=StanceController(model,identity)
    weighted=StanceController(model,identity)
    np.testing.assert_array_equal(original.compute(data),weighted.compute(data,
        posture_weights=np.full(model.nu,original.reference_weight)))
    before=weighted.snapshot()
    for invalid in (np.ones(model.nu+1),np.full(model.nu,np.nan),
                    np.zeros(model.nu),np.full(model.nu,101.)):
        with pytest.raises(ValueError,match='posture weights'):
            weighted.compute(data,posture_weights=invalid)
        assert weighted.snapshot()==before
