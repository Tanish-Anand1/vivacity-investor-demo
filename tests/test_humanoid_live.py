"""The live-trial transport exposes only committed simulator frames."""

import time

from fastapi.testclient import TestClient

from vivacity.api import create_app
import vivacity.humanoids as humanoids


OWNER = {'X-Workspace-Token': 'humanoid-live-owner-' + 'a' * 40}
OTHER = {'X-Workspace-Token': 'humanoid-live-other-' + 'b' * 40}


def until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.015)
    raise AssertionError('timed out waiting for trial state')


def test_stream_pause_resume_and_persisted_replay(monkeypatch, tmp_path):
    def controlled_simulation(request, *, on_frame, checkpoint):
        frames = []
        for step in range(28):
            checkpoint()
            frame = {'time_s': step * .01, 'phase': 'measured_motion',
                     'qpos': [step], 'contacts': step % 2,
                     'base_position_m': [step * .001, 0., 1.]}
            frames.append(frame)
            on_frame(frame, step)
            time.sleep(.018)
        return {'frames': frames, 'task_success': True, 'robot_id': request.robot_id,
                'model_hash': 'contract-fixture', 'measurements': {'simulation_steps': 28}}

    monkeypatch.setattr(humanoids, 'simulate', controlled_simulation)
    database = tmp_path / 'live.sqlite3'
    with TestClient(create_app(database=database)) as client:
        submitted = client.post('/v1/robotics/humanoids/experiments', headers=OWNER,
                                json={'robot_id': 'unitree_g1', 'action': 'pickup_place'})
        assert submitted.status_code == 202
        trial_id = submitted.json()['id']
        prefix = f'/v1/robotics/humanoids/experiments/{trial_id}'
        def streaming():
            payload = client.get(prefix+'/frames', headers=OWNER).json()
            return payload if len(payload['frames']) >= 4 else None
        live = until(streaming)
        assert live['status'] == 'running'
        assert [entry['seq'] for entry in live['frames']] == list(range(len(live['frames'])))
        assert live['partial_measurements']['base_position_m'][2] == 1.
        assert live['partial_measurements']['contact_count'] in (0, 1)
        assert client.get(prefix+'/frames', headers=OTHER).status_code == 404
        assert client.get(prefix+'/frames?cursor=-1', headers=OWNER).status_code == 422
        paused = client.post(prefix+'/pause', headers=OWNER)
        assert paused.status_code == 200 and paused.json()['status'] == 'paused'
        time.sleep(.07)
        before = client.get(prefix+'/frames', headers=OWNER).json()
        time.sleep(.07)
        after = client.get(prefix+'/frames', headers=OWNER).json()
        assert after['sim_time_s'] == before['sim_time_s']
        assert after['steps_completed'] == before['steps_completed']
        assert client.post(prefix+'/resume', headers=OTHER).status_code == 404
        assert client.post(prefix+'/resume', headers=OWNER).json()['status'] == 'running'
        def finished():
            record = client.get(prefix, headers=OWNER).json()
            return record if record['status'] == 'completed' else None
        completed = until(finished)
        assert completed['result']['task_success']
        frames = client.get(prefix+'/frames?cursor=5&limit=7', headers=OWNER).json()
        assert [entry['seq'] for entry in frames['frames']] == list(range(5, 12))
        assert frames['next_cursor'] == 12
        assert client.get(prefix+'/replay', headers=OWNER).status_code == 200
    with TestClient(create_app(database=database)) as client:
        assert client.get(prefix+'/frames', headers=OWNER).json()['frames']
        assert client.get(prefix, headers=OWNER).json()['status'] == 'completed'


def test_cancelled_trial_retains_partial_frames(monkeypatch, tmp_path):
    def long_simulation(request, *, on_frame, checkpoint):
        for step in range(80):
            checkpoint()
            on_frame({'time_s': step * .01, 'phase': 'moving'}, step)
            time.sleep(.015)
        return {'frames': [], 'task_success': False}

    monkeypatch.setattr(humanoids, 'simulate', long_simulation)
    with TestClient(create_app(database=tmp_path / 'cancel.sqlite3')) as client:
        trial_id = client.post('/v1/robotics/humanoids/experiments', headers=OWNER,
                               json={'robot_id': 'unitree_g1', 'action': 'pickup_place'}).json()['id']
        prefix = f'/v1/robotics/humanoids/experiments/{trial_id}'
        until(lambda: len(client.get(prefix+'/frames', headers=OWNER).json()['frames']) >= 3)
        assert client.post(prefix+'/cancel', headers=OWNER).json()['status'] == 'cancelling'
        def stopped():
            record = client.get(prefix, headers=OWNER).json()
            return record if record['status'] == 'cancelled' else None
        cancelled = until(stopped)
        assert cancelled['result'] is None
        assert client.get(prefix+'/frames', headers=OWNER).json()['frames']
        assert client.get(prefix+'/replay', headers=OWNER).status_code == 409


def test_pause_resume_preserves_real_mujoco_trace(monkeypatch, tmp_path):
    request = humanoids.HumanoidTrialRequest(robot_id='apptronik_apollo', action='service_machine')
    baseline = humanoids.simulate(request)
    actual_simulate = humanoids.simulate

    def paced_simulation(settings, *, on_frame, checkpoint):
        def deliver(frame, steps):
            on_frame(frame, steps)
            time.sleep(.012)  # Slow wall delivery only; never alter MuJoCo state.
        return actual_simulate(settings, on_frame=deliver, checkpoint=checkpoint)

    monkeypatch.setattr(humanoids, 'simulate', paced_simulation)
    with TestClient(create_app(database=tmp_path / 'real-pause.sqlite3')) as client:
        submitted = client.post('/v1/robotics/humanoids/experiments', headers=OWNER,
                                json=request.model_dump())
        assert submitted.status_code == 202
        prefix = f"/v1/robotics/humanoids/experiments/{submitted.json()['id']}"
        until(lambda: len(client.get(prefix+'/frames', headers=OWNER).json()['frames']) >= 4)
        assert client.post(prefix+'/pause', headers=OWNER).json()['status'] == 'paused'
        time.sleep(.07)
        before = client.get(prefix+'/frames', headers=OWNER).json()
        time.sleep(.07)
        after = client.get(prefix+'/frames', headers=OWNER).json()
        assert after['steps_completed'] == before['steps_completed']
        assert after['sim_time_s'] == before['sim_time_s']
        assert client.post(prefix+'/resume', headers=OWNER).json()['status'] == 'running'
        completed = until(lambda: (record if (record := client.get(prefix, headers=OWNER).json())['status'] == 'completed' else None), timeout=5)
        assert completed['result']['task_success']
        assert completed['result']['frames'] == baseline['frames']
        assert completed['result']['final_integration_state'] == baseline['final_integration_state']
