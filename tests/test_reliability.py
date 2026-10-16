"""Boundary regressions for duplicate submissions and incomplete branch evidence."""
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.runtime import Conflict, Runtime, Unavailable
from vivacity.schemas import CreateWorld, ExperimentRequest


def test_idempotent_concurrent_requests_and_conflicting_input(runtime):
    world = runtime.create_world(CreateWorld(backend='cloth'))
    request = ExperimentRequest(search_candidates=50, physics_budget=3)
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies = list(pool.map(lambda _: runtime.submit(world['id'], request, 'investor-run-1'), range(4)))
    ids = {reply['id'] for reply in replies}
    assert len(ids) == 1
    experiment = runtime.wait(ids.pop())
    assert experiment['status'] == 'completed'
    assert runtime.get_world(world['id'])['history'] == [experiment['id']]
    with pytest.raises(Conflict, match='different'):
        runtime.submit(world['id'], ExperimentRequest(candidates=4), 'investor-run-1')
    runtime.reset(world['id'])
    replayed = runtime.submit(world['id'], request, 'investor-run-1')
    assert replayed['id'] == experiment['id']
    assert replayed['stale']  # A retry never silently computes a new environment revision.


def test_idempotent_retry_bypasses_a_full_queue(runtime):
    world = runtime.create_world(CreateWorld(backend='cloth'))
    experiment = runtime.wait(runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3), 'same-operation')['id'])
    for _ in range(8):
        assert runtime.capacity.acquire(blocking=False)
    try:
        retry = runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3), 'same-operation')
        assert retry['id'] == experiment['id']
    finally:
        for _ in range(8):
            runtime.capacity.release()


def test_idempotency_survives_process_restart(tmp_path):
    path = tmp_path / 'restart.sqlite3'
    first = Runtime(path)
    world = first.create_world(CreateWorld(backend='cloth'))
    experiment = first.wait(first.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3), 'persistent-retry')['id'])
    first.close()
    second = Runtime(path)
    try:
        assert second.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3), 'persistent-retry')['id'] == experiment['id']
        assert len(second.get_world(world['id'])['history']) == 1
    finally:
        second.close()


def test_failure_in_one_adapter_branch_does_not_erase_other_outcomes(runtime, monkeypatch):
    backend = runtime.backends['cloth']
    simulate = backend.simulate
    calls = 0
    def partial_failure(world, settings):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('injected adapter failure')
        return simulate(world, settings)
    monkeypatch.setattr(backend, 'simulate', partial_failure)
    world = runtime.create_world(CreateWorld(backend='cloth'))
    experiment = runtime.wait(runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3))['id'])
    assert experiment['status'] == 'completed'
    assert experiment['selected_branch_id']  # Independent feasible physical alternatives survive.
    branches = runtime.store.branches(experiment['id'])
    assert len(branches) == 3
    assert branches[0]['evaluation']['status'] == 'adapter_failure'
    assert branches[0]['trace'] == []
    assert branches[0]['performance']['simulation_steps'] is None
    assert branches[1]['evaluation']['success'] and branches[1]['trace']
    assert experiment['performance']['adapter_error_count'] == 1
    assert not experiment['performance']['measurement_complete']
    assert runtime.replay(experiment['id'])['branches'][0]['source'] == 'failed_adapter_execution'
    assert len(runtime.get_world(world['id'])['branches']) == 3
    with pytest.raises(Conflict, match='failed'):
        runtime.commit(world['id'], experiment['id'], branches[0]['id'])


def test_uncaught_nan_result_is_not_persisted_as_valid_evidence(runtime, monkeypatch):
    backend = runtime.backends['cloth']
    simulate = backend.simulate
    calls = 0
    def invalid_result(world, settings):
        nonlocal calls
        calls += 1
        result = simulate(world, settings)
        if calls == 1:
            result['execution_duration_s'] = float('nan')
        return result
    monkeypatch.setattr(backend, 'simulate', invalid_result)
    world = runtime.create_world(CreateWorld(backend='cloth'))
    experiment = runtime.wait(runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3))['id'])
    branch = runtime.store.branches(experiment['id'])[0]
    assert branch['evaluation']['status'] == 'adapter_failure'
    assert branch['evaluation']['phase'] == 'serialize_result'
    assert branch['trace'] == []
    assert experiment['selected_branch_id']


def test_unavailable_final_snapshot_is_explicit(runtime, monkeypatch):
    backend = runtime.backends['cloth']
    snapshot = backend.snapshot
    world = runtime.create_world(CreateWorld(backend='cloth'))
    def broken_snapshot(instance):
        if instance.data.time > 0:
            raise RuntimeError('injected snapshot failure')
        return snapshot(instance)
    monkeypatch.setattr(backend, 'snapshot', broken_snapshot)
    experiment = runtime.wait(runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3))['id'])
    assert experiment['status'] == 'failed'
    assert all(b['final_state'] is None for b in runtime.store.branches(experiment['id']))
    assert all(not b['evaluation']['final_state_available'] for b in runtime.store.branches(experiment['id']))


