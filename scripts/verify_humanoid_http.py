"""Exercise all three humanoid trials through a running Vivacity HTTP server.

Run after starting the backend: ``python scripts/verify_humanoid_http.py``.
Each job uses a fresh workspace token, waits for real physics, then verifies the
persisted replay has the exact frames returned by the completed experiment.
"""

from __future__ import annotations

import argparse
import secrets
import time

import httpx


def completed_trial(client: httpx.Client, robot_id: str, movement_scale: float):
    model = client.get(f'/v1/robotics/humanoids/models/{robot_id}')
    model.raise_for_status()
    model = model.json()
    submitted = client.post('/v1/robotics/humanoids/experiments', json={
        'robot_id': robot_id, 'duration_s': 2, 'movement_scale': movement_scale,
        'floor_friction': .8, 'parcel_mass_kg': .5, 'perturbation_n': 0, 'seed': 7,
    })
    submitted.raise_for_status()
    assert submitted.status_code == 202
    trial_id = submitted.json()['id']
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            response = client.get(f'/v1/robotics/humanoids/experiments/{trial_id}')
        except httpx.TransportError:
            # A transient dropped keep-alive connection must not be confused
            # with a failed simulation; the persisted job remains queryable.
            time.sleep(.5)
            continue
        response.raise_for_status()
        trial = response.json()
        if trial['status'] in ('completed', 'failed'):
            break
        time.sleep(.75)
    else:
        raise TimeoutError(f'{robot_id} trial did not finish in 120 seconds')
    if trial['status'] != 'completed':
        raise AssertionError(f'{robot_id} physics worker failed: {trial["error"]}')
    result = trial['result']
    assert result['model_hash'] == model['model_hash']
    assert result['scene_geometry_hash'] == model['model_hash']
    assert result['measurements']['simulation_steps'] >= 400
    replay = client.get(f'/v1/robotics/humanoids/experiments/{trial_id}/replay')
    replay.raise_for_status()
    assert replay.json()['frames'] == result['frames']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    token = secrets.token_urlsafe(32)
    with httpx.Client(base_url=args.base_url, headers={'X-Workspace-Token': token}, timeout=120) as client:
        for robot_id, scale in [('unitree_g1', 1), ('apptronik_apollo', 1), ('unitree_h1', .6)]:
            result = completed_trial(client, robot_id, scale)
            measure = result['measurements']
            print(f'{robot_id}: success={result["task_success"]} '
                  f'reason={result["failure_reason"]} '
                  f'steps={measure["simulation_steps"]} '
                  f'contacts={measure["task_contact_samples"]} '
                  f'compute_s={measure["compute_wall_s"]:.2f} '
                  f'replay_frames={len(result["frames"])}')


if __name__ == '__main__':
    main()
