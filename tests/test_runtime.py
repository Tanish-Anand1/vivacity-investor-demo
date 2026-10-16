import json
import threading
import httpx
import pytest
from vivacity.runtime import Runtime, Conflict, Busy
from vivacity.schemas import CreateWorld, ExperimentRequest, ClothConfig
from vivacity.agent import HostedPolicy
from vivacity.agent import DeterministicPolicy


def test_persistence_and_interrupted_job(tmp_path):
    path = tmp_path / 'persistent.sqlite3'
    r = Runtime(path)
    w = r.create_world(CreateWorld(backend='cloth'))
    e = r.wait(r.submit(w['id'], ExperimentRequest(search_candidates=50, physics_budget=3))['id'])
    branches = r.store.branches(e['id']); events = r.store.events(e['id'])
    interrupted = r.store.get('experiments', e['id']) | {'id': 'interrupted', 'status': 'running'}
    r.store.put('experiments', interrupted)
    r.close()
    second = Runtime(path)
    try:
        assert second.get_world(w['id'])['state'] == w['state']
        assert second.get_experiment(e['id']) == e
        assert second.store.branches(e['id']) == branches
        assert second.store.events(e['id']) == events
        assert second.get_experiment('interrupted')['status'] == 'failed'
        assert second.store.events('interrupted')[-1]['kind'] == 'failed'
    finally:
        second.close()


def test_geometry_change_while_running_preserves_new_world(runtime, monkeypatch):
    started, release = threading.Event(), threading.Event()
    backend = runtime.backends['cloth']; simulate = backend.simulate

    def delayed(w, limits):
        started.set(); assert release.wait(timeout=10)
        return simulate(w, limits)

    monkeypatch.setattr(backend, 'simulate', delayed)
    w = runtime.create_world(CreateWorld(backend='cloth'))
    e = runtime.submit(w['id'], ExperimentRequest(search_candidates=50, physics_budget=3))
    assert started.wait(timeout=10)
    try:
        changed = runtime.environment(w['id'], ClothConfig(friction=.5))
    finally:
        release.set()
    completed = runtime.wait(e['id'])
    assert completed['stale']
    assert runtime.get_world(w['id'])['state'] == changed['state']
    with pytest.raises(Conflict):
        runtime.commit(w['id'], e['id'], completed['selected_branch_id'])


def test_worker_failure_is_persisted(runtime, monkeypatch):
    def failure(*args):
        raise RuntimeError('injected integration boundary failure')
    monkeypatch.setattr(runtime.backends['cloth'], 'simulate', failure)
    w = runtime.create_world(CreateWorld(backend='cloth'))
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest(search_candidates=50, physics_budget=3))['id'])
    assert e['status'] == 'failed' and e['selected_branch_id'] is None
    assert e['error'] == 'all_branches_failed:adapter_failure'
    branches = runtime.store.branches(e['id'])
    assert len(branches) == 3
    assert all(b['evaluation']['status'] == 'adapter_failure' for b in branches)
    assert all(b['performance']['simulation_steps'] is None for b in branches)
    assert runtime.store.events(e['id'])[-1]['kind'] == 'failed'


def test_cross_world_commit_is_rejected(runtime):
    a = runtime.create_world(CreateWorld(backend='cloth'))
    b = runtime.create_world(CreateWorld(backend='cloth'))
    e = runtime.wait(runtime.submit(a['id'], ExperimentRequest(search_candidates=50, physics_budget=3))['id'])
    with pytest.raises(Conflict, match='belong'):
        runtime.commit(b['id'], e['id'], e['selected_branch_id'])


def test_bounded_queue(runtime):
    for _ in range(8):
        assert runtime.capacity.acquire(blocking=False)
    try:
        with pytest.raises(Busy):
            runtime.submit('unused', ExperimentRequest(search_candidates=50, physics_budget=3))
    finally:
        for _ in range(8):
            runtime.capacity.release()


def test_no_key_mode_is_explicit(runtime, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    with pytest.raises(ValueError, match='requires'):
        HostedPolicy().propose({}, {}, ExperimentRequest(policy='llm').model_dump())
    w = runtime.create_world(CreateWorld(backend='cloth'))
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest(search_candidates=50, physics_budget=3))['id'])
    assert not e['result']['policy']['llm_used']


def test_hosted_adapter_contract_only(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-noncredential')
    monkeypatch.setenv('OPENAI_MODEL', 'contract-test-model')
    original_client = httpx.Client
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(200, json={'output': [{'content': [{'type': 'output_text', 'text': '{"candidates":3,"planner_iterations":1200}'}]}]})

    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original_client(transport=httpx.MockTransport(handler)))
    proposal, metadata = HostedPolicy().propose({'observations': [[1, 0]]}, {'type': 'fit_hypothesis'}, ExperimentRequest(policy='llm').model_dump())
    assert proposal['planner_iterations'] == 1200
    assert sent[0]['text']['format']['strict'] is True
    assert metadata['llm_used']  # transport contract test; no live provider call


def test_hosted_proposal_cannot_supply_fake_results(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-noncredential')
    monkeypatch.setenv('OPENAI_MODEL', 'contract-test-model')
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'output': [{'content': [{'type': 'output_text', 'text': '{"candidates":3,"planner_iterations":1200,"success":true}'}]}]}))
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original_client(transport=transport))
    with pytest.raises(ValueError):
        HostedPolicy().propose({}, {}, ExperimentRequest(policy='llm').model_dump())


def test_policy_chooses_bounded_followup():
    policy = DeterministicPolicy()
    branches = [{'evaluation': {'success': False, 'status': 'planning_failure'}, 'action': {'ik': {'converged': True}}}]
    settings = ExperimentRequest(planner_iterations=100).model_dump()
    assert policy.next_experiment('mujoco', {'contacts': []}, branches, settings)['planner_iterations'] == 200
    assert policy.next_experiment('mujoco', {'contacts': [{'category': 'environment_collision'}]}, branches, settings) is None
    assert policy.next_experiment('cloth', {}, branches, settings) is None


def test_followup_runs_real_physics_and_preserves_failed_round(runtime):
    w = runtime.create_world(CreateWorld(backend='mujoco'))
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest(candidates=2, planner_iterations=100))['id'])
    assert e['status'] == 'completed'
    assert e['result']['followup_settings']['planner_iterations'] == 200
    branches = runtime.store.branches(e['id'])
    assert len(branches) == 4
    assert branches[0]['evaluation']['status'] == 'collision_failure'
    assert branches[2]['action']['followup']
    assert branches[3]['action']['followup']
    assert any(ev['kind'] == 'planned' and ev['details'].get('followup') for ev in runtime.store.events(e['id']))
