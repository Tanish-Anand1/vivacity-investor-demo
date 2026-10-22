"""Editor acceptance checks against compiled MuJoCo physics and SQLite state."""
import pytest
import mujoco as mj
from fastapi.testclient import TestClient

from vivacity.api import create_app
from vivacity.runtime import Conflict, Runtime
from vivacity.schemas import CreateWorld, EditorChange, EditorGeometryAction, RoboticsConfig


@pytest.fixture
def runtime(tmp_path):
    instance = Runtime(tmp_path / 'editor.sqlite3')
    yield instance
    instance.close()


def _create(runtime):
    return runtime.create_world(CreateWorld(backend='mujoco',
                                           config=RoboticsConfig(task='pick_place', obstacle_enabled=False)))


def test_editor_changes_native_mass_inertia_contact_and_gravity(runtime):
    world = _create(runtime)
    original = runtime.fork(world['id'])
    original_inertia = original.model.body_inertia[original.model.body('target').id].copy()
    world = runtime.edit_property(world['id'], EditorChange(
        expected_revision=0, entity_id='object', property_key='density', value=1000.))
    native = runtime.fork(world['id'])
    assert native.model.body_mass[native.model.body('target').id] == pytest.approx(.125)
    assert native.model.body_inertia[native.model.body('target').id][0] > original_inertia[0]
    world = runtime.edit_property(world['id'], EditorChange(
        expected_revision=1, entity_id='object', property_key='half_size_x', value=.028))
    native = runtime.fork(world['id'])
    assert native.model.geom_size[native.model.geom('cube').id][0] == pytest.approx(.028)
    assert native.model.body_mass[native.model.body('target').id] == pytest.approx(.14)
    world = runtime.edit_property(world['id'], EditorChange(
        expected_revision=2, entity_id='surface', property_key='friction', value=.25))
    native = runtime.fork(world['id'])
    assert native.model.geom_friction[native.model.geom('table').id][0] == pytest.approx(.25)
    for _ in range(120):
        mj.mj_step(native.model, native.data)
    table_cube = [contact for contact in native.data.contact[:native.data.ncon]
                  if {native.model.geom(contact.geom1).name,
                      native.model.geom(contact.geom2).name} == {'cube', 'table'}]
    assert table_cube and all(contact.friction[0] == pytest.approx(.25)
                              for contact in table_cube)
    world = runtime.edit_property(world['id'], EditorChange(
        expected_revision=3, entity_id='environment', property_key='gravity', value=4.))
    assert runtime.fork(world['id']).model.opt.gravity[2] == pytest.approx(-4.)
    slow = runtime.fork(world['id'])
    faster_world = runtime.edit_property(world['id'], EditorChange(
        expected_revision=4, entity_id='environment', property_key='gravity', value=12.))
    fast = runtime.fork(faster_world['id'])
    for trial in (slow, fast):
        address = trial.model.jnt_qposadr[trial.model.joint('cube_free').id]
        trial.data.qpos[address + 2] = .25
        trial.data.qvel[:] = 0
        mj.mj_forward(trial.model, trial.data)
        for _ in range(50):
            mj.mj_step(trial.model, trial.data)
    assert slow.data.body('target').xpos[2] > fast.data.body('target').xpos[2] + .02


def test_scene_primitives_are_measured_rotated_and_versioned(runtime):
    world = _create(runtime)
    world = runtime.edit_geometry(world['id'], EditorGeometryAction(expected_revision=0, action='add'))
    assert world['revision'] == 1
    world = runtime.edit_property(world['id'], EditorChange(
        expected_revision=1, entity_id='geometry:block_1', property_key='yaw_deg', value=45.))
    world = runtime.edit_property(world['id'], EditorChange(
        expected_revision=2, entity_id='geometry:block_1', property_key='position_y', value=.2))
    measured = runtime.observe(world['id'])['observation']['environment_geometries']
    geom = next(g for g in measured if g['name'] == 'environment_block_1')
    assert geom['position'][1] == pytest.approx(.2)
    assert abs(geom['quaternion_wxyz'][3]) > .38
    native = runtime.fork(world['id'])
    assert native.model.geom_size[native.model.geom('environment_block_1').id][0] == pytest.approx(.05)
    from vivacity.schemas import EditorMove
    world = runtime.move_geometry(world['id'], EditorMove(expected_revision=3,
        entity_id='geometry:block_1', position=[.6,-.2,.08]))
    moved = runtime.observe(world['id'])['observation']['environment_geometries']
    assert next(g for g in moved if g['name']=='environment_block_1')['position'][1] == pytest.approx(-.2)
    assert [version['revision'] for version in runtime.world_versions(world['id'])] == [4, 3, 2, 1, 0]
    restored = runtime.restore_world_version(world['id'], 0, expected_revision=4)
    assert restored['revision'] == 5
    assert restored['config']['scene_geometries'] == []
    assert all(g['name'] != 'environment_block_1' for g in runtime.observe(world['id'])['observation'].get('environment_geometries', []))
    assert runtime.world_versions(world['id'])[0]['source_revision'] == 0
    with pytest.raises(Conflict):
        runtime.restore_world_version(world['id'], 1, expected_revision=4)


