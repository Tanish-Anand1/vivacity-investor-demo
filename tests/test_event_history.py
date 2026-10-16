import time
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.storage import Store


def test_events_have_real_timestamps_and_paginated_sequence(tmp_path):
    store=Store(tmp_path/'events.sqlite')
    before=time.time()
    for i in range(105):
        store.event('experiment','progress',{'screened':i})
    batch=store.events('experiment')
    assert len(batch)==100
    assert all(before<=e['details']['timestamp_unix_s']<=time.time() for e in batch)
    assert [e['details']['screened'] for e in store.events('experiment',batch[-1]['seq'])]==list(range(100,105))


def test_rest_history_requires_real_experiment(tmp_path):
    with TestClient(create_app(tmp_path/'api.sqlite')) as client:
        assert client.get('/v1/experiments/missing/events').status_code==404
        w=client.post('/v1/worlds',json={'backend':'cloth'}).json()
        e=client.post(f"/v1/worlds/{w['id']}/experiments",json={"search_candidates":50,"physics_budget":3}).json()
        client.app.state.runtime.wait(e['id'])
        events=client.get(f"/v1/experiments/{e['id']}/events").json()
        assert events[0]['kind']=='queued'
        assert events[-1]['kind']=='completed'
        assert events[0]['details']['timestamp_unix_s']<=events[-1]['details']['timestamp_unix_s']
