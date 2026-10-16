import base64
import gzip
import json
import struct
import time
import uuid
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.providers import WorldLabs, ProviderError, OpenAIInterpreter
from vivacity.spatial import capture_metadata, geometry_evidence
from vivacity.workspace import owner
from vivacity.workspace_schemas import GenerationRequest, EnvironmentSpec, MeasurementRequest
from vivacity.schemas import RoboticsConfig, SessionRequest, VariationSettings
from vivacity.variation import conditions, report

OWNER={'X-Workspace-Token':'spatial-owner-capability-123456789000'}
OTHER={'X-Workspace-Token':'spatial-other-capability-123456789000'}
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQioAAAAASUVORK5CYII=')


def glb():
    raw=struct.pack('<9f',0,0,0,1,0,0,0,1,0)
    doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(raw)}],
         'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':len(raw)}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3'}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],
         'nodes':[{'mesh':0}],'scenes':[{'nodes':[0]}],'scene':0}
    encoded=json.dumps(doc).encode();encoded+=b' '*((-len(encoded))%4)
    return struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(raw))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(raw),0x004e4942)+raw


def test_capture_validation_ownership_persistence_and_no_public_bytes(tmp_path):
    database=tmp_path/'spatial.sqlite'
    with TestClient(create_app(database)) as client:
        r=client.post('/v1/workspace/captures?filename=capture.png',headers=OWNER,content=PNG)
        assert r.status_code==201,r.text
        captured=r.json();assert captured['dimensions_px']==[1,1] and captured['uploaded_bytes']==len(PNG)
        assert client.get('/v1/workspace/captures',headers=OTHER).json()==[]
        assert client.get('/v1/workspace/captures/'+captured['id']).status_code==404
        assert client.post('/v1/workspace/captures?filename=bad.png',headers=OWNER,content=b'bad').status_code==422
        assert client.post('/v1/workspace/captures?filename=../bad.png',headers=OWNER,content=PNG).status_code==422
        svc=client.app.state.workspace
        with pytest.raises(KeyError):svc.capture_path(captured['id'],OTHER['X-Workspace-Token'])
        assert svc.capture_path(captured['id'],OWNER['X-Workspace-Token'])[1].read_bytes()==PNG
    with TestClient(create_app(database)) as client:
        assert client.get('/v1/workspace/captures',headers=OWNER).json()[0]['sha256']==captured['sha256']


@pytest.mark.parametrize('patch',[
 {'input_type':'image'},{'input_type':'video'},{'input_type':'multi-image','inputs':[{'capture_id':str(uuid.uuid4())}]},
 {'input_type':'text','inputs':[{'capture_id':str(uuid.uuid4())}]},
 {'input_type':'image','provider':'openai','inputs':[{'capture_id':str(uuid.uuid4())}]},
 {'input_type':'image','inputs':[{'capture_id':'../secret'}]},
])
def test_generation_input_shape_rejected(patch):
    with pytest.raises(ValueError):GenerationRequest(prompt='A physical world',**patch)


@pytest.mark.parametrize('filename,data',[
 ('wrong.jpg',PNG),('image.png',PNG[:20]),('film.mp4',b'bad'),
 ('image.png',PNG[:16]+struct.pack('>II',100000,100000)+PNG[24:]),
])
def test_capture_content_limits(filename,data):
    with pytest.raises(ValueError):capture_metadata(filename,data)


def test_signed_media_upload_uses_documented_contract_no_credentials_on_storage(monkeypatch):
    monkeypatch.setenv('WORLDLABS_API_KEY','private-test-value')
    monkeypatch.setattr('vivacity.providers.asset_url',lambda value:value)
    calls=[]
    def respond(request):
        calls.append(request)
        if request.url.host=='api.worldlabs.ai':
            assert request.headers['WLT-Api-Key']=='private-test-value'
            assert json.loads(request.content)=={'file_name':'capture.png','kind':'image','extension':'png'}
            return httpx.Response(200,json={'media_asset':{'media_asset_id':'real-media-id'},'upload_info':{
                'upload_url':'https://storage.googleapis.com/signed?private=1','upload_method':'PUT','required_headers':{'x-goog-content-length-range':'0,16777216'}}})
        assert 'wlt-api-key' not in request.headers and 'authorization' not in request.headers and request.content==PNG
        return httpx.Response(200)
    adapter=WorldLabs(httpx.MockTransport(respond))
    assert adapter.upload_capture('capture.png','image','png',PNG)=='real-media-id' and len(calls)==2