def test_invalid_and_unsupported_editor_requests_leave_world_unchanged(runtime):
    world = _create(runtime)
    for change in (
        EditorChange(expected_revision=0, entity_id='object', property_key='mass', value=-1.),
        EditorChange(expected_revision=0, entity_id='robot', property_key='joint_topology', value=3.),
        EditorChange(expected_revision=0, entity_id='object', property_key='density', value=5000.),
    ):
        with pytest.raises(ValueError):
            runtime.edit_property(world['id'], change)
    assert runtime.get_world(world['id'])['revision'] == 0
    with pytest.raises(Conflict):
        runtime.edit_geometry(world['id'], EditorGeometryAction(expected_revision=1, action='add'))
    assert runtime.get_world(world['id'])['config']['scene_geometries'] == []


def test_static_primitive_duplicate_and_delete_update_native_scene(runtime):
    world = _create(runtime)
    world = runtime.edit_geometry(world['id'], EditorGeometryAction(
        expected_revision=0, action='add', geometry_type='cylinder'))
    world = runtime.edit_geometry(world['id'], EditorGeometryAction(
        expected_revision=1, action='duplicate', entity_id='geometry:cylinder_1'))
    geoms = runtime.observe(world['id'])['observation']['environment_geometries']
    assert {item['name'] for item in geoms} == {'environment_cylinder_1',
                                                'environment_cylinder_1_1'}
    assert all(item['type'] == 'cylinder' for item in geoms)
    world = runtime.edit_geometry(world['id'], EditorGeometryAction(
        expected_revision=2, action='delete', entity_id='geometry:cylinder_1'))
    geoms = runtime.observe(world['id'])['observation']['environment_geometries']
    assert [item['name'] for item in geoms] == ['environment_cylinder_1_1']
    assert runtime.fork(world['id']).model.geom('environment_cylinder_1_1').id >= 0


def test_editor_http_contract_and_persisted_versions(tmp_path):
    database = tmp_path / 'http-editor.sqlite3'
    with TestClient(create_app(database)) as client:
        created = client.post('/v1/worlds', json={'backend':'mujoco','config':{'task':'pick_place','obstacle_enabled':False}})
        assert created.status_code == 201
        world_id = created.json()['id']
        editor = client.get(f'/v1/worlds/{world_id}/editor')
        assert editor.status_code == 200
        assert any(e['id'] == 'surface' for e in editor.json()['entities'])
        response = client.post(f'/v1/worlds/{world_id}/editor/geometries',
                               json={'expected_revision':0,'action':'add','geometry_type':'box'})
        assert response.status_code == 200
        assert client.get(f'/v1/worlds/{world_id}/state').json()['observation']['environment_geometries']
        stale = client.patch(f'/v1/worlds/{world_id}/editor/properties', json={
            'expected_revision':0, 'entity_id':'surface','property_key':'friction','value':.5})
        assert stale.status_code == 409
        invalid = client.patch(f'/v1/worlds/{world_id}/editor/properties', json={
            'expected_revision':1,'entity_id':'surface','property_key':'friction','value':-1})
        assert invalid.status_code == 422
        versions = client.get(f'/v1/worlds/{world_id}/versions')
        assert versions.status_code == 200
        assert [v['revision'] for v in versions.json()] == [1,0]
    with TestClient(create_app(database)) as client:
        versions = client.get(f'/v1/worlds/{world_id}/versions')
        assert [v['revision'] for v in versions.json()] == [1,0]
