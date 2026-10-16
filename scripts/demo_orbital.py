"""Exercise the actual import -> native probe -> configured task -> physics APIs."""
import argparse
import json
from pathlib import Path
import time
import uuid

import httpx


def run(base_url, output):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/imports/orbital_salvage_lab.zip'
    with httpx.Client(base_url=base_url, timeout=150) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        record = request('POST', '/v1/imports?filename=Orbital_Salvage_Lab_FIXED.zip',
                         content=fixture.read_bytes(), headers={'Content-Type': 'application/octet-stream'})
        identifier = record['id']
        request('POST', f'/v1/imports/{identifier}/verify')
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            record = request('GET', f'/v1/imports/{identifier}')
            if record['status'] != 'physics_verifying':
                break
            time.sleep(1)
        assert record['status'] == 'actuation_verified', record
        configured = request('POST', f'/v1/imports/{identifier}/configure-task')
        world = request('GET', f"/v1/worlds/{configured['configured_world_id']}")
        experiment = request('POST', f"/v1/worlds/{world['id']}/experiments",
                             json={'candidates': 3, 'physics_trials': 3, 'search_candidates': 3, 'physics_budget': 3, 'execute_selected': True, 'max_simulation_seconds': 40},
                             headers={'Idempotency-Key': str(uuid.uuid4())})
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            experiment = request('GET', f"/v1/experiments/{experiment['id']}")
            if experiment['status'] not in ('queued', 'running'):
                break
            time.sleep(1)
        branches = request('GET', f"/v1/experiments/{experiment['id']}/branches")
        evidence = {'schema_version': '1.0', 'source': 'executed_live_orbital_import_api',
                    'base_url': base_url, 'original_probe': record, 'configured_import': configured,
                    'world': world, 'experiment': experiment, 'branches': branches}
        Path(output).write_text(json.dumps(evidence, indent=2, allow_nan=False) + '\n')
        assert experiment['status'] == 'completed', experiment
        assert experiment['result']['execution_evaluation']['success'], experiment['result']
        print(json.dumps({'status': 'passed', 'experiment_id': experiment['id'],
                          'goal_error_m': experiment['result']['execution_evaluation']['goal_error_m'],
                          'performance': experiment['performance'], 'evidence': output}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8002')
    parser.add_argument('--output', default='artifacts/orbital-api.json')
    args = parser.parse_args()
    run(args.base_url.rstrip('/'), args.output)
