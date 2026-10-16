import gzip
import json,struct
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.workspace_schemas import EnvironmentSpec

OWNER={'X-Workspace-Token':'visual-owner-capability-123456789000'}
OTHER={'X-Workspace-Token':'visual-other-capability-123456789000'}

def test_visual_bytes_are_owned_cached_and_not_provider_urls(tmp_path,monkeypatch):
    calls=[]
    content=gzip.compress(b'NGSPvisual-test')
    def download(url):calls.append(url);return content
    monkeypatch.setattr('vivacity.workspace.download_asset',download)
    with TestClient(create_app(tmp_path/'visual.sqlite')) as client:
        svc=client.app.state.workspace
        spec=EnvironmentSpec(name='Real provider world',description='Colored splats with separate collisions')
        record=svc.save_world(spec,OWNER['X-Workspace-Token'],'worldlabs',appearance={'format':'spz','semantics':None})
        record['_visual_url']='https://storage.googleapis.com/provider/private.spz?signed=not-public'
        from vivacity.workspace import owner
        svc._put('world',owner(OWNER['X-Workspace-Token']),record)
        identifier=record['id'];url='/v1/workspace/worlds/'+identifier+'/appearance'
        assert client.get(url,headers=OTHER).status_code==404
        public=client.get('/v1/workspace/worlds/'+identifier,headers=OWNER)
        assert '_visual_url' not in public.text and 'signed=' not in public.text
        for _ in range(2):
            response=client.get(url,headers=OWNER)
            assert response.status_code==200 and response.content==content
            assert response.headers['cache-control'].startswith('private')
        assert len(calls)==1
        copy=client.post('/v1/workspace/worlds',headers=OWNER,json={'source_id':identifier})
        assert copy.status_code==201 and copy.json()['appearance']['format']=='spz'
        assert client.get('/v1/workspace/worlds/'+copy.json()['id']+'/appearance',headers=OWNER).content==content

def test_failed_visual_output_is_an_error_and_not_a_primitive_substitute(tmp_path,monkeypatch):
    monkeypatch.setattr('vivacity.workspace.download_asset',lambda url:b'not spz')
    with TestClient(create_app(tmp_path/'visual.sqlite')) as client:
        svc=client.app.state.workspace
        record=svc.save_world(EnvironmentSpec(name='Failed asset',description='Provider bytes fail'),OWNER['X-Workspace-Token'],'worldlabs',appearance={'format':'spz'})
        record['_visual_url']='https://storage.googleapis.com/provider/bad.spz'
        from vivacity.workspace import owner
        svc._put('world',owner(OWNER['X-Workspace-Token']),record)
        response=client.get('/v1/workspace/worlds/'+record['id']+'/appearance',headers=OWNER)
        assert response.status_code==502 and 'not a compressed SPZ' in response.text
        assert client.get('/v1/workspace/worlds/desktop/appearance',headers=OWNER).status_code==422


def test_embedded_glb_material_bytes_survive_mapping_and_download(tmp_path):
    # A real GLB triangle with an embedded material, preserved byte-for-byte.
    binary=struct.pack('<9f',0,0,0,1,0,0,0,1,0)
    document={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(binary)}],
        'bufferViews':[{'buffer':0,'byteLength':len(binary)}],
        'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3'}],
        'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[.15,.4,.7,1],'roughnessFactor':.35}}],
        'meshes':[{'primitives':[{'attributes':{'POSITION':0},'material':0}]}],
        'nodes':[{'mesh':0}],'scenes':[{'nodes':[0]}],'scene':0}
    encoded=json.dumps(document).encode();encoded+=b' '*((-len(encoded))%4)
    content=struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    with TestClient(create_app(tmp_path/'visual.sqlite')) as client:
        imported=client.post('/v1/workspace/imports?filename=material.glb',headers=OWNER,content=content)
        assert imported.status_code==201,imported.text
        world=client.post('/v1/workspace/imports/'+imported.json()['id']+'/map',headers=OWNER,json={'name':'Original material'})
        assert world.status_code==201,world.text
        assert world.json()['appearance']['format']=='glb'
        response=client.get('/v1/workspace/worlds/'+world.json()['id']+'/appearance',headers=OWNER)
        assert response.status_code==200 and response.content==content
        assert response.headers['content-type']=='model/gltf-binary'