def test_generation_post_is_never_retried_and_error_body_redacted(monkeypatch):
    monkeypatch.setenv('WORLDLABS_API_KEY','private-test-value');calls=[]
    def respond(r):calls.append(r);return httpx.Response(503,json={'secret':'private-test-value'})
    with pytest.raises(ProviderError,match='HTTP 503') as error:WorldLabs(httpx.MockTransport(respond)).generate('A room','Room',7,'marble-1.1')
    assert len(calls)==1 and 'private-test-value' not in str(error.value)


@pytest.mark.parametrize('corrected',[True,False])
def test_openai_physical_validation_has_one_bounded_correction(monkeypatch,corrected):
    monkeypatch.setenv('OPENAI_API_KEY','private-test-value');calls=[]
    good=EnvironmentSpec(name='Room',description='A bounded scene').model_dump()
    bad=good|{'geometries':[{'name':'invalid','type':'box','position':[0,0,0],'size':[1,1,0],'rgba':[1,1,1,1],'friction':.8}]}
    def respond(request):
        calls.append(json.loads(request.content))
        body=good if corrected and len(calls)==2 else bad
        return httpx.Response(200,json={'status':'completed','id':'response-'+str(len(calls)),'usage':{'input_tokens':10},
            'output':[{'content':[{'type':'output_text','text':json.dumps(body)}]}]})
    interpreter=OpenAIInterpreter(httpx.MockTransport(respond))
    if corrected:
        spec,provenance=interpreter.environment('A bounded room');assert spec.name=='Room' and provenance['attempts']==2 and len(provenance['attempt_usage'])==2
    else:
        with pytest.raises(ProviderError,match='after one correction'):interpreter.environment('A bounded room')
    assert len(calls)==2 and 'Validator reported' in calls[1]['input'][-1]['content']


@pytest.mark.parametrize('kind,count',[('image',1),('panorama',1),('video',1),('multi-image',2)])
def test_all_capture_modalities_use_actual_provider_schema(runtime,monkeypatch,kind,count):
    from vivacity.workspace import WorkspaceService
    from vivacity.workspace_schemas import CaptureReference
    from vivacity.spatial import capture_metadata as original
    monkeypatch.setenv('OPENAI_API_KEY','test');monkeypatch.setenv('WORLDLABS_API_KEY','test')
    # Unit transport fixture only: generation outputs are deliberately not successful.
    svc=WorkspaceService(runtime);received=[]
    monkeypatch.setattr(svc.interpreter,'environment',lambda _: (EnvironmentSpec(name='Room',description='A bounded test room'),{}))
    monkeypatch.setattr(svc.worldlabs,'upload_capture',lambda *args: 'media-'+str(len(received)))
    def generate(*args):received.append(args[-1]);return {'operation_id':'actual-operation'}
    monkeypatch.setattr(svc.worldlabs,'generate',generate)
    monkeypatch.setattr(svc,'_poll',lambda job:svc._stage(job,'failed','test stops after provider submission'))
    references=[]
    for i in range(count):
        data=struct.pack('>I4s8s',16,b'ftyp',b'isom0000') if kind=='video' else PNG
        record=svc.capture('capture.mp4' if kind=='video' else f'capture{i}.png',data,OWNER['X-Workspace-Token'])
        if kind=='panorama':
            record['dimensions_px']=[2,1];svc._put('capture',owner(OWNER['X-Workspace-Token']),record)
        references.append(CaptureReference(capture_id=record['id'],azimuth_deg=i*180))
    try:
        job=svc.generate(GenerationRequest(prompt='A room with a workbench',input_type=kind,inputs=references),OWNER['X-Workspace-Token'],str(uuid.uuid4()))
        deadline=time.monotonic()+3
        while svc.generation(job['id'],OWNER['X-Workspace-Token'])['status']!='failed' and time.monotonic()<deadline:time.sleep(.01)
        assert received
        value=received[0];assert value['type']==('image' if kind=='panorama' else kind)
        if kind=='multi-image':assert [i['azimuth'] for i in value['multi_image_prompt']]==[0,180]
        elif kind=='video':assert value['video_prompt']['source']=='media_asset'
        else:assert value['image_prompt']['source']=='media_asset' and value['is_pano']==(kind=='panorama')
    finally:svc.close()


