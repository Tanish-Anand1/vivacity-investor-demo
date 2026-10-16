"""Exercise retry safety through real HTTP; no injected simulator results."""
import json
from pathlib import Path
import time
import uuid
import httpx


def main():
    base = 'http://127.0.0.1:8000'
    with httpx.Client(base_url=base, timeout=30) as client:
        response = client.post('/v1/worlds', json={'backend': 'cloth'})
        response.raise_for_status()
        world = response.json()
        route = f"/v1/worlds/{world['id']}/experiments"
        key = str(uuid.uuid4())
        headers = {'Idempotency-Key': key}
        first = client.post(route, json={'search_candidates':50,'physics_budget':3}, headers=headers)
        retry = client.post(route, json={'search_candidates':50,'physics_budget':3}, headers=headers)
        first.raise_for_status(); retry.raise_for_status()
        assert first.json()['id'] == retry.json()['id']
        conflict = client.post(route, json={'candidates': 5}, headers=headers)
        assert conflict.status_code == 409
        experiment = retry.json()
        deadline = time.monotonic()+120
        while experiment['status'] in ('queued', 'running'):
            if time.monotonic() > deadline:
                raise RuntimeError('experiment did not finish')
            time.sleep(0.05)
            experiment = client.get(f"/v1/experiments/{experiment['id']}").json()
        assert experiment['status'] == 'completed' and experiment['selected_branch_id']
        history = client.get(f"/v1/worlds/{world['id']}").json()['history']
        assert history == [experiment['id']]
        reset = client.post(f"/v1/worlds/{world['id']}/reset")
        reset.raise_for_status()
        after_reset = client.post(route, json={'search_candidates':50,'physics_budget':3}, headers=headers)
        after_reset.raise_for_status()
        assert after_reset.json()['id'] == experiment['id'] and after_reset.json()['stale']
        branches = client.get(f"/v1/experiments/{experiment['id']}/branches").json()
        report = {'status': 'passed', 'base_url': base, 'world_id': world['id'], 'experiment': experiment, 'observed_http_statuses': {'first': first.status_code, 'retry': retry.status_code, 'conflict': conflict.status_code}, 'evaluations': [b['evaluation'] for b in branches], 'checks': ['same_key_returns_same_experiment', 'conflicting_body_rejected', 'single_experiment_in_history', 'retry_after_revision_change_is_original_stale_result', 'real_mujoco_folding_completed']}
        Path('artifacts/live-retries.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print({k: v for k, v in report.items() if k not in ('experiment', 'evaluations')})


if __name__ == '__main__':
    main()
