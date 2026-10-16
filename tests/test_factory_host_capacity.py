"""Run this file inside Docker --memory=512m --memory-swap=512m."""
import time
from pathlib import Path
from fastapi.testclient import TestClient
from vivacity.api import create_app

def test_factory_camera_three_cartons_history_and_report_with_host_limit(tmp_path,monkeypatch):
    def memory(stage):
        status=Path('/proc/self/status')
        if status.exists():
            print(stage,[line for line in status.read_text().splitlines() if line.startswith(('VmRSS:','VmHWM:'))],flush=True)
        for name in ('memory.current','memory.peak','memory.events'):
            path=Path('/sys/fs/cgroup')/name
            if path.exists():print(name,path.read_text().strip(),flush=True)
    monkeypatch.setenv('VIVACITY_HEADLESS_GEOMETRY','1')
    headers={'X-Workspace-Token':'factory-host-memory-capability-0123456789'}
    with TestClient(create_app(tmp_path/'host.sqlite3')) as c:
        memory('factory app ready')
        cell=c.post('/v1/factory/cells',headers=headers,json={'realtime_speed':8}).json()
        memory('factory cell ready')
        camera=c.get('/v1/factory/cells/'+cell['id']+'/observation',headers=headers)
        assert camera.status_code==200,camera.text[:300]
        assert camera.json()['camera']['image_data_url'].startswith('data:image/png;base64,')
        memory('camera captured')
        run=c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=headers,json={'mode':'production'}).json()
        captured_during_run=False
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            row=c.get('/v1/factory/runs/'+run['id'],headers=headers).json()
            assert c.get('/health').status_code==200
            if row['status']=='running' and row['frame']['time']>60 and not captured_during_run:
                assert c.get('/v1/factory/cells/'+cell['id']+'/observation',headers=headers).status_code==200
                captured_during_run=True
                memory('camera during production')
            if row['status'] not in ('queued','running','paused'):break
            time.sleep(.3)
        assert row['status']=='completed' and row['metrics']['cartons_sorted']==3,row
        assert captured_during_run
        memory('three cartons delivered')
        assert c.get('/v1/factory/runs',headers=headers).status_code==200
        assert len(c.get('/v1/factory/runs/'+run['id']+'/samples?limit=50',headers=headers).json()['frames'])==50
        memory('history and replay queried')
        exported=c.get('/v1/factory/runs/'+run['id']+'/export',headers=headers)
        assert exported.status_code==200 and b'"integration_state"' in exported.content
        assert len(exported.content)>100000
        del exported
        memory('complete JSON exported')
        report=c.get('/v1/factory/reports/run/'+run['id'],headers=headers)
        assert report.status_code==200,report.text[:300]
        assert report.content.startswith(b'%PDF')
        memory('PDF prepared')
        archive=c.get('/v1/factory/reports/run/'+run['id']+'?format=zip',headers=headers)
        assert archive.status_code==200 and archive.content.startswith(b'PK')
        del archive
        memory('ZIP prepared')
        assert c.get('/v1/factory/cells/'+cell['id']+'/observation',headers=headers).status_code==200
        memory('final camera captured')
