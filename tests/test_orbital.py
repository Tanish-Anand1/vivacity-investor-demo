from pathlib import Path
import time

import pytest

from vivacity.schemas import CreateWorld, RoboticsConfig, ExperimentRequest

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/imports/orbital_salvage_lab.zip'


def configure(runtime):
    record = runtime.imports.create('Orbital.zip', FIXTURE.read_bytes())
    with pytest.raises(ValueError, match='verified'):
        runtime.imports.configure_orbital(record['id'], runtime)
    runtime.imports.verify(record['id'], runtime.executor)
    deadline = time.monotonic() + 30
    while runtime.imports.get(record['id'])['status'] == 'physics_verifying':
        assert time.monotonic() < deadline
        time.sleep(.02)
    return runtime.imports.configure_orbital(record['id'], runtime)


def test_imported_orbital_actual_delivery_failure_replan_and_export(runtime):
    record = configure(runtime)
    assert record['physics_ready'] and not record['capabilities']['task_execution_verified']
    world = runtime.get_world(record['configured_world_id'])
    observation = runtime.observe(world['id'])['observation']
    assert observation['import_provenance']['source_sha256'] == record['sha256']
    assert any(g['name']=='obstacle_geom' and g['type']=='cylinder' for g in observation['environment_geometries'])
    assert runtime.imports.configure_orbital(record['id'], runtime)['configured_world_id']==world['id']
    experiment = runtime.wait(runtime.submit(world['id'], ExperimentRequest(candidates=3, execute_selected=True, max_simulation_seconds=40))['id'], timeout=300)
    assert experiment['status']=='completed' and experiment['selected_branch_id'], experiment
    branches = runtime.store.branches(experiment['id'])
    successes = [b for b in branches if b['evaluation']['success']]
    assert successes
    for b in successes:
        e = b['evaluation']
        assert e['grasp_established'] and e['lifted'] and e['retained_during_transport']
        assert e['released'] and e['table_supported'] and not e['contact_violations']
        assert e['goal_error_m'] < .025
    exported = runtime.export_branch(experiment['id'], experiment['selected_branch_id'])
    assert exported['initial_configuration']['source_import_id']==record['id']
    assert exported['recorded_frames'][-1]['import_provenance']['source_sha256']==record['sha256']
    # The actual free cargo moved; its parent state was not edited in place.
    assert successes[0]['initial_state']!=successes[0]['final_state']
    blocked = dict(world['config'], obstacle_position=[.5,0,.2], obstacle_size=[.3,.3,.2])
    runtime.environment(world['id'], RoboticsConfig(**blocked))
    assert runtime.get_experiment(experiment['id'])['stale']
    failed = runtime.wait(runtime.submit(world['id'], ExperimentRequest(candidates=2))['id'], timeout=300)
    assert failed['selected_branch_id'] is None
    assert all(not b['evaluation']['success'] for b in runtime.store.branches(failed['id']))


def test_arbitrary_world_cannot_claim_verified_orbital_provenance(runtime):
    with pytest.raises(KeyError):
        runtime.create_world(CreateWorld(backend='mujoco', config=RoboticsConfig(task='pick_place',scene_profile='orbital_salvage',source_import_id='bad-id',obstacle_size=[.18,.18,.33])))
