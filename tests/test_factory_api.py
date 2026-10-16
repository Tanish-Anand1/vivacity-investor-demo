import time
from fastapi.testclient import TestClient
from vivacity.api import create_app

OWNER={'X-Workspace-Token':'factory-owner-capability-123456789000'}
OTHER={'X-Workspace-Token':'factory-other-capability-123456789000'}

def wait(client,identifier,statuses):
    # This is a functional physics test, not a 20-second hardware benchmark.
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        row=client.get('/v1/factory/runs/'+identifier,headers=OWNER).json()
        if row['status'] in statuses:return row
        time.sleep(.03)
    raise AssertionError({k:row.get(k) for k in ('id','status','phase','error','metrics')})

def test_transport_controls_ownership_and_persistence(tmp_path):
    path=tmp_path/'factory.sqlite3'
    with TestClient(create_app(path)) as c:
        assert c.post('/v1/factory/cells',json={}).status_code==422
        assert c.post('/v1/factory/cells',headers=OWNER,json={'conveyor_speed_m_s':1}).status_code==422
        cell=c.post('/v1/factory/cells',headers=OWNER,json={'realtime_speed':8,'carton_count':1}).json()
        from vivacity.factory_schemas import FactoryCellResponse,FactoryRunResponse,FactorySamplesResponse
        FactoryCellResponse.model_validate(cell)
        assert cell['frame']['time']==0
        assert c.get('/v1/factory/cells/'+cell['id'],headers=OTHER).status_code==404
        response=c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=OWNER,json={})
        assert response.status_code==202
        identifier=response.json()['id'];control='/v1/factory/runs/'+identifier+'/control'
        assert c.post(control,headers=OTHER,json={'action':'stop'}).status_code==404
        assert c.post(control,headers=OWNER,json={'action':'pause'}).status_code==200
        paused=wait(c,identifier,{'paused'})
        time.sleep(.08)
        assert c.get('/v1/factory/runs/'+identifier,headers=OWNER).json()['frame']['time']==paused['frame']['time']
        c.post(control,headers=OWNER,json={'action':'resume'})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            current=c.get('/v1/factory/runs/'+identifier,headers=OWNER).json()
            if current['frame']['time']>5.25:break
            time.sleep(.03)
        c.post(control,headers=OWNER,json={'action':'pause'})
        wait(c,identifier,{'paused'})
        live_record=c.get('/v1/factory/runs/'+identifier+'/record',headers=OWNER).json()
        assert len(live_record['trace'])>100
        crossing=c.get('/v1/factory/runs/'+identifier+'/samples?after=89&limit=30',headers=OWNER).json()
        assert crossing['frames']==live_record['trace'][90:120]
        c.post(control,headers=OWNER,json={'action':'resume'})
        row=wait(c,identifier,{'completed','failed'})
        assert row['status']=='completed',row
        FactoryRunResponse.model_validate(row)
        assert row['metrics']['station_arrivals']==1
        record=c.get('/v1/factory/runs/'+identifier+'/record',headers=OWNER).json()
        times=[f['time'] for f in record['trace']]
        assert times==sorted(set(times)) and len(times)>10
        assert record['initial_state']!=record['final_state']
        assert record['events'][-1]['kind']=='station_arrival'
        assert c.get('/v1/factory/runs/'+identifier+'/samples',headers=OTHER).status_code==404
        assert c.get('/v1/factory/runs/'+identifier+'/samples?limit=1001',headers=OWNER).status_code==422
        page=c.get('/v1/factory/runs/'+identifier+'/samples?limit=10',headers=OWNER).json()
        next_page=c.get('/v1/factory/runs/'+identifier+'/samples?after=9&limit=10',headers=OWNER).json()
        FactorySamplesResponse.model_validate(page)
        assert page['frames']+next_page['frames']==record['trace'][:20]
        assert page['next_index']==9 and next_page['next_index']==19
        # The durable metadata stays small; full HTTP replay remains lossless.
        import json
        with c.app.state.runtime.store.connect() as db:
            stored=json.loads(db.execute('SELECT payload FROM library_items WHERE id=?',(identifier,)).fetchone()[0])
            assert stored['trace']==[] and stored['trace_storage']=='sqlite_pages/1.0'
            assert db.execute('SELECT count(*) FROM factory_samples WHERE run_id=?',(identifier,)).fetchone()[0]==len(times)
        assert c.get('/v1/factory/runs/'+identifier+'/export',headers=OWNER).json()['record']==record
    with TestClient(create_app(path)) as c:
        assert c.get('/v1/factory/runs/'+identifier+'/record',headers=OWNER).json()==record

