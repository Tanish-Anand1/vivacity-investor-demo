"""Exercise the deployed precision-assembly API and retain measured evidence.

Usage: python -m scripts.verify_v_robotics_public --base https://isabella-labs-runtime.onrender.com
This intentionally starts a new public-host experiment; do not run it as a health probe.
"""
import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='https://isabella-labs-runtime.onrender.com')
    parser.add_argument('--output', type=Path, default=Path('artifacts/v-robotics-public-live.json'))
    parser.add_argument('--timeout-s', type=int, default=600)
    args = parser.parse_args()
    base = args.base.rstrip('/')
    evidence = {'base': base, 'started_unix_s': time.time()}
    with httpx.Client(timeout=httpx.Timeout(120., connect=30.), follow_redirects=False) as client:
        def request(method: str, path: str, **kwargs):
            response = client.request(method, base + path, **kwargs)
            response.raise_for_status()
            return response.json()

        health = request('GET', '/health')
        programs = request('GET', '/v1/robotics/programs')['programs']
        assert health['status'] == 'ok'
        assert len(programs) == 7
        program = next(program for program in programs if program['id'] == 'precision_assembly')
        assert program['status'] == 'executable'
        evidence['backend_version'] = health['backends']['mujoco']
        evidence['program_statuses'] = {program['id']: program['status'] for program in programs}

        configuration = program['default_configuration']
        resolved = request('POST', '/v1/workspace/configurations/resolve',
                           headers={'X-Workspace-Token': uuid4().hex + uuid4().hex[:8]}, json=configuration)
        world = request('POST', '/v1/worlds', json=resolved['world'])
        world_id = world['id']
        evidence['world_id'] = world_id
        submitted = request('POST', f'/v1/worlds/{world_id}/experiments',
                            json={'candidates': 2, 'max_simulation_seconds': 40})
        experiment_id = submitted['id']
        evidence['experiment_id'] = experiment_id
        print(f'Public experiment {experiment_id} submitted; waiting for measured physics.', flush=True)
        deadline = time.monotonic() + args.timeout_s
        while True:
            experiment = request('GET', f'/v1/experiments/{experiment_id}')
            if experiment['status'] not in ('queued', 'running'):
                break
            if time.monotonic() > deadline:
                evidence['poll_timeout'] = True
                break
            time.sleep(5)
        evidence['experiment_status'] = experiment['status']
        evidence['experiment_error'] = experiment.get('error')
        branches = request('GET', f'/v1/experiments/{experiment_id}/branches')
        evidence['branch_count'] = len(branches)
        evidence['branch_statuses'] = [branch['evaluation']['status'] for branch in branches]
        evidence['branch_physics_steps'] = [branch['performance'].get('simulation_steps') for branch in branches]
        report = request('GET', f'/v1/robotics/experiments/{experiment_id}/report')
        evidence['report_validation_status'] = report['validation_status']
        evidence['selected_branch_id'] = report['selected_branch_id']
        evidence['placement_error_m'] = report['measurements']['evaluation'].get('goal_error_m')
        evidence['world_revision'] = report['world_revision']
        evidence['model_sha256'] = report['solver_configuration']['model_sha256']
        if report['selected_branch_id']:
            replay = request('GET', f'/v1/experiments/{experiment_id}/replay')
            matching = next((branch for branch in replay['branches']
                             if branch['branch_id'] == report['selected_branch_id']), None)
            evidence['replay_frame_count'] = len(matching['frames']) if matching else 0
        evidence['finished_unix_s'] = time.time()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2), flush=True)
    return 0 if (evidence['experiment_status'] == 'completed'
                 and evidence['report_validation_status'] == 'verified'
                 and evidence['branch_count'] >= 2
                 and evidence.get('replay_frame_count', 0) > 1) else 1


if __name__ == '__main__':
    raise SystemExit(main())
