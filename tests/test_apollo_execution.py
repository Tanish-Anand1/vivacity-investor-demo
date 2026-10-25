"""The experimental Apollo primitive uses the same durable runtime as G1."""
import time

from fastapi.testclient import TestClient
import numpy as np
import pytest

from vivacity.api import create_app
from vivacity.apollo_execution import ApolloDoorAdapter, ApolloDoorSettings


OWNER = {'X-Workspace-Token': 'apollo-research-owner-' + 'a'*40}
OTHER = {'X-Workspace-Token': 'apollo-research-other-' + 'b'*40}
BASE = '/v1/robotics/contact'


def wait_for(client, path, predicate, timeout=90.):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        response = client.get(path, headers=OWNER)
        assert response.status_code == 200, response.text
        value = response.json()
        if predicate(value):
            return value
        assert value['status'] != 'interrupted', value
        time.sleep(.05)
    raise AssertionError(f'Timed out waiting for {path}: {value}')


def test_apollo_adapter_forks_independent_full_native_state_and_classifies_scope():
    adapter = ApolloDoorAdapter()
    task = adapter.create(ApolloDoorSettings().model_dump())
    first = task.frame()
    assert first['phase'] == 'settle' and not first['grasp_constraint_active']
    for _ in range(30):
        task.step()
    checkpoint = task.snapshot()
    branch = adapter.restore(checkpoint)
    for _ in range(15):
        task.step()
        branch.step()
    np.testing.assert_array_equal(task.primitive.data.qpos, branch.primitive.data.qpos)
    assert task.primitive.controller.snapshot() == branch.primitive.controller.snapshot()
    branch.primitive.data.ctrl[0] += .1
    assert not np.array_equal(task.primitive.data.ctrl, branch.primitive.data.ctrl)
    report = task.result()
    assert not report['task_success'] and not report['cabinet_service_complete']
    assert report['equality_constraints'] == report['mocap_bodies'] == 0
    assert report['model_sha256'] == checkpoint.checkpoint.model_sha256
    checkpoint.checkpoint.task_state['execution_adapter_source_sha256'] = '0'*64
    with pytest.raises(ValueError, match='adapter changed'):
        adapter.restore(checkpoint)


def test_apollo_http_frames_pause_fork_cancel_and_replay_are_owner_scoped(monkeypatch, tmp_path):
    monkeypatch.setenv('VIVACITY_EXPERIMENTAL_CONTACT_TASKS', '1')
    with TestClient(create_app(tmp_path/'apollo.sqlite3')) as client:
        caps = client.get(BASE+'/capabilities').json()
        assert any(t['id'] == 'apollo_door_primitive' and 'Cartridge exchange' in t['scope']
                   for t in caps['tasks'])
        invalid = client.post(BASE+'/apollo-door-experiments', headers=OWNER,
                              json={'config': {'opening_angle_rad': 1.7}})
        assert invalid.status_code == 422
        for field in ('old_tray_surface_height_m', 'replacement_tray_surface_height_m'):
            invalid_layout = client.post(BASE+'/apollo-door-experiments', headers=OWNER,
                json={'config': {'cabinet': {field: .6}}})
            assert invalid_layout.status_code == 422
        created = client.post(BASE+'/apollo-door-experiments', headers=OWNER, json={})
        assert created.status_code == 202, created.text
        identifier = created.json()['id']
        path = BASE+'/experiments/'+identifier
        live = wait_for(client, path+'/frames', lambda page: len(page['frames']) >= 2)
        assert live['status'] == 'running'
        assert live['frames'][0]['frame']['time_s'] < live['frames'][1]['frame']['time_s']
        assert all(not entry['frame']['grasp_constraint_active'] for entry in live['frames'])
        assert client.get(path+'/checkpoint', headers=OTHER).status_code == 404
        assert client.post(path+'/pause', headers=OWNER).status_code == 200
        paused = wait_for(client, path, lambda record: record['status'] == 'paused')
        checkpoint = client.get(path+'/checkpoint', headers=OWNER).json()
        assert checkpoint['steps_completed'] == paused['steps_completed']
        assert checkpoint['task_state']['execution_adapter_source_sha256']
        forked = client.post(path+'/fork', headers=OWNER, json={})
        assert forked.status_code == 202, forked.text
        branch = forked.json()['id']
        assert client.post(path+'/cancel', headers=OWNER).status_code == 200
        wait_for(client, path, lambda record: record['status'] == 'cancelled')
        branch_path = BASE+'/experiments/'+branch
        branch_live = wait_for(client, branch_path+'/frames', lambda page: len(page['frames']) >= 1)
        assert branch_live['frames'][0]['seq'] == 0
        assert client.post(branch_path+'/cancel', headers=OWNER).status_code == 200
        wait_for(client, branch_path, lambda record: record['status'] == 'cancelled')
        compared = client.post(BASE+'/compare', headers=OWNER,
                               json={'ids': [identifier, branch]}).json()
        assert compared['same_world_version']
        saved = client.get(path+'/export', headers=OWNER).json()
        replay = client.get(path+'/replay', headers=OWNER).json()
        assert replay['frames'] == saved['frames']
        assert all(entry['seq'] == index for index, entry in enumerate(replay['frames']))
        assert client.get(branch_path+'/replay', headers=OTHER).status_code == 404


def test_apollo_shared_worker_reports_only_measured_door_primitive_success(monkeypatch, tmp_path):
    monkeypatch.setenv('VIVACITY_EXPERIMENTAL_CONTACT_TASKS', '1')
    with TestClient(create_app(tmp_path/'apollo-success.sqlite3')) as client:
        created = client.post(BASE+'/apollo-door-experiments', headers=OWNER, json={})
        assert created.status_code == 202, created.text
        path = BASE+'/experiments/'+created.json()['id']
        finished = wait_for(client, path, lambda record: record['status'] in ('completed','failed'),
                            timeout=180.)
        assert finished['status'] == 'completed', finished
        report = finished['result']
        assert report['task_success'] and not report['cabinet_service_complete']
        assert report['measurements']['door_angle_rad'] > .20
        assert report['measurements']['latch_retraction_m'] > .035
        assert report['measurements']['root_speed_m_s'] < .03
        assert report['equality_constraints'] == report['mocap_bodies'] == 0
        replay = client.get(path+'/replay', headers=OWNER).json()
        assert len(replay['frames']) > 2
        assert replay['frames'][-1]['frame']['time_s'] == pytest.approx(
            report['measurements']['time_s'])
