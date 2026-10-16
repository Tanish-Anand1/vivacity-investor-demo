import json
import time
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.providers import OpenAIInterpreter, WorldLabs, ProviderError, asset_url
from vivacity.workspace_schemas import EnvironmentSpec
from vivacity.schemas import RoboticsConfig
from vivacity.robot_models import ModelPickupBackend, MODELS
from vivacity.pick_place import PickPlaceBackend
from vivacity.imports import triangle_preview

OWNER={'X-Workspace-Token':'workspace-owner-capability-1234567890'}
OTHER={'X-Workspace-Token':'other-workspace-capability-1234567890'}


def test_library_configuration_ownership_and_persistence(tmp_path):
    database=tmp_path/'workspace.sqlite'
    with TestClient(create_app(database)) as client:
        assert client.get('/v1/workspace/worlds').status_code==422
        worlds=client.get('/v1/workspace/worlds',headers=OWNER).json()
        assert len(worlds)==13 and all(w['spec']['geometries'] for w in worlds)
        copied=client.post('/v1/workspace/worlds',headers=OWNER,json={'source_id':'desktop'}).json()
        assert client.get('/v1/workspace/worlds/'+copied['id'],headers=OTHER).status_code==404
        renamed=client.patch('/v1/workspace/worlds/'+copied['id'],headers=OWNER,json={'name':'My cell'})
        assert renamed.status_code==200 and renamed.json()['name']=='My cell'
        body={'name':'Repeatable test','environment_id':copied['id'],'robot_id':'ur5e','validation_trials':3}
        resolved=client.post('/v1/workspace/configurations/resolve',headers=OWNER,json=body)
        assert resolved.status_code==200, resolved.text
        assert resolved.json()['world']['config']['robot_model']=='ur5e'
        assert resolved.json()['world']['config']['environment']['id']==copied['id']
        saved=client.post('/v1/workspace/configurations',headers=OWNER,json=body)
        assert saved.status_code==201, saved.text
        assert client.get('/v1/workspace/configurations/'+saved.json()['id'],headers=OTHER).status_code==404
        assert client.post('/v1/workspace/worlds/'+copied['id']+'/archive',headers=OWNER).status_code==200
        assert client.get('/v1/workspace/worlds/'+copied['id'],headers=OWNER).status_code==404
        assert client.post('/v1/workspace/worlds/'+copied['id']+'/restore',headers=OWNER).status_code==200
    with TestClient(create_app(database)) as client:
        assert client.get('/v1/workspace/worlds/'+copied['id'],headers=OWNER).json()['name']=='My cell'
        assert len(client.get('/v1/workspace/configurations',headers=OWNER).json())==1


def test_import_mapping_uses_actual_uploaded_geometry_and_capability(tmp_path):
    obj=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'
    with TestClient(create_app(tmp_path/'import.sqlite')) as client:
        record=client.post('/v1/workspace/imports?filename=triangle.obj',headers=OWNER,content=obj)
        assert record.status_code==201,record.text
        identifier=record.json()['id']
        legacy=client.app.state.imports._load(identifier)
        legacy['preview']['indices']=[[0,1,2]]
        legacy['preview'].pop('coordinate_system')
        client.app.state.imports._save(legacy)
        assert client.get('/v1/imports/'+identifier,headers=OTHER).status_code==403
        assert client.get('/v1/imports/'+identifier,headers=OWNER).status_code==200
        assert client.post('/v1/workspace/imports/'+identifier+'/map',headers=OTHER,json={'name':'Private triangle'}).status_code==404
        mapped=client.post('/v1/workspace/imports/'+identifier+'/map',headers=OWNER,json={'name':'Triangle','scale':.5})
        assert mapped.status_code==201,mapped.text
        world=mapped.json();preview=client.get('/v1/workspace/worlds/'+world['id']+'/preview',headers=OWNER).json()
        assert preview['vertex_count']==3 and preview['triangle_count']==1
        assert preview['indices']==[0,1,2] and preview['coordinate_system']
        assert world['spec']['geometries'][0]['size']==[.25,.005,.25]
        assert world['mapping']['source_sha256']==record.json()['sha256']
        copied=client.post('/v1/workspace/worlds',headers=OWNER,json={'source_id':world['id']}).json()
        assert copied['mapping']==world['mapping'] and copied['import_id']==world['import_id']
        assert client.get('/v1/workspace/worlds/'+copied['id']+'/preview',headers=OWNER).json()==preview
        assert client.post('/v1/workspace/imports/'+identifier+'/map',headers=OWNER,json={'name':'Huge','scale':100}).status_code==422