def test_geometry_evidence_open_and_closed_and_sample_scope():
    tetra={'positions':[[0,0,0],[1,0,0],[0,1,0],[0,0,1]],'indices':[0,2,1,0,1,3,1,2,3,2,0,3]}
    closed=geometry_evidence(tetra)
    assert closed['watertight_preview'] and closed['inconsistent_winding_edges']==0
    opened=geometry_evidence(tetra|{'indices':tetra['indices'][:-3]},sampled=True)
    assert not opened['watertight_preview'] and opened['boundary_edges']==3 and not opened['source_mesh_fully_checked']
    assert opened['self_intersections']=='not checked' and opened['physical_properties']['mass']=='unknown'


def test_provider_schema_contains_actual_geometry_bounds():
    schema=EnvironmentSpec.model_json_schema()
    geometry=schema['$defs']['StaticGeometry']['properties']
    assert geometry['size']['items']['minimum']==.005 and geometry['size']['items']['maximum']==8
    assert geometry['position']['items']['minimum']==-8 and geometry['position']['items']['maximum']==8
    assert schema['properties']['dimensions_m']['items']['minimum']==1


def test_generated_collider_preserved_detail_cached_and_private_thumbnail(tmp_path,monkeypatch):
    monkeypatch.setattr('vivacity.workspace.download_asset',lambda url:PNG if 'thumbnail' in url else gzip.compress(b'NGSPtest'))
    with TestClient(create_app(tmp_path/'assets.sqlite')) as client:
        svc=client.app.state.workspace
        record=client.app.state.imports.create('collider.glb',glb(),reduce_preview=True)
        assert (client.app.state.imports.root/(record['id']+'.glb')).read_bytes()==glb()
        from vivacity.workspace_schemas import ImportMapping
        world=svc.map_import(record,client.app.state.imports.get(record['id'],preview=True),ImportMapping(name='Room'),OWNER['X-Workspace-Token'],'worldlabs')
        world.update(appearance={'format':'spz','qualities':['100k','500k']},_visual_url='https://storage.googleapis.com/500k.spz',
                     _visual_urls={'100k':'https://storage.googleapis.com/100k.spz','500k':'https://storage.googleapis.com/500k.spz'},
                     _thumbnail_url='https://storage.googleapis.com/thumbnail.png',thumbnail_available=True)
        svc._put('world',owner(OWNER['X-Workspace-Token']),world)
        base='/v1/workspace/worlds/'+world['id']
        assert client.get(base+'/geometry',headers=OWNER).content==glb()
        assert client.get(base+'/geometry',headers=OTHER).status_code==404
        assert client.get(base+'/thumbnail',headers=OWNER).content==PNG
        assert client.get(base+'/thumbnail',headers=OTHER).status_code==404
        assert client.get(base+'/appearance?quality=100k',headers=OWNER).status_code==200
        assert client.get(base+'/appearance?quality=full_res',headers=OWNER).status_code==422
        public=client.get(base,headers=OWNER);assert '_visual_urls' not in public.text and 'googleapis.com' not in public.text
        assert public.json()['representations']['geometry']['validation']['source_mesh_fully_checked'] is False
        copied=client.post('/v1/workspace/worlds',headers=OWNER,json={'source_id':world['id']}).json()
        assert client.get('/v1/workspace/worlds/'+copied['id']+'/appearance?quality=100k',headers=OWNER).status_code==200


