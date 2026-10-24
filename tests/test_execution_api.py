import time
import hashlib

from fastapi.testclient import TestClient

from vivacity.api import create_app


OWNER = {'X-Workspace-Token':'contact-owner-'+ 'a'*40}
OTHER = {'X-Workspace-Token':'contact-other-'+ 'b'*40}
PREFIX = '/v1/robotics/contact'


def wait_for(client, path, predicate, timeout=180.):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        response = client.get(path, headers=OWNER)
        assert response.status_code == 200, response.text
        record = response.json()
        if predicate(record):
            return record
        assert record['status'] not in ('interrupted','failed'), record
        time.sleep(.1)
    raise AssertionError(f'Timed out: {record}')


def test_research_gate_does_not_start_work_on_load(monkeypatch,tmp_path):
    monkeypatch.delenv('VIVACITY_EXPERIMENTAL_CONTACT_TASKS',raising=False)
    with TestClient(create_app(tmp_path/'disabled.sqlite3')) as client:
        capabilities = client.get(PREFIX+'/capabilities').json()
        assert capabilities['enabled'] is False
        assert capabilities['release_status'] == 'experimental'
        assert client.post(PREFIX+'/experiments',headers=OWNER,json={}).status_code == 503


def test_real_g1_live_pause_fork_compare_replay_and_export(monkeypatch,tmp_path):
    monkeypatch.setenv('VIVACITY_EXPERIMENTAL_CONTACT_TASKS','1')
    with TestClient(create_app(tmp_path/'native.sqlite3')) as client:
        assert client.get(PREFIX+'/capabilities').json()['enabled']
        assert client.post(PREFIX+'/experiments',headers=OWNER,json={'config':{'parcel':{'mass_kg':-1}}}).status_code == 422
        assert client.post(PREFIX+'/experiments',json={}).status_code == 422
        response = client.post(PREFIX+'/experiments',headers=OWNER,json={})
        assert response.status_code == 202,response.text
        identifier = response.json()['id']
        path = PREFIX+'/experiments/'+identifier
        live = wait_for(client,path+'/frames',lambda p:len(p['frames'])>=2)
        assert live['status'] == 'running'
        assert live['frames'][1]['frame']['qpos'] != live['frames'][0]['frame']['qpos']
        assert client.get(path+'/frames',headers=OTHER).status_code == 404
        assert client.get(path+'/frames?cursor=-1',headers=OWNER).status_code == 422
        assert client.post(path+'/pause',headers=OWNER).status_code == 200
        paused = wait_for(client,path,lambda p:p['status']=='paused')
        before = client.get(path+'/checkpoint',headers=OWNER).json()
        time.sleep(.1)
        after = client.get(path+'/checkpoint',headers=OWNER).json()
        assert before == after
        assert paused['steps_completed'] == before['steps_completed']
        assert client.post(path+'/fork',headers=OTHER,json={}).status_code == 404
        response = client.post(path+'/fork',headers=OWNER,json={})
        assert response.status_code == 202,response.text
        branch = response.json()['id']
        assert client.post(path+'/resume',headers=OWNER).status_code == 200
        result = wait_for(client,path,lambda p:p['status']=='completed')
        fork = wait_for(client,PREFIX+'/experiments/'+branch,lambda p:p['status']=='completed')
        assert result['result']['task_success'] and fork['result']['task_success']
        assert result['result']['measurements']['last_measurement'] == fork['result']['measurements']['last_measurement']
        comparison = client.post(PREFIX+'/compare',headers=OWNER,json={'ids':[identifier,branch]})
        assert comparison.status_code == 200 and comparison.json()['same_world_version']
        replay = client.get(path+'/replay',headers=OWNER).json()
        exported = client.get(path+'/export',headers=OWNER).json()
        assert replay['frames'] == exported['frames']
        assert len(replay['frames']) == exported['checkpoint']['next_frame_seq']
        assert all(not f['frame']['grasp_constraint_active'] for f in replay['frames'])
        assert client.get(path+'/export',headers=OTHER).status_code == 404
        assert client.get(path+'/checkpoint',headers=OTHER).status_code == 404


def test_constrained_task_runs_through_the_same_live_checkpoint_contract(monkeypatch,tmp_path):
    monkeypatch.setenv('VIVACITY_EXPERIMENTAL_CONTACT_TASKS','1')
    with TestClient(create_app(tmp_path/'constrained.sqlite3')) as client:
        invalid = client.post(PREFIX+'/experiments',headers=OWNER,json={'task':'pretend_robot'})
        assert invalid.status_code == 422
        created = client.post(PREFIX+'/experiments',headers=OWNER,json={'task':'g1_constrained_carton'})
        assert created.status_code == 202, created.text
        path = PREFIX+'/experiments/'+created.json()['id']
        live = wait_for(client,path+'/frames',lambda p:len(p['frames'])>=2)
        assert live['status'] == 'running'
        client.post(path+'/pause',headers=OWNER).raise_for_status()
        wait_for(client,path,lambda p:p['status']=='paused')
        checkpoint = client.get(path+'/checkpoint',headers=OWNER).json()
        assert checkpoint['controller_version'] == 'vivacity.g1-wrench-carton/1-experimental'
        assert checkpoint['task_state']['state']['controller_source_sha256']
        scene = client.get(path+'/scene',headers=OWNER).json()
        assert scene['model_hash'] == checkpoint['model_sha256']
        assert scene['world_version'] == checkpoint['world_version']
        table = next(g for g in scene['geoms'] if g['name'] == 'bimanual_table')
        assert table['size'] == [.28,.45,.02]
        meshes = client.get(path+'/meshes',headers=OWNER)
        assert meshes.status_code == 200
        assert hashlib.sha256(meshes.content).hexdigest() == scene['mesh_buffer_sha256']
        assert client.get(path+'/scene',headers=OTHER).status_code == 404
        assert client.get(path+'/meshes',headers=OTHER).status_code == 404
        assert client.get(PREFIX+'/experiments',headers=OTHER).json() == []
        history = client.get(PREFIX+'/experiments',headers=OWNER).json()
        assert created.json()['id'] in [item['id'] for item in history]
        time.sleep(.1)
        assert client.get(path+'/checkpoint',headers=OWNER).json() == checkpoint
        client.post(path+'/resume',headers=OWNER).raise_for_status()
        result = wait_for(client,path,lambda p:p['status']=='completed')
        assert result['result']['task_success']
        assert result['result']['measurements']['maximum_actuator_torque_fraction'] <= 1.00001
        replay = client.get(path+'/replay',headers=OWNER).json()
        export = client.get(path+'/export',headers=OWNER).json()
        assert replay['frames'] == export['frames']