def test_configuration_bounds_and_supported_compatibility(tmp_path):
    with TestClient(create_app(tmp_path/'bounds.sqlite')) as client:
        for patch in ({'robot_id':'unknown'},{'gripper_id':'vacuum'},{'object_mass_kg':50},{'object_half_sizes':[.3,.3,.3]},
                      {'validation_trials':5000},{'operation_id':'cloth_fold'},{'operation_id':'run_shell_command'}):
            response=client.post('/v1/workspace/configurations/resolve',headers=OWNER,json={'name':'Test','environment_id':'desktop'}|patch)
            assert response.status_code==422,response.text
        for operation in ('sorting','assembly','stacking','insertion','machine_tending'):
            response=client.post('/v1/workspace/configurations/resolve',headers=OWNER,json={'name':'Physical goal','environment_id':'desktop','operation_id':operation})
            assert response.status_code==200,response.text
            assert response.json()['world']['config']['physical_operation']==operation


def test_provider_headers_structure_and_secret_redaction(monkeypatch):
    monkeypatch.setenv('WORLDLABS_API_KEY','private-test-key')
    calls=[]
    def respond(request):
        calls.append(request)
        if request.method=='POST':return httpx.Response(200,json={'operation_id':'test-operation','done':False})
        return httpx.Response(429,json={'detail':'private-test-key must not escape'})
    adapter=WorldLabs(httpx.MockTransport(respond))
    result=adapter.generate('A real scene','Scene',7,'marble-1.0-draft')
    assert result['operation_id']=='test-operation'
    assert str(calls[0].url)=='https://api.worldlabs.ai/marble/v1/worlds:generate'
    assert calls[0].headers['WLT-Api-Key']=='private-test-key'
    payload=json.loads(calls[0].content)
    assert payload['world_prompt']=={'type':'text','text_prompt':'A real scene'} and payload['permission']=={'public':False}
    with pytest.raises(ProviderError) as failure:adapter.operation('test-operation')
    assert 'private-test-key' not in str(failure.value) and 'rate limited' in str(failure.value)
    with pytest.raises(ProviderError):adapter.world('../private')


def test_openai_validates_structured_output_and_rejects_refusal(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','private-test-openai-key')
    spec=EnvironmentSpec(name='Valid scene',description='A bounded test cell').model_dump()
    def response(request):
        body=json.loads(request.content)
        assert body['text']['format']['strict'] and not body['store']
        assert body['text']['format']['schema']['additionalProperties'] is False
        return httpx.Response(200,json={'status':'completed','id':'unit-response','output':[{'content':[{'type':'output_text','text':json.dumps(spec)}]}]})
    scene,provenance=OpenAIInterpreter(httpx.MockTransport(response)).environment('A valid scene')
    assert scene.name=='Valid scene' and provenance['response_id']=='unit-response'
    refusal=OpenAIInterpreter(httpx.MockTransport(lambda _:httpx.Response(200,json={'status':'completed','output':[{'content':[{'type':'refusal'}]}]})))
    with pytest.raises(ProviderError):refusal.environment('A refused scene')


def test_generation_missing_keys_is_honest(tmp_path,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False);monkeypatch.delenv('WORLDLABS_API_KEY',raising=False)
    with TestClient(create_app(tmp_path/'missing.sqlite')) as client:
        capabilities=client.get('/v1/workspace/capabilities').json()
        assert not capabilities['openai_configured'] and not capabilities['worldlabs_configured']
        response=client.post('/v1/workspace/generations',headers=OWNER|{'Idempotency-Key':'missing-key'},json={'prompt':'A manufacturing environment'})
        assert response.status_code==503 and 'not configured' in response.json()['detail']
        assert client.get('/v1/workspace/generations',headers=OWNER).json()==[]


@pytest.mark.parametrize('url',['http://localhost/file','https://127.0.0.1/file','https://evil.example/file','https://api.worldlabs.ai@127.0.0.1/file'])
def test_provider_asset_fetch_does_not_accept_arbitrary_urls(url):
    with pytest.raises(ProviderError):asset_url(url)


def test_provider_preview_reduction_preserves_full_collision_bounds():
    import struct
    from vivacity.imports import gltf_preview
    # An extreme vertex on a discarded triangle must still bound the solid proxy.
    positions=np.zeros((75006,3),dtype='<f4');positions[-1]=[9,4,2]
    raw=positions.tobytes()
    doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(raw)}],
         'bufferViews':[{'buffer':0,'byteLength':len(raw)}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':len(positions),'type':'VEC3'}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],
         'nodes':[{'mesh':0}],'scenes':[{'nodes':[0]}]}
    metadata=json.dumps(doc).encode();metadata+=b' '*((-len(metadata))%4)
    content=struct.pack('<4sII',b'glTF',2,28+len(metadata)+len(raw))+struct.pack('<II',len(metadata),0x4e4f534a)+metadata+struct.pack('<II',len(raw),0x004e4942)+raw
    preview,_=gltf_preview(content,'.glb',{},reduce_preview=True)
    assert preview['triangle_count']<=25000
    assert all(type(index) is int for index in preview['indices'])
    assert len(preview['indices'])==preview['triangle_count']*3
    assert preview['source_bounds_m']==[[0,0,0],[9,4,2]]


