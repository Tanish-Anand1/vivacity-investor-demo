from fastapi.testclient import TestClient
from vivacity.api import create_app
from test_factory_api import OWNER,OTHER,wait

def test_immutable_project_versions_conflicts_and_owned_results(tmp_path):
    path=tmp_path/'factory.sqlite3'
    with TestClient(create_app(path)) as c:
        url='/v1/factory/projects'
        assert c.post(url,headers=OWNER,json={'name':'','team_label':'Lab','creator_label':'Engineer'}).status_code==422
        project=c.post(url,headers=OWNER,json={'name':'Payload study','team_label':'Research team','creator_label':'Engineer A'}).json()
        cell=c.post('/v1/factory/cells',headers=OWNER,json={'carton_count':1,'carton_start_y_m':-.4,'realtime_speed':8}).json()
        base=url+'/'+project['id'];version={'expected_revision':1,'cell_id':cell['id'],'creator_label':'Engineer A','note':'Baseline'}
        assert c.post(base+'/versions',headers=OTHER,json=version).status_code==404
        first=c.post(base+'/versions',headers=OWNER,json=version).json()
        assert first['revision']==2
        assert c.post(base+'/versions',headers=OWNER,json=version).status_code==409
        cell2=c.post('/v1/factory/cells',headers=OWNER,json=cell['config']|{'carton_mass_kg':.09}).json()
        second=c.post(base+'/versions',headers=OWNER,json=version|{'expected_revision':2,'cell_id':cell2['id'],'creator_label':'Engineer B','note':'Payload change'}).json()
        assert second['versions'][0]==first['versions'][0] and second['revision']==3
        assert second['versions'][1]['definition']['configuration']['carton_mass_kg']==.09
        run=c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=OWNER,json={'mode':'conveyor','creator_label':'Engineer A'}).json()
        wait(c,run['id'],{'completed'})
        attached=c.post(base+'/attachments',headers=OWNER,json={'expected_revision':3,'kind':'run','record_id':run['id'],'added_by_label':'Engineer B'}).json()
        assert attached['attachments'][0]['summary']['creator_label']=='Engineer A'
        assert attached['attachments'][0]['added_by_label']=='Engineer B'
        from pypdf import PdfReader
        import io
        report=c.get('/v1/factory/reports/run/'+run['id']+'?project_id='+project['id'],headers=OWNER)
        assert report.status_code==200,report.text[:100]
        text=PdfReader(io.BytesIO(report.content)).pages[0].extract_text()
        assert 'Payload study / Research team' in text and 'Engineer A' in text
        assert c.get(base,headers=OTHER).status_code==404
        assert c.get(url,headers=OTHER).json()==[]
        foreign=c.post('/v1/factory/projects',headers=OTHER,json={'name':'Other','team_label':'Other','creator_label':'Other'}).json()
        assert c.post(url+'/'+foreign['id']+'/attachments',headers=OTHER,json={'expected_revision':1,'kind':'run','record_id':run['id'],'added_by_label':'Other'}).status_code==404
    with TestClient(create_app(path)) as c:assert c.get(base,headers=OWNER).json()==attached
