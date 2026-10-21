"""Public template readiness and actual workcell execution regressions."""
import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.templates import catalog, resolve, TemplateSelection
from vivacity.schemas import ExperimentRequest


@pytest.mark.parametrize('world,task', [
    (world, task) for world in ('manufacturing','warehouse','inspection','cluttered')
    for task in ('pick_place','obstacle_transfer')
] + [('textile','cloth_fold')])
def test_runnable_templates_use_real_mujoco(runtime, world, task):
    request = resolve(TemplateSelection(world=world,task=task))
    w = runtime.create_world(request)
    observed = runtime.observe(w['id'])['observation']
    assert observed['body_transforms'] and observed['time'] == 0
    initial = runtime.snapshot(w['id'])
    assert initial['integration_state']
    experiment = runtime.wait(runtime.submit(w['id'], ExperimentRequest(
        search_candidates=50 if task=='cloth_fold' else 256,
        physics_budget=3,execute_selected=True,max_simulation_seconds=40))['id'])
    assert experiment['status']=='completed', experiment
    branches = runtime.store.branches(experiment['id'])
    assert branches and any(b['performance']['simulation_steps']>0 for b in branches)
    assert all(b['evaluation']['status'] != 'adapter_failure' for b in branches)
    replay = runtime.replay(experiment['id'])
    assert len(replay['branches'])==len(branches)
    assert all(r['frames']==b['trace'] for r,b in zip(replay['branches'],branches))
    if experiment['selected_branch_id']:
        assert experiment['result']['execution_evaluation']['success'], experiment
    else:
        assert not any(b['evaluation']['success'] for b in branches)


def test_catalog_public_contract_and_science_backend(tmp_path):
    with TestClient(create_app(tmp_path/'catalog.sqlite')) as client:
        public = client.get('/v1/templates').json()
        assert public==catalog()
        assert all(len(public[key])==5 for key in ('arms','worlds','tasks'))
        assert [o['id'] for o in public['arms'] if o['status']!='reference']==['panda','ur5e','iiwa','scara','dual_arm']
        assert set(client.get('/health').json()['backends'])=={'mujoco','scipy','cloth'}
        assert client.post('/v1/worlds',json={'backend':'scipy'}).status_code==201
        spec=client.get('/openapi.json').json()
        assert 'ScienceConfig' in spec['components']['schemas']
        assert spec['components']['schemas']['CreateWorld']['properties']['backend']['enum']==['mujoco','scipy','cloth']
        for body in ({'arm':'missing'},{'task':'missing'},{'arm':'ur5e','task':'cloth_fold','world':'textile'},
                     {'task':'cloth_fold'},{'world':'textile'},{'world':'missing'}):
            response=client.post('/v1/templates/resolve',json=body)
            assert response.status_code==422, response.text
        resolved=client.post('/v1/templates/resolve',json={'world':'warehouse'}).json()
        w=client.post('/v1/worlds',json=resolved)
        assert w.status_code==201
        assert w.json()['config']['cube_mass']==.04 and w.json()['history']==[]


def test_catalog_does_not_share_mutable_readiness():
    edited=catalog();edited['arms'][1]['status']='reference'
    assert catalog()['arms'][1]['status']=='available'
