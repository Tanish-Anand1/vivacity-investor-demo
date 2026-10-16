import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app


@pytest.mark.parametrize('route', ['/v1/sessions', '/v1/worlds/missing/experiments'])
def test_host_rejects_oversized_jobs_before_allocating_worlds_or_queue(tmp_path, monkeypatch, route):
    monkeypatch.setenv('VIVACITY_MAX_PHYSICS_TRIALS', '8')
    with TestClient(create_app(tmp_path / 'limits.sqlite3')) as client:
        body = {'physics_trials': 5000, 'search_candidates': 5000}
        if route == '/v1/sessions':
            body.update(backend='mujoco', config={'task': 'pick_place'})
        response = client.post(route, headers={'X-Session-Token': 'test-' + 'a' * 40}, json=body)
        assert response.status_code == 422, response.text
        assert 'at most 8' in response.json()['detail']
        assert client.get('/health').json()['limits']['max_physics_trials'] == 8
        with client.app.state.runtime.store.connect() as db:
            assert db.execute('SELECT COUNT(*) FROM worlds').fetchone()[0] == 0
            assert db.execute('SELECT COUNT(*) FROM experiments').fetchone()[0] == 0
