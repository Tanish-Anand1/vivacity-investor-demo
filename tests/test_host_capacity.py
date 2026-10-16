"""Production-image smoke used with a real 512 MiB Docker memory limit."""
from fastapi.testclient import TestClient
import time
from vivacity.api import create_app
from concurrent.futures import ThreadPoolExecutor


def test_all_labs_execute_sequentially_in_host_container(tmp_path, monkeypatch):
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS', '1')
    monkeypatch.setenv('VIVACITY_MAX_PICKUP_WALL_SECONDS', '300')
    with TestClient(create_app(tmp_path / 'host.sqlite3')) as client:
        for backend, config, settings in [
            ('mujoco', {'task': 'pick_place', 'obstacle_enabled': False},
             {'physics_trials': 8, 'search_candidates': 8, 'execute_selected': True,
              'realtime_execution': True}),
            ('mujoco', {'task': 'pick_place', 'obstacle_enabled': False},
             {'adaptive_trials': True, 'search_candidates': 256, 'physics_budget': 8, 'execute_selected': True}),
            ('cloth', None, {'search_candidates': 50, 'physics_budget': 3,
                             'execute_selected': True}),
        ]:
            body = {'backend': backend, 'seed': 7}
            if config is not None:
                body['config'] = config
            response = client.post('/v1/worlds', json=body)
            assert response.status_code == 201, response.text
            world = response.json()
            response = client.post(f"/v1/worlds/{world['id']}/experiments", json=settings)
            assert response.status_code == 202, response.text
            eid = response.json()['id']
            deadline = time.monotonic() + 120
            while True:
                experiment = client.get(f'/v1/experiments/{eid}').json()
                if experiment['status'] not in ('queued', 'running'):
                    break
                assert time.monotonic() < deadline, experiment
                time.sleep(.05)
            assert experiment['status'] == 'completed', experiment
            assert experiment['selected_branch_id'], experiment
            if backend == 'mujoco':
                assert experiment['result']['executed_settings']['max_wall_seconds'] == 300
            replay = client.get(f'/v1/experiments/{eid}/replay').json()
            assert all(branch['frames'] for branch in replay['branches'])
            assert experiment['result']['execution_evaluation']['success']


def test_every_available_arm_executes_in_host_container(tmp_path,monkeypatch):
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS','1')
    monkeypatch.setenv('VIVACITY_MAX_PICKUP_WALL_SECONDS','300')
    with TestClient(create_app(tmp_path/'arms.sqlite')) as client:
        for arm in ('panda','ur5e','iiwa','gen3','xarm7','scara','dual_arm'):
            from pathlib import Path
            def memory_stage(stage):
                status=Path('/proc/self/status')
                memory=[line for line in status.read_text().splitlines() if line.startswith(('VmRSS:','VmHWM:'))] if status.exists() else []
                print(arm,stage,memory,flush=True)
            memory_stage('initializing')
            response=client.post('/v1/worlds',json={'backend':'mujoco','seed':7,'config':{'task':'pick_place','robot_model':arm,'obstacle_enabled':False}})
            assert response.status_code==201,response.text
            memory_stage('world initialized')
            eid=client.post(f"/v1/worlds/{response.json()['id']}/experiments",json={'physics_trials':3,'search_candidates':3,'max_simulation_seconds':40}).json()['id']
            deadline=time.monotonic()+120
            while True:
                experiment=client.get(f'/v1/experiments/{eid}').json()
                if experiment['status'] not in ('queued','running'):break
                assert time.monotonic()<deadline,(arm,experiment)
                time.sleep(.05)
            assert experiment['status']=='completed' and experiment['selected_branch_id'],(arm,experiment)
            assert experiment['performance']['trial_count']==3
            memory_stage('three native trials completed')


def test_parallel_trials_with_world_creation_and_concurrent_reads(tmp_path,monkeypatch):
    monkeypatch.setenv('VIVACITY_HEADLESS_GEOMETRY','1')
    monkeypatch.setenv('VIVACITY_IMMUTABLE_MODEL_FORKS','1')
    monkeypatch.setenv('VIVACITY_PHYSICS_TRIAL_WORKERS','2')
    with TestClient(create_app(tmp_path/'parallel.sqlite3')) as client:
        first=client.post('/v1/worlds',json={'backend':'mujoco','seed':7,'config':{'task':'pick_place','obstacle_enabled':False}})
        assert first.status_code==201,first.text
        eid=client.post(f"/v1/worlds/{first.json()['id']}/experiments",json={'physics_trials':8,'search_candidates':8,'execute_selected':True}).json()['id']
        second=client.post('/v1/worlds',json={'backend':'mujoco','seed':8,'config':{'task':'pick_place','cube_mass':.065,'obstacle_enabled':False}})
        assert second.status_code==201,second.text
        paths=['/health',f'/v1/experiments/{eid}',f"/v1/worlds/{first.json()['id']}/state",f"/v1/worlds/{second.json()['id']}/state"]
        deadline=time.monotonic()+180
        with ThreadPoolExecutor(max_workers=4) as pool:
            while True:
                responses=list(pool.map(client.get,paths))
                assert all(response.status_code==200 for response in responses),[r.text for r in responses]
                experiment=responses[1].json()
                if experiment['status'] not in ('queued','running'):break
                assert time.monotonic()<deadline
                time.sleep(.05)
        assert experiment['status']=='completed'
        assert experiment['performance']['trial_count']==8
        assert experiment['performance']['peak_parallel_trials']==2
        assert experiment['result']['execution_evaluation']['success']