def test_machine_closure_respects_timeout_and_cancellation():
    from vivacity.scene import finish_task
    backend=PickPlaceBackend()
    world=backend.create_world(RoboticsConfig(task='pick_place',physical_operation='machine_tending',obstacle_enabled=False).model_dump(),7)
    steps,failure,_=finish_task(world,{'max_simulation_seconds':.001},[],backend,0,time.perf_counter(),0)
    assert steps==1 and failure=='timeout'
    steps,failure,_=finish_task(world,{'max_simulation_seconds':40,'checkpoint':lambda:False},[],backend,0,time.perf_counter(),0)
    assert steps==0 and failure=='cancelled'


@pytest.mark.parametrize('arm',['panda','ur5e','dual_arm'])
def test_native_object_environment_collision_is_measured(arm,monkeypatch):
    from vivacity.native_pick_place import NativePickup
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS','1')
    backend=PickPlaceBackend() if arm=='panda' else ModelPickupBackend(arm)
    config=RoboticsConfig(task='pick_place',robot_model=arm,obstacle_enabled=False,
        scene_geometries=[{'name':'collision_fixture','type':'box','position':[-1.4,0,.35] if arm=='dual_arm' else [.5,-.15,.03],'size':[.08,.08,.08] if arm=='dual_arm' else [.06,.06,.02]}]).model_dump()
    world=backend.create_world(config,7);start=world.data.qpos[:backend.arm_dof].tolist()
    stage={'phase':'approach','start':start,'goal':start,'duration_s':.02,'dwell_s':.02,'gripper':255}
    action={'kind':'pick_place','stages':[stage.copy() for _ in range(8)],'planning_feasible':True}
    result,evaluation,_=NativePickup(backend,backend.snapshot(world)).simulate(action,{'max_simulation_seconds':40})
    assert result['simulation_steps']>0 and evaluation['status']=='collision_failure'
    assert result['contact_violations']


def test_native_live_pacing_respects_speed_and_preserves_parent(monkeypatch):
    from vivacity.native_pick_place import NativePickup
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS','1')
    backend=PickPlaceBackend();world=backend.create_world(RoboticsConfig(task='pick_place',obstacle_enabled=False).model_dump(),7)
    start=world.data.qpos[:backend.arm_dof].tolist()
    stage={'phase':'approach','start':start,'goal':start,'duration_s':.02,'dwell_s':.02,'gripper':255}
    action={'kind':'pick_place','stages':[stage.copy() for _ in range(8)],'planning_feasible':True}
    engine=NativePickup(backend,backend.snapshot(world))
    assert engine.template.model is world.model and engine.template.data is not world.data
    began=time.perf_counter()
    result,_,final=engine.simulate(action,{'max_simulation_seconds':10,'realtime':True,'realtime_speed':.25})
    assert result['simulation_steps']==160 and time.perf_counter()-began>=1.2
    assert final['integration_state'][0]==pytest.approx(.32)
    assert world.data.time==0