def test_completed_lineage_survives_later_planning_failure(runtime, monkeypatch):
    backend = runtime.backends['mujoco']
    candidates = backend.candidates
    count = 0
    def fail_followup(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('injected follow-up planning failure')
        return candidates(*args)
    monkeypatch.setattr(backend, 'candidates', fail_followup)
    world = runtime.create_world(CreateWorld(backend='mujoco'))
    experiment = runtime.wait(runtime.submit(world['id'], ExperimentRequest(candidates=2, planner_iterations=100))['id'])
    assert experiment['status'] == 'failed'
    branches = runtime.store.branches(experiment['id'])
    lineage = runtime.get_world(world['id'])['branches']
    assert len(branches) == len(lineage) == 2
    assert {b['id'] for b in branches} == {b['branch_id'] for b in lineage}
    assert runtime.store.events(experiment['id'])[-1]['kind'] == 'failed'


def test_terminal_event_committed_during_empty_read_is_delivered(tmp_path, monkeypatch):
    app = create_app(tmp_path / 'event-race.sqlite3')
    with TestClient(app) as client:
        runtime = app.state.runtime
        backend = runtime.backends['cloth']
        simulate = backend.simulate
        started, release = threading.Event(), threading.Event()
        def paused(world, settings):
            started.set()
            assert release.wait(10)
            return simulate(world, settings)
        monkeypatch.setattr(backend, 'simulate', paused)
        world = runtime.create_world(CreateWorld(backend='cloth'))
        experiment = runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3))
        assert started.wait(10)
        events = runtime.store.events
        raced = False
        def raced_empty(eid, after=0):
            nonlocal raced
            if not raced:
                raced = True
                release.set()
                assert runtime.wait(eid)['status'] == 'completed'
                return []  # Emulate a read taken immediately before terminal commit.
            return events(eid, after)
        monkeypatch.setattr(runtime.store, 'events', raced_empty)
        try:
            with client.websocket_connect(f"/v1/experiments/{experiment['id']}/events") as ws:
                received = []
                while True:
                    event = ws.receive_json()
                    received.append(event)
                    if event['kind'] == 'completed':
                        break
            assert raced
            assert received[-1]['kind'] == 'completed'
        finally:
            release.set()


def test_http_idempotency_validation_and_browser_preflight(tmp_path):
    with TestClient(create_app(tmp_path / 'headers.sqlite3')) as client:
        world = client.post('/v1/worlds', json={'backend': 'cloth'}).json()
        route = f"/v1/worlds/{world['id']}/experiments"
        first = client.post(route, json={"search_candidates":50,"physics_budget":3}, headers={'Idempotency-Key': 'demo-unique-1'})
        second = client.post(route, json={"search_candidates":50,"physics_budget":3}, headers={'Idempotency-Key': 'demo-unique-1'})
        assert first.status_code == second.status_code == 202
        assert first.json()['id'] == second.json()['id']
        assert client.post(route, json={'candidates': 5}, headers={'Idempotency-Key': 'demo-unique-1'}).status_code == 409
        for key in ['', 'a'*129, 'has spaces']:
            assert client.post(route, json={"search_candidates":50,"physics_budget":3}, headers={'Idempotency-Key': key}).status_code == 422
        preflight = client.options(route, headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type,idempotency-key'})
        assert preflight.status_code == 200
        documented = client.get('/openapi.json').json()['paths']['/v1/worlds/{world_id}/experiments']['post']['parameters']
        assert any(p['name'] == 'idempotency-key' and p['in'] == 'header' for p in documented)


def test_worker_submission_failure_is_persistent_and_releases_slot(runtime, monkeypatch):
    def unavailable(*args):
        raise RuntimeError('injected executor shutdown')
    monkeypatch.setattr(runtime.executor, 'submit', unavailable)
    world = runtime.create_world(CreateWorld(backend='cloth'))
    with pytest.raises(Unavailable):
        runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3), 'submission-failure')
    retry = runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3), 'submission-failure')
    assert retry['status'] == 'failed'
    assert retry['error'] == 'worker_submission_failed'
    assert runtime.store.events(retry['id'])[-1]['kind'] == 'failed'
    for _ in range(8):
        assert runtime.capacity.acquire(blocking=False)
    for _ in range(8):
        runtime.capacity.release()


def test_adapter_failure_serializes_nullable_snapshot_and_503(tmp_path, monkeypatch):
    app = create_app(tmp_path / 'error-response.sqlite3')
    with TestClient(app) as client:
        runtime = app.state.runtime
        world = client.post('/v1/worlds', json={'backend': 'cloth'}).json()
        backend = runtime.backends['cloth']
        snapshot = backend.snapshot
        def broken_snapshot(instance):
            if instance.data.time > 0:
                raise RuntimeError('injected final snapshot failure')
            return snapshot(instance)
        monkeypatch.setattr(backend, 'snapshot', broken_snapshot)
        eid = client.post(f"/v1/worlds/{world['id']}/experiments", json={"search_candidates":50,"physics_budget":3}).json()['id']
        assert runtime.wait(eid)['status'] == 'failed'
        response = client.get(f'/v1/experiments/{eid}/branches')
        assert response.status_code == 200
        assert all(b['final_state'] is None for b in response.json())
        def unavailable(*args):
            raise RuntimeError('injected executor unavailable')
        monkeypatch.setattr(runtime.executor, 'submit', unavailable)
        response = client.post(f"/v1/worlds/{world['id']}/experiments", json={"search_candidates":50,"physics_budget":3}, headers={'Idempotency-Key': 'worker-outage'})
        assert response.status_code == 503 and response.headers['retry-after'] == '5'


def test_future_completes_only_after_queue_capacity_is_released(runtime, monkeypatch):
    entered, allow_release = threading.Event(), threading.Event()
    original = runtime.capacity.release
    def delayed_release():
        entered.set()
        assert allow_release.wait(10)
        original()
    monkeypatch.setattr(runtime.capacity, 'release', delayed_release)
    world = runtime.create_world(CreateWorld(backend='cloth'))
    experiment = runtime.submit(world['id'], ExperimentRequest(search_candidates=50, physics_budget=3))
    try:
        assert entered.wait(120)
        assert not runtime.futures[experiment['id']].done()
    finally:
        allow_release.set()
    assert runtime.wait(experiment['id'])['status'] == 'completed'
    for _ in range(8):
        assert runtime.capacity.acquire(blocking=False)
    for _ in range(8):
        runtime.capacity.release()
