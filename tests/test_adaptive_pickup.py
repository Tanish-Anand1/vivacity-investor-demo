"""Measured adaptive pickup search, including a genuinely impossible scene."""

import time
import pytest

from vivacity.runtime import Runtime
from vivacity.schemas import CreateWorld, ExperimentRequest, RoboticsConfig


def _completed(runtime, experiment_id):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = runtime.get_experiment(experiment_id)
        if result['status'] not in ('queued', 'running'):
            return result
        time.sleep(.05)
    raise AssertionError('adaptive experiment exceeded its test deadline')


@pytest.mark.parametrize('workers',[1,2])
def test_adaptive_search_stops_from_measured_results(tmp_path,monkeypatch,workers):
    monkeypatch.setenv('VIVACITY_PHYSICS_TRIAL_WORKERS',str(workers))
    runtime = Runtime(tmp_path / 'adaptive.sqlite3')
    try:
        world = runtime.create_world(CreateWorld(backend='mujoco', config=RoboticsConfig(
            task='pick_place', obstacle_enabled=False)))
        experiment = runtime.submit(world['id'], ExperimentRequest(
            adaptive_trials=True, search_candidates=32, physics_budget=6,
            max_simulation_seconds=40))
        done = _completed(runtime, experiment['id'])
        assert done['status'] == 'completed', done['error']
        search = done['result']['search']
        assert search['generated'] == search['distinct_generated'] == 32
        assert search['adaptive_stopping']
        assert 1 <= done['performance']['trial_count'] <= 6
        assert search['physics_attempts'] == done['performance']['trial_count']
        assert done['performance']['integrated_trial_count'] > 0
        assert done['performance']['trial_simulation_steps'] > 1000
        assert done['performance']['stopping_reason'] in ('measured_improvement_plateau', 'host_compute_budget')
        if done['performance']['stopping_reason'] == 'measured_improvement_plateau':
            assert done['performance']['trial_count'] < 6
        assert done['selected_branch_id'] is not None
    finally:
        runtime.close()


def test_adaptive_search_reports_unreachable_mount_overlap(tmp_path):
    runtime = Runtime(tmp_path / 'blocked.sqlite3')
    try:
        world = runtime.create_world(CreateWorld(backend='mujoco', config=RoboticsConfig(
            task='pick_place', obstacle_enabled=False, cube_position=[0, 0, .026])))
        experiment = runtime.submit(world['id'], ExperimentRequest(
            adaptive_trials=True, search_candidates=32, physics_budget=6,
            max_simulation_seconds=40))
        done = _completed(runtime, experiment['id'])
        assert done['status'] == 'completed', done['error']
        assert done['selected_branch_id'] is None
        assert done['result']['search']['stopping_reason'] == 'candidate_exhausted'
        assert done['performance']['integrated_trial_count'] == 0
        assert done['performance']['trial_count'] == 1
        assert done['result']['search']['rejection_reasons']['object_not_visible'] == 32
    finally:
        runtime.close()
