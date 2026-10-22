"""Exercise all three nominal tasks in one memory-limited production process.

The Linux workflow runs this file in a fresh Docker container capped at 512 MiB,
matching the current Render Free instance's memory envelope.
"""

import time

from fastapi.testclient import TestClient

from vivacity.api import create_app


OWNER = {'X-Workspace-Token': 'host-memory-humanoid-' + 'a' * 40}
TASKS = (
    {'robot_id': 'unitree_h1', 'action': 'walk_to_goal', 'movement_scale': 1},
    {'robot_id': 'apptronik_apollo', 'action': 'service_machine'},
    {'robot_id': 'unitree_g1', 'action': 'pickup_place', 'movement_scale': 1},
)


def test_all_humanoid_tasks_share_one_host_process(tmp_path):
    with TestClient(create_app(tmp_path / 'humanoids.sqlite3')) as client:
        for task in TASKS:
            submitted = client.post('/v1/robotics/humanoids/experiments', headers=OWNER, json=task)
            assert submitted.status_code == 202, submitted.text
            trial_id = submitted.json()['id']
            prefix = f'/v1/robotics/humanoids/experiments/{trial_id}'
            deadline = time.monotonic() + 90
            while True:
                record = client.get(prefix, headers=OWNER)
                assert record.status_code == 200, record.text
                if record.json()['status'] in ('completed', 'failed', 'cancelled'):
                    break
                assert time.monotonic() < deadline, (task, record.json())
                time.sleep(.05)
            result = record.json()['result']
            assert record.json()['status'] == 'completed', record.json()
            assert result['task_success'], (task, result['failure_reason'])
            assert client.get(prefix + '/frames', headers=OWNER).json()['frames']
            assert client.get(prefix + '/replay', headers=OWNER).status_code == 200
