import base64
import io
import json
import struct
import zipfile
import numpy as np
import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.imports import ImportService,MAX_UPLOAD


def triangle():
    raw=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='<f4').tobytes()
    doc={'asset':{'version':'2.0'},'buffers':[{'uri':'data:application/octet-stream;base64,'+base64.b64encode(raw).decode(),'byteLength':36}],'bufferViews':[{'buffer':0,'byteLength':36}],'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3'}],'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],'nodes':[{'mesh':0,'translation':[2,0,0]}],'scenes':[{'nodes':[0]}],'scene':0}
    return doc,raw


def glb():
    doc,raw=triangle();doc['buffers'][0].pop('uri');header=json.dumps(doc).encode();header+=b' '*(-len(header)%4)
    return struct.pack('<4sII',b'glTF',2,12+8+len(header)+8+len(raw))+struct.pack('<II',len(header),0x4E4F534A)+header+struct.pack('<II',len(raw),0x004E4942)+raw


def bundle(files):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return buffer.getvalue()


@pytest.mark.parametrize('extension,data',[('.gltf',lambda:json.dumps(triangle()[0]).encode()),('.glb',glb)])
def test_real_triangle_decode_transform_and_persistence(tmp_path,extension,data):
    service=ImportService(tmp_path);record=service.create('scene'+extension,data())
    assert record['status']=='visual_only' and record['physics_ready'] is False
    preview=service.get(record['id'],True)
    assert preview['positions']==[[2,0,0],[3,0,0],[2,1,0]]
    assert preview['indices']==[0,1,2] and preview['triangle_count']==1
    assert ImportService(tmp_path).get(record['id'])==record


def test_relative_bundle_and_staged_robot_descriptions(tmp_path):
    doc,raw=triangle();doc['buffers'][0]['uri']='mesh.bin'
    data=bundle({'manifest.json':json.dumps({'entrypoint':'assets/scene.gltf'}),'assets/scene.gltf':json.dumps(doc),'assets/mesh.bin':raw})
    service=ImportService(tmp_path);record=service.create('scene.zip',data)
    assert record['summary']['bundle_entries']==3 and service.get(record['id'],True)['vertex_count']==3
    for name,content in [('robot.xml',b'<mujoco><worldbody><body><joint type="hinge" range="-1 1"/><geom type="box" size=".1 .1 .1" mass="1"/></body></worldbody></mujoco>'),('robot.urdf',b'<robot name="r"><link name="base"/><link name="tool"/><joint name="slide" type="prismatic"><parent link="base"/><child link="tool"/><limit lower="0" upper="1" effort="2" velocity="1"/></joint></robot>')]:
        result=service.create(name,content)
        assert result['status']=='configuration_required' and not result['physics_ready'] and not result['preview_available']


@pytest.mark.parametrize('name,content',[
    ('fake.glb',b'not a model'),('fake.gltf',b'{}'),
    ('robot.xml',b'<!DOCTYPE mujoco [<!ENTITY x SYSTEM "file:///etc/passwd">]><mujoco>&x;</mujoco>'),
    ('robot.xml','<!DOCTYPE mujoco [<!ENTITY x "expansion">]><mujoco>&x;</mujoco>'.encode('utf-16')),
    ('robot.xml',b'<mujoco><include file="https://example.com/model.xml"/></mujoco>'),
    ('robot.xml',b'<mujoco><worldbody><geom type="box" size="nan 1 1"/></worldbody></mujoco>'),
    ('robot.xml',b'<mujoco><plugin plugin="native_code"/></mujoco>'),
    ('robot.urdf',b'<robot><joint type="unknown"/></robot>'),
    ('scene.zip',bundle({'../escape.xml':b'<mujoco/>'})),
    ('scene.zip',bundle({'manifest.json':'{}','bomb.bin':b'0'*(2*1024*1024)})),
    ('scene.zip',bundle({'C:/escape.xml':'<mujoco/>'})),
])
def test_rejects_malformed_unsafe_and_resource_bombs(tmp_path,name,content):
    with pytest.raises(ValueError):ImportService(tmp_path).create(name,content)
    assert list(tmp_path.iterdir())==[]


def test_gltf_external_refs_cycles_bounds_and_upload_limits(tmp_path):
    service=ImportService(tmp_path)
    doc,_=triangle();doc['buffers'][0]['uri']='https://attacker.invalid/mesh.bin'
    with pytest.raises(ValueError):service.create('scene.gltf',json.dumps(doc).encode())
    doc,_=triangle();doc['nodes'][0]['children']=[0]
    with pytest.raises(ValueError):service.create('scene.gltf',json.dumps(doc).encode())
    doc,_=triangle();doc['accessors'][0]['count']=100001
    with pytest.raises(ValueError):service.create('scene.gltf',json.dumps(doc).encode())
    with pytest.raises(ValueError):service.create('scene.glb',b'x'*(MAX_UPLOAD+1))
    with pytest.raises(ValueError):service.create('../scene.glb',glb())


def test_real_http_upload_preview_error_and_restart(tmp_path):
    database=tmp_path/'demo.sqlite3'
    with TestClient(create_app(database)) as client:
        response=client.post('/v1/imports?filename=scene.glb',content=glb(),headers={'Content-Type':'application/octet-stream'})
        assert response.status_code==201,response.text
        record=response.json();preview=client.get(f'/v1/imports/{record["id"]}/preview')
        assert preview.status_code==200 and preview.json()['positions'][0]==[2,0,0]
        assert client.post('/v1/imports?filename=bad.glb',content=b'broken').status_code==422
        assert client.get('/v1/imports/missing').status_code==404
    with TestClient(create_app(database)) as client:assert client.get(f'/v1/imports/{record["id"]}').json()==record