def test_emergency_stop_and_fresh_cell_reset(tmp_path):
    with TestClient(create_app(tmp_path/'factory.sqlite3')) as c:
        cell=c.post('/v1/factory/cells',headers=OWNER,json={}).json()
        run=c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=OWNER,json={}).json()
        c.post('/v1/factory/runs/'+run['id']+'/control',headers=OWNER,json={'action':'emergency_stop'})
        row=wait(c,run['id'],{'emergency_stopped'})
        time.sleep(.06)
        assert c.get('/v1/factory/runs/'+run['id'],headers=OWNER).json()['frame']['time']==row['frame']['time']
        reset=c.post('/v1/factory/cells',headers=OWNER,json=cell['config']).json()
        assert reset['initial_state']==cell['initial_state'] and reset['frame']['time']==0


def test_abandoned_pause_releases_worker_but_active_client_keeps_lease(tmp_path):
    with TestClient(create_app(tmp_path/'factory.sqlite3')) as c:
        c.app.state.factory.pause_lease_seconds=.3
        cell=c.post('/v1/factory/cells',headers=OWNER,json={}).json()
        run=c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=OWNER,json={}).json()
        url='/v1/factory/runs/'+run['id']
        c.post(url+'/control',headers=OWNER,json={'action':'pause'})
        paused=wait(c,run['id'],{'paused'})
        for _ in range(5):
            time.sleep(.1)
            row=c.get(url,headers=OWNER).json()
            assert row['status']=='paused' and row['frame']['time']==paused['frame']['time']
        time.sleep(.65)
        row=c.get(url,headers=OWNER).json()
        assert row['status']=='stopped' and 'without an active client' in row['error']
        assert c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=OWNER,json={}).status_code==202

def test_camera_http_ownership_and_changed_initial_conditions(tmp_path):
    with TestClient(create_app(tmp_path/'factory.sqlite3')) as c:
        cell=c.post('/v1/factory/cells',headers=OWNER,json={'carton_count':1,'carton_start_y_m':-.4}).json()
        url='/v1/factory/cells/'+cell['id']+'/observation'
        assert c.get(url,headers=OTHER).status_code==404
        response=c.get(url,headers=OWNER)
        assert response.status_code==200
        value=response.json();assert value['camera']['detections'][0]['detected']
        assert value['camera']['time_s']==value['ground_truth']['time']==0
        assert abs(value['camera']['detections'][0]['estimated_center_m'][1]+.4)<.01
        assert c.get('/v1/factory/cells/'+cell['id'],headers=OWNER).json()['initial_state']==cell['initial_state']

def test_production_records_exact_event_time_samples(tmp_path):
    with TestClient(create_app(tmp_path/'factory.sqlite3')) as c:
        cell=c.post('/v1/factory/cells',headers=OWNER,json={'carton_count':1,'carton_start_y_m':-.4,'realtime_speed':8}).json()
        response=c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=OWNER,json={'mode':'production'})
        assert response.status_code==202
        row=wait(c,response.json()['id'],{'completed','failed'})
        assert row['status']=='completed',row.get('error')
        record=c.get('/v1/factory/runs/'+row['id']+'/record',headers=OWNER).json()
        timestamps={f['time'] for f in record['trace']}
        assert all(event['time_s'] in timestamps for event in record['events'])
        assert row['metrics']['cartons_sorted']==1
