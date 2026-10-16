import csv
import io
import json
import zipfile
from pypdf import PdfReader
from fastapi.testclient import TestClient
from vivacity.api import create_app
from test_factory_api import OWNER,OTHER,wait

def test_saved_run_pdf_and_zip_agree_with_actual_physics(tmp_path):
    with TestClient(create_app(tmp_path/'factory.sqlite3')) as c:
        cell=c.post('/v1/factory/cells',headers=OWNER,json={'carton_count':1,'carton_start_y_m':-.4,'realtime_speed':8,'name':'Report <escaped> & provenance'}).json()
        run=c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=OWNER,json={'mode':'production'}).json()
        base='/v1/factory/reports/run/'+run['id']
        assert c.get(base,headers=OWNER).status_code==429
        result=wait(c,run['id'],{'completed','failed'})
        assert result['status']=='completed',result
        assert c.get(base,headers=OTHER).status_code==404
        response=c.get(base,headers=OWNER)
        assert response.status_code==200,response.text[:100]
        reader=PdfReader(io.BytesIO(response.content));text='\n'.join(page.extract_text() for page in reader.pages)
        assert 5<=len(reader.pages)<=9
        assert all(len(page.extract_text())>100 for page in reader.pages)
        assert '1 of 1 configured cartons' in text and run['id'] in text
        assert 'Report <escaped> & provenance' in text
        assert 'electrical consumption' in text and 'Gripper contact normal force' in text
        response=c.get(base+'?format=zip',headers=OWNER)
        assert response.status_code==200
        z=zipfile.ZipFile(io.BytesIO(response.content));saved=json.loads(z.read('runs/'+run['id']+'.json'))
        actual=c.get('/v1/factory/runs/'+run['id']+'/record',headers=OWNER).json()
        assert saved==actual
        rows=list(csv.DictReader(io.StringIO(z.read('runs/'+run['id']+'.csv').decode())))
        assert len(rows)==len(actual['trace'])
        for row,frame in zip(rows,actual['trace']):
            assert float(row['time_s'])==frame['time']
            assert float(row['power_w'])==frame['measurements']['actuator_power_w']
        assert json.loads(z.read('definition.json'))['configuration']==cell['config']
        assert PdfReader(io.BytesIO(z.read('report.pdf'))).pages[0].extract_text()==reader.pages[0].extract_text()