def test_provider_reported_cost_survives_retrieval_failure(runtime,monkeypatch):
    from vivacity.workspace import WorkspaceService,owner
    import uuid
    service=WorkspaceService(runtime);now=time.time();token=OWNER['X-Workspace-Token']
    job={'id':str(uuid.uuid4()),'_owner':owner(token),'_token':token,'provider':'worldlabs',
        'status':'generating','prompt':'A physical workshop','seed':7,'model':'marble-1.0-draft',
        'operation_id':'existing-operation','created_unix_s':now,'updated_unix_s':now,
        'events':[],'interpretation':EnvironmentSpec(name='Cell',description='A workshop').model_dump()}
    monkeypatch.setattr(service.worldlabs,'operation',lambda _: {'done':True,'response':{'world_id':'existing-world'},'cost':{'total_credits':230}})
    monkeypatch.setattr(service.worldlabs,'world',lambda _: {'assets':{}})
    try:
        service._put('generation',owner(token),job);service._resume(job)
        record=service.generation(job['id'],token)
        assert record['status']=='failed' and record['provider_cost_credits']==230
        assert '_token' not in record
    finally:service.close()


@pytest.mark.parametrize('arm',['panda',*MODELS])
def test_real_models_controller_forks_and_measured_pickup(arm,monkeypatch):
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS','1')
    backend=PickPlaceBackend() if arm=='panda' else ModelPickupBackend(arm)
    world=backend.create_world(RoboticsConfig(task='pick_place',robot_model=arm,obstacle_enabled=False).model_dump(),7)
    snapshot=backend.snapshot(world);branch=backend.fork(snapshot)
    branch.data.ctrl[0]+=.02
    assert world.data.ctrl[0]!=branch.data.ctrl[0]
    backend.restore(branch,snapshot)
    assert np.array_equal(backend.snapshot(branch)['integration_state'],snapshot['integration_state'])
    actions,_=backend.candidates(world,2,500)
    outcomes=[]
    for action in actions:
        candidate=backend.fork(snapshot);backend.apply_action(candidate,action)
        result=backend.simulate(candidate,{'max_simulation_seconds':40})
        evaluation=backend.evaluate(candidate,result);outcomes.append(evaluation)
        assert result['trace'][0]['time']==0
        if evaluation['success']:
            assert result['simulation_steps']>0 and evaluation['grasp_established'] and evaluation['table_supported']
            assert evaluation['goal_error_m']<.025
    assert any(e['success'] for e in outcomes),outcomes
    assert backend.snapshot(world)['integration_state']==snapshot['integration_state']


@pytest.mark.parametrize('operation',['sorting','assembly','stacking','insertion','machine_tending'])
def test_operations_have_real_goals_and_traces(runtime,operation,monkeypatch):
    from vivacity.workspace import WorkspaceService
    from vivacity.workspace_schemas import ExperimentConfiguration
    from vivacity.schemas import ExperimentRequest
    workspace=WorkspaceService(runtime)
    try:
        request=workspace.resolve(ExperimentConfiguration(name='Goal test',environment_id='desktop',operation_id=operation),OWNER['X-Workspace-Token']).world
        world=runtime.create_world(request)
        experiment=runtime.wait(runtime.submit(world['id'],ExperimentRequest(candidates=3,max_simulation_seconds=40))['id'],timeout=180)
        branches=runtime.store.branches(experiment['id'])
        assert any(b['evaluation']['success'] for b in branches),[b['evaluation'] for b in branches]
        for b in branches:
            if b['evaluation']['success']:
                assert b['performance']['simulation_steps']>0
                assert b['evaluation']['milestone']!='physical_pick_and_place'
        replay=runtime.replay(experiment['id'])
        assert replay['branches'][0]['frames']==branches[0]['trace']
    finally:workspace.close()


@pytest.mark.parametrize('scene',['warehouse','factory','robotics_lab','automotive','logistics','research','packaging','cleanroom','workshop','desktop','cluttered_cell','quality_control'])
def test_each_prebuilt_scene_has_actual_collisions_and_can_execute(scene,runtime):
    from vivacity.workspace import WorkspaceService
    from vivacity.workspace_schemas import ExperimentConfiguration
    from vivacity.schemas import ExperimentRequest
    workspace=WorkspaceService(runtime)
    try:
        world=runtime.create_world(workspace.resolve(ExperimentConfiguration(name='Scene test',environment_id=scene),OWNER['X-Workspace-Token']).world)
        observation=runtime.observe(world['id'])['observation']
        assert observation['environment_geometries']
        assert observation['environment_provenance']['id']==scene
        experiment=runtime.wait(runtime.submit(world['id'],ExperimentRequest(candidates=2,max_simulation_seconds=40))['id'],timeout=180)
        assert experiment['selected_branch_id'],experiment
        assert any(b['performance']['simulation_steps']>0 for b in runtime.store.branches(experiment['id']))
    finally:workspace.close()
