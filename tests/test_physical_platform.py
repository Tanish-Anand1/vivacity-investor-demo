import numpy as np
import mujoco as mj
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from vivacity.schemas import RoboticsConfig, PhysicsSettings
from vivacity.pick_place import PickPlaceBackend
from vivacity.physical_properties import MATERIALS
from vivacity.physics_validation import run_benchmarks


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setenv('VIVACITY_HEADLESS_GEOMETRY', '1')
    return PickPlaceBackend()


def config(**kw):
    return RoboticsConfig(task='pick_place', obstacle_enabled=False, **kw).model_dump()


def test_analytical_benchmarks_and_repeatability():
    r = run_benchmarks()
    assert r['passed']==r['total']==8, r['cases']
    assert r['performance']['simulation_steps']==4600
    assert r['cases'][0]['absolute_error']<1e-7
    assert r['cases'][-1]['absolute_error']==0


@pytest.mark.parametrize('material', list(MATERIALS))
def test_material_changes_native_contacts_without_overriding_mass(backend, material):
    w = backend.create_world(config(object_material=material),7)
    preset = MATERIALS[material]
    assert w.model.geom('cube').friction.tolist()==[preset['sliding'],preset['torsional'],preset['rolling']]
    assert w.model.geom('cube').condim[0]==6
    assert w.model.body('target').mass[0]==.06


@pytest.mark.parametrize('setting', [dict(gravity_m_s2=-1),dict(air_density_kg_m3=6),dict(wind_velocity_m_s=[21,0,0]),dict(object_force_n=[3,0,0]),dict(object_torque_nm=[0,0,.3]),dict(gripper_force_scale=0)])
def test_physics_bounds(setting):
    with pytest.raises(ValidationError): PhysicsSettings(**setting)


def test_gravity_wind_and_force_are_native_forkable_inputs(backend):
    w = backend.create_world(config(physics=dict(gravity_m_s2=4.,air_density_kg_m3=1.225,wind_velocity_m_s=[5,0,0],object_force_n=[.1,0,0])),7)
    snap = backend.snapshot(w); a = backend.fork(snap); b = backend.fork(snap)
    np.testing.assert_array_equal(a.model.opt.gravity, [0,0,-4])
    assert a.model.opt.density==1.225
    np.testing.assert_array_equal(a.data.xfrc_applied[a.model.body('target').id], [.1,0,0,0,0,0])
    before = backend.snapshot(a)['integration_state']
    inspection = backend.observe(a)['inspection']
    assert inspection['object']['mass_kg']==.06
    assert inspection['environment']['air_density_kg_m3']==1.225
    # Observation must not corrupt integration inputs/warmstart.
    assert before==backend.snapshot(a)['integration_state']
    mj.mj_step(a.model,a.data,nstep=30)
    assert b.data.time==0
    backend.restore(a,snap)
    assert backend.snapshot(a)==snap


def test_actual_air_intervention_and_measured_contact_vectors(backend):
    worlds = [backend.create_world(config(physics=p),7) for p in ({'gravity_m_s2':0.}, {'gravity_m_s2':0.,'air_density_kg_m3':1.225,'wind_velocity_m_s':[10,0,0]})]
    for w in worlds:
        mj.mj_step(w.model,w.data,nstep=300)
    assert worlds[1].data.qpos[-7]>worlds[0].data.qpos[-7]+.001
    w = backend.create_world(config(),7)
    mj.mj_step(w.model,w.data,nstep=500); mj.mj_forward(w.model,w.data)
    inspection = backend.observe(w)['inspection']
    cube_contacts = [c for c in inspection['contacts'] if 'cube' in c['geoms']]
    assert cube_contacts and sum(c['normal_force_n'] for c in cube_contacts)>0
    assert all(np.isfinite(c['force_on_geom2_n']).all() for c in cube_contacts)


def test_gripper_limit_and_geometry_hash_change(backend):
    a = backend.create_world(config(),7)
    b = backend.create_world(config(physics={'gripper_force_scale':.1}),7)
    assert a.model_hash!=b.model_hash
    np.testing.assert_array_equal(b.model.actuator_forcerange[7], [-10,10])


def test_owned_import_preview_precedes_mapping(tmp_path):
    from vivacity.api import create_app
    with TestClient(create_app(tmp_path/'imports.sqlite')) as c:
        headers={'X-Workspace-Token':'a'*64}
        upload=c.post('/v1/workspace/imports?filename=triangle.obj',headers=headers,content=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
        assert upload.status_code==201, upload.text
        identifier=upload.json()['id']
        preview=c.get('/v1/workspace/imports/'+identifier+'/preview',headers=headers)
        assert preview.status_code==200 and preview.json()['triangle_count']==1
        assert c.get('/v1/workspace/imports/'+identifier+'/preview',headers={'X-Workspace-Token':'b'*64}).status_code==404


def test_saved_configuration_resolves_physics_and_material(tmp_path):
    from vivacity.api import create_app
    with TestClient(create_app(tmp_path/'configuration.sqlite')) as c:
        headers={'X-Workspace-Token':'a'*64}
        body={'name':'Air experiment','environment_id':'desktop','object_material':'rubber','physics':{'gravity_m_s2':3.7,'air_density_kg_m3':1.225,'wind_velocity_m_s':[5,0,0]}}
        r=c.post('/v1/workspace/configurations',headers=headers,json=body)
        assert r.status_code==201, r.text
        saved=c.get('/v1/workspace/configurations/'+r.json()['id'],headers=headers).json()['configuration']
        resolved=c.post('/v1/workspace/configurations/resolve',headers=headers,json=saved).json()['world']['config']
        assert resolved['physics']['gravity_m_s2']==3.7 and resolved['object_material']=='rubber'


def test_native_execution_records_actual_air_and_weak_grip_failure(backend):
    from vivacity.native_pick_place import NativePickup
    base=backend.create_world(config(),7)
    actions,_=backend.candidates(base,3,100)
    action=next(a for a in actions if a['planning_feasible'] and a['stages'])
    limits={'max_simulation_seconds':25,'max_wall_seconds':120}
    result,evaluation,_=NativePickup(backend,backend.snapshot(base)).simulate(action,limits)
    assert evaluation['success'], evaluation
    assert all('inspection' in f for f in result['trace'])
    weak=backend.create_world(config(cube_mass=.15,cube_friction=.05,physics={'air_density_kg_m3':1.225,'gripper_force_scale':.05}),7)
    result,evaluation,_=NativePickup(backend,backend.snapshot(weak)).simulate(action,limits)
    assert not evaluation['success'], evaluation
    assert evaluation['status'] in ('grasp_failure','dropped_object','controller_failure'), evaluation
    assert result['trace'][-1]['inspection']['environment']['air_density_kg_m3']==1.225


def test_validation_api_persistence_and_owner_boundary(tmp_path):
    from vivacity.api import create_app
    app = create_app(tmp_path/'physics.sqlite')
    with TestClient(app) as client:
        headers = {'X-Workspace-Token':'a'*64}
        r = client.post('/v1/workspace/physics-validations',headers=headers)
        assert r.status_code==201, r.text
        assert r.json()['passed']==8
        id = r.json()['id']
        assert client.get('/v1/workspace/physics-validations/'+id,headers={'X-Workspace-Token':'b'*64}).status_code==404
        assert client.get('/v1/workspace/physics-validations/'+id).status_code==422
        assert len(client.get('/v1/workspace/materials').json()['materials'])==8
    with TestClient(create_app(tmp_path/'physics.sqlite')) as client:
        assert client.get('/v1/workspace/physics-validations/'+id,headers=headers).json()['cases']==r.json()['cases']
