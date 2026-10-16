import copy
import numpy as np
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.factory import FactoryBackend
from vivacity.factory_exchange import digest,Exchange
from test_factory_api import OWNER,OTHER
from test_factory_benchmark import REQUEST

def test_configuration_roundtrip_reproduces_native_physics(tmp_path):
    with TestClient(create_app(tmp_path/'factory.sqlite3')) as c:
        cell=c.post('/v1/factory/cells',headers=OWNER,json={'carton_count':1}).json()
        url='/v1/factory/cells/'+cell['id']+'/export'
        assert c.get(url,headers=OTHER).status_code==404
        exported=c.get(url,headers=OWNER).json();Exchange.model_validate(exported)
        response=c.post('/v1/factory/imports',headers=OWNER,json=exported)
        assert response.status_code==201,response.text
        imported=response.json()['cell']
        assert imported['id']!=cell['id'] and imported['last_run_id'] is None
        assert imported['config']==cell['config'] and imported['initial_state']==cell['initial_state']
        b=FactoryBackend();a=b.fork(cell['initial_state']);d=b.fork(imported['initial_state'])
        for w in (a,d):b.apply_action(w,{'infeed':.09});b.step(w,300)
        np.testing.assert_array_equal(a.data.qpos,d.data.qpos)
        assert b.snapshot(a)==b.snapshot(d)
        assert not c.get('/v1/factory/runs',headers=OWNER).json()
        for field,value in [('schema_version','other/2'),('units',{'length':'cm'}),('unknown',1)]:
            bad=exported|{field:value}
            assert c.post('/v1/factory/imports',headers=OWNER,json=bad).status_code==422
        bad=copy.deepcopy(exported);bad['software']['engine_version']='0.0'
        bad['content_sha256']=digest({k:v for k,v in bad.items() if k!='content_sha256'})
        response=c.post('/v1/factory/imports',headers=OWNER,json=bad)
        assert response.status_code==422 and 'Incompatible' in response.text
        assert c.post('/v1/factory/imports',headers=OWNER,content=' '*262145).status_code==422
        bad=copy.deepcopy(exported);bad['configuration']['carton_mass_kg']=.12
        assert c.post('/v1/factory/imports',headers=OWNER,json=bad).status_code==422

def test_benchmark_import_preserves_definition_without_starting_worker(tmp_path):
    from vivacity.factory_benchmark import definition
    from vivacity.workspace import owner
    with TestClient(create_app(tmp_path/'factory.sqlite3')) as c:
        f=c.app.state.factory
        cell=f.create({'carton_count':1},OWNER['X-Workspace-Token'])
        benchmark={'id':'export-test','cell_id':cell['id'],'request':REQUEST,'definition':definition(cell['config'],REQUEST)}
        f.workspace._put('factory_benchmark',owner(OWNER['X-Workspace-Token']),benchmark)
        exported=c.get('/v1/factory/benchmarks/export-test/export',headers=OWNER).json()
        response=c.post('/v1/factory/imports',headers=OWNER,json=exported)
        assert response.status_code==201,response.text
        result=response.json()
        assert result['benchmark_request']['changes']['gripper_force_scale']==.005
        assert definition(result['cell']['config'],result['benchmark_request'])==benchmark['definition']
        assert not f.controls
def test_streamed_digest_keeps_the_canonical_archive_hash():
    import hashlib,json
    from vivacity.factory_exchange import digest
    value={'unicode':'Carton \u2192 bin','trace':[{'time':i*.002,'data':[None,True,1e-8,-0.0]} for i in range(1000)]}
    assert digest(value)==hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