def test_physical_conditions_are_seeded_valid_and_partitioned_before_execution():
    config=RoboticsConfig(task='pick_place',obstacle_enabled=False).model_dump()
    settings=VariationSettings(enabled=True).model_dump();original=json.dumps(config,sort_keys=True)
    result,partition=conditions(config,8,1,4,settings)
    repeated,_=conditions(config,8,1,4,settings)
    assert result==repeated and partition=='training' and json.dumps(config,sort_keys=True)==original
    assert result['cube_mass']!=config['cube_mass'] and result['cube_friction']!=config['cube_friction']
    assert conditions(config,10,3,4,settings)[1]=='held_out'
    assert conditions(config,7,0,4,settings)[0]==config
    assert result['object_material']=='custom' and RoboticsConfig.model_validate(result)
    with pytest.raises(ValueError):SessionRequest(backend='mujoco',config=config,max_cycles=2,variation={'enabled':True})


def test_robustness_rates_only_include_measured_completed_configurations():
    experiments=[];metadata=[]
    for i,success in enumerate((True,False,True)):
        experiment={'id':str(i),'world_id':str(i),'config':{'cube_mass':.06,'cube_friction':.2},'status':'completed','result':{'execution_evaluation':{'success':success,'status':'success' if success else 'dropped_object','goal_error_m':.01}},'selected_branch_id':'branch'}
        experiments.append((experiment,[]));metadata.append({'world_id':str(i),'partition':['baseline','training','held_out'][i],'seed':7+i,'configuration_sha256':str(i)})
    experiments.append(({'id':'pending','world_id':'pending','status':'running','result':{}},[]))
    value=report(experiments,metadata)
    assert value['partitions']['training']['success_rate']==0 and value['partitions']['held_out']['success_rate']==1
    assert len(value['failure_regions'])==1 and len(value['configurations'])==3 and value['hardware_validation']=='not performed'
    experiment=experiments[0][0]|{'id':'all-failed','selected_branch_id':None,'result':{}}
    measured=report([(experiment,[{'id':'failed','evaluation':{'success':False,'status':'dropped_object','goal_error_m':.4}}])],metadata)
    assert measured['configurations'][0]['success'] is False and measured['partitions']['baseline']['failures']==1
    assert measured['configurations'][0]['evaluation_source']=='failed validation branch; no feasible selection'


def test_measurement_schema_rejects_unordered_or_nonfinite_values():
    body={'experiment_id':'e','branch_id':'b','source_label':'Synthetic test','source_kind':'synthetic_reference','samples':[{'time_s':1,'position_m':[0,0,0]},{'time_s':0,'position_m':[0,0,0]}]}
    with pytest.raises(ValueError):MeasurementRequest.model_validate(body)
    body['samples'][1]['time_s']=2;body['samples'][1]['position_m'][0]=float('nan')
    with pytest.raises(ValueError):MeasurementRequest.model_validate(body)


def test_run_report_reads_persisted_configuration_not_public_projection(runtime,monkeypatch):
    from vivacity.workspace import WorkspaceService
    from vivacity.storage import encode
    svc=WorkspaceService(runtime)
    session={'experiments':['e'],'conditions':[{'world_id':'w','partition':'held_out','seed':9}]}
    experiment={'id':'e','world_id':'w','status':'completed','selected_branch_id':'b','result':{'execution_evaluation':{'success':True,'status':'success'}}}
    monkeypatch.setattr(runtime.supervisor,'get',lambda *args:session)
    monkeypatch.setattr(runtime,'get_experiment',lambda _:experiment)
    monkeypatch.setattr(runtime.store,'branches',lambda _:[])
    original=runtime.store.get
    monkeypatch.setattr(runtime.store,'get',lambda kind,identifier,*args: {'config':{'cube_mass':.08,'cube_friction':.3}} if kind=='experiments' else original(kind,identifier,*args))
    with runtime.store.connect() as db:
        db.execute('INSERT INTO configuration_runs VALUES(?,?,?,?)',('s',owner(OWNER['X-Workspace-Token']),'c',encode({'session_id':'s','configuration_id':'c','capability':'secret-test-token'})))
    try:
        result=svc.runs(OWNER['X-Workspace-Token'])
        assert result[0]['robustness']['partitions']['held_out']['success_rate']==1
        assert result[0]['robustness']['configurations'][0]['conditions']['mass_kg']==.08
        assert 'capability' not in result[0] and 'config' not in result[0]['experiments'][0]['experiment']
    finally:svc.close()
