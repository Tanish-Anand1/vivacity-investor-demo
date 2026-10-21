import time
import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / 'api.sqlite3')) as c:
        yield c


def finish(client, world):
    response = client.post(f"/v1/worlds/{world['id']}/experiments", json=({'search_candidates':50,'physics_budget':3} if world['backend']=='cloth' else {}))
    assert response.status_code == 202
    eid = response.json()['id']
    # IK/RRT wall time varies with CPU contention; correctness has no 30 s SLA.
    deadline = time.monotonic()+120
    while time.monotonic() < deadline:
        e = client.get(f'/v1/experiments/{eid}').json()
        if e['status'] in ('completed', 'failed'):
            assert e['status'] == 'completed', e
            return e
        time.sleep(0.02)
    pytest.fail('job did not finish in 120 seconds')


@pytest.mark.parametrize('body', [
    {'backend': 'fake'}, {'backend': 'mujoco', 'seed': -1},
    {'backend': 'mujoco', 'config': {'obstacle_position': [1, 2]}},
    {'backend': 'mujoco', 'config': {'obstacle_position': [9, 0, 0.2]}},
    {'backend': 'cloth', 'config': {'mass': 0}},
    {'backend': 'cloth', 'config': {'side_length': 100000}},
    {'backend': 'cloth', 'config': {'unknown': True}},
    {'backend': 'cloth', 'config': {'side_length': 0}},
    {'backend': 'mujoco', 'config': {'hidden_mass': 0.1}},
    {'backend': 'cloth', 'config': {'friction': 0}},
    {'backend': 'scipy', 'config': {'noise_std': -1}},
    {'backend': 'scipy', 'config': {'samples': 10000}},
    {'backend': 'scipy', 'config': {'initial_state': [0, 0, 0, 1]}},
])
def test_request_validation(client, body):
    assert client.post('/v1/worlds', json=body).status_code == 422


def test_api_cloth_journey_events_commit_reset(client):
    assert client.get('/health').status_code == 200
    assert client.head('/health').status_code == 200
    response = client.post('/v1/worlds', json={'backend': 'cloth'})
    assert response.status_code == 201
    w = response.json()
    assert 'hidden_mass' not in response.text
    assert client.get(f"/v1/worlds/{w['id']}").json() == w
    assert client.get(f"/v1/worlds/{w['id']}/state").status_code == 200
    e = finish(client, w)
    branches = client.get(f"/v1/experiments/{e['id']}/branches").json()
    assert len(branches) == 3
    assert branches[0]['experiment_id'] == e['id']
    replay = client.get(f"/v1/experiments/{e['id']}/replay")
    assert replay.status_code == 200 and len(replay.json()['branches']) == 3
    assert 'hidden_mass' not in replay.text
    with client.websocket_connect(f"/v1/experiments/{e['id']}/events") as ws:
        events = []
        while True:
            event = ws.receive_json(); events.append(event)
            if event['kind'] == 'completed':
                break
    assert events[0]['kind']=='queued' and events[-1]['kind']=='completed'
    assert sum(ev['kind']=='branch_completed' for ev in events)==3
    assert all(a['seq'] < b['seq'] for a, b in zip(events, events[1:]))
    commit = {'experiment_id': e['id'], 'branch_id': e['selected_branch_id']}
    assert client.post(f"/v1/worlds/{w['id']}/commit", json=commit).status_code == 200
    assert client.post(f"/v1/worlds/{w['id']}/commit", json=commit).status_code == 409
    reset = client.post(f"/v1/worlds/{w['id']}/reset").json()
    assert reset['state'] == w['initial_state']
    assert client.get(f"/v1/experiments/{e['id']}").json()['stale']


def test_api_science_fits_replay_and_environment_invalidation(client):
    response = client.post('/v1/worlds', json={'backend':'scipy','seed':7,'config':{'hidden_mass':.12}})
    assert response.status_code == 201
    world = response.json()
    assert 'hidden_mass' not in response.text
    observed = client.get(f"/v1/worlds/{world['id']}/state").json()
    assert len(observed['observation']['observations']) == 70
    assert 'hidden_mass' not in str(observed)
    experiment = finish(client, world)
    branches = client.get(f"/v1/experiments/{experiment['id']}/branches").json()
    assert len(branches) == 2
    assert branches[0]['evaluation']['hypothesis'] == 'central_only'
    assert branches[1]['evaluation']['hypothesis'] == 'central_plus_fixed_perturber'
    assert branches[1]['evaluation']['heldout_rmse'] < branches[0]['evaluation']['heldout_rmse']
    assert experiment['selected_branch_id'] == branches[1]['id']
    with client.websocket_connect(f"/v1/experiments/{experiment['id']}/events") as ws:
        kinds = []
        while True:
            event = ws.receive_json()
            kinds.append(event['kind'])
            if event['kind'] == 'completed':
                break
    assert kinds.count('branch_completed') == 2
    replay = client.get(f"/v1/experiments/{experiment['id']}/replay")
    assert replay.status_code == 200
    assert replay.json()['branches'][1]['frames'] == branches[1]['trace']
    assert 'hidden_mass' not in replay.text
    changed = client.patch(f"/v1/worlds/{world['id']}/environment",json={'config':{'noise_std':.01,'samples':50}})
    assert changed.status_code == 200
    assert changed.json()['revision'] == 1
    assert client.get(f"/v1/experiments/{experiment['id']}").json()['stale']


def test_api_robotics_reposition_and_replan(client):
    w = client.post('/v1/worlds', json={'backend': 'mujoco'}).json()
    e = finish(client, w)
    branches = client.get(f"/v1/experiments/{e['id']}/branches").json()
    assert any(b['evaluation']['success'] for b in branches)
    failed = next(b for b in branches if not b['evaluation']['success'])
    assert client.post(f"/v1/worlds/{w['id']}/commit", json={'experiment_id': e['id'], 'branch_id': failed['id']}).status_code == 409
    assert client.patch(f"/v1/worlds/{w['id']}/environment", json={'config': {'obstacle_position': [0.75, -0.4, 0.2]}}).status_code == 200
    assert client.get(f"/v1/experiments/{e['id']}/replay").json()['stale']
    assert client.post(f"/v1/worlds/{w['id']}/commit", json={'experiment_id': e['id'], 'branch_id': e['selected_branch_id']}).status_code == 409
    e2 = finish(client, w)
    assert e2['selected_branch_id']


def test_missing_and_invalid_resources(client):
    for route in ['/v1/worlds/missing', '/v1/worlds/missing/state', '/v1/experiments/missing', '/v1/experiments/missing/branches', '/v1/experiments/missing/replay']:
        assert client.get(route).status_code == 404
    assert client.post('/v1/worlds/missing/experiments', json={"search_candidates":50,"physics_budget":3}).status_code == 404
    w = client.post('/v1/worlds', json={'backend': 'cloth'}).json()
    assert client.post(f"/v1/worlds/{w['id']}/experiments", json={'candidates': 50}).status_code == 422
    assert client.patch(f"/v1/worlds/{w['id']}/environment", json={'config': {'obstacle_position': [0.5, 0, 0.2]}}).status_code == 422


def test_cors_and_openapi(client):
    response = client.options('/v1/worlds', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    response = client.options('/v1/worlds', headers={'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST'})
    assert response.status_code == 400
    spec = client.get('/openapi.json').json()
    assert spec['info']['version'] == '1.0.0'
    assert 'BranchResponse' in spec['components']['schemas']
