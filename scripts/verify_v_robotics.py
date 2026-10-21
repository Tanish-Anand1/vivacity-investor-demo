r"""Run real V-Robotics acceptance checks and write a machine-readable matrix.

Usage: .\.venv\Scripts\python -m scripts.verify_v_robotics
The output is rebuilt from fresh temporary MuJoCo worlds, never edited to pass.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import mujoco as mj
import numpy as np

from vivacity.runtime import Runtime
from vivacity.schemas import ExperimentRequest
from vivacity.v_robotics import catalog, experiment_report
from vivacity.workspace import WorkspaceService
from vivacity.workspace_schemas import ExperimentConfiguration


def verify():
    start = perf_counter()
    programs = catalog().programs
    matrix = {program.id: {name: 'NOT TESTED' for name in (
        'model_loaded', 'kinematics_verified', 'dynamics_verified', 'controller_verified',
        'task_baseline_passed', 'failure_case_passed', 'parameter_variation_passed',
        'experiment_replay_passed', 'ui_end_to_end_passed')} for program in programs}
    details = {}
    with TemporaryDirectory() as folder:
        runtime = Runtime(Path(folder) / 'verification.sqlite3')
        workspace = WorkspaceService(runtime)
        try:
            baseline = programs[0].default_configuration.model_dump()

            def execute(configuration):
                resolved = workspace.resolve(ExperimentConfiguration.model_validate(configuration), 'v' * 40)
                world = runtime.create_world(resolved.world)
                experiment = runtime.wait(runtime.submit(world['id'], ExperimentRequest(
                    candidates=3, max_simulation_seconds=40))['id'], timeout=180)
                return world, experiment, runtime.store.branches(experiment['id'])

            world, experiment, branches = execute(baseline)
            backend = runtime.backends['mujoco']
            model_world = backend.fork(world['initial_state'])
            model = model_world.model
            selected = next((branch for branch in branches if branch['id'] == experiment['selected_branch_id']), None)
            checks = matrix['precision_assembly']
            checks['model_loaded'] = 'PASS' if (
                model.nu >= 7 and all(model.jnt_limited[:6]) and all(model.body_inertia[1:7].flatten() > 0)
                and model.geom('task_fixture_source_tray_0_0').id >= 0
                and model.geom('task_fixture_0_0').id >= 0) else 'FAIL'
            checks['kinematics_verified'] = 'PASS' if selected and selected['action']['planning_feasible'] and len(selected['action']['stages']) == 8 else 'FAIL'
            checks['dynamics_verified'] = 'PASS' if selected and selected['performance']['simulation_steps'] > 1000 and selected['final_state']['integration_state'][0] > 0 and model.opt.gravity[2] < 0 else 'FAIL'
            checks['controller_verified'] = 'PASS' if selected and selected['evaluation']['grasp_established'] and selected['evaluation']['retained_during_transport'] and selected['evaluation']['released'] else 'FAIL'
            checks['task_baseline_passed'] = 'PASS' if selected and selected['evaluation']['success'] and selected['evaluation']['seated'] and selected['evaluation']['placement_within_tolerance'] else 'FAIL'
            weak = baseline | {'object_mass_kg': .30, 'object_friction': .05,
                               'physics': baseline['physics'] | {'gripper_force_scale': .05}}
            _, failed, failures = execute(weak)
            checks['failure_case_passed'] = 'PASS' if failed['selected_branch_id'] is None and failures and all(
                branch['evaluation']['status'] == 'dropped_object' for branch in failures) else 'FAIL'
            heavier = baseline | {'object_mass_kg': .30}
            heavy_world, varied, varied_branches = execute(heavier)
            heavy_model = backend.fork(heavy_world['initial_state']).model
            checks['parameter_variation_passed'] = 'PASS' if (
                np.isclose(heavy_model.body_mass[heavy_model.body('target').id], .30)
                and np.isclose(model.body_mass[model.body('target').id], .15)
                and varied_branches and any(branch['performance']['simulation_steps'] > 0 for branch in varied_branches)
                and any(branch['evaluation']['peak_actuator_scalar'] != selected['evaluation']['peak_actuator_scalar']
                        for branch in varied_branches)) else 'FAIL'
            replay = runtime.replay(experiment['id'])
            original = backend.fork(selected['initial_state']) if selected else None
            fork = backend.fork(selected['initial_state']) if selected else None
            if fork is not None:
                fork.data.qpos[0] += .1
            independent = original is not None and not np.array_equal(original.data.qpos, fork.data.qpos)
            matching = selected is not None and any(branch['frames'] == selected['trace'] for branch in replay['branches'])
            persisted = selected is not None and runtime.export_branch(experiment['id'], selected['id'])['final_state'] == selected['final_state']
            checks['experiment_replay_passed'] = 'PASS' if independent and matching and persisted else 'FAIL'
            report = experiment_report(runtime, experiment['id'])
            details = {
                'model_source': 'MuJoCo Menagerie UR5e with modeled Panda parallel-jaw flange',
                'solver_version': mj.__version__, 'timestep_s': float(model.opt.timestep),
                'baseline_experiment_id': experiment['id'], 'baseline_branch_count': len(branches),
                'baseline_selected_status': selected['evaluation']['status'] if selected else None,
                'baseline_placement_error_m': selected['evaluation']['goal_error_m'] if selected else None,
                'baseline_physics_steps': sum(branch['performance']['simulation_steps'] or 0 for branch in branches),
                'weak_grip_statuses': [branch['evaluation']['status'] for branch in failures],
                'heavy_mass_kg': float(heavy_model.body_mass[heavy_model.body('target').id]),
                'heavy_experiment_id': varied['id'], 'heavy_branch_statuses': [branch['evaluation']['status'] for branch in varied_branches],
                'report_validation_status': report.validation_status,
                'scope': 'Reproducible local simulator evidence, not hardware validation or cross-version bitwise determinism.',
            }
        finally:
            workspace.close()
            runtime.close()
    return {'schema_version': 'vivacity.v-robotics.verification/1.0',
            'source': 'fresh MuJoCo runs executed by scripts.verify_v_robotics',
            'elapsed_wall_s': perf_counter() - start, 'matrix': matrix,
            'precision_assembly': details,
            'limitations': ['UI end-to-end is verified separately with a browser test.',
                            'Other six programs have no executable task controller and remain NOT TESTED.']}


if __name__ == '__main__':
    output = verify()
    path = Path('docs/v-robotics-verification.json')
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(path), 'matrix': output['matrix'], 'elapsed_wall_s': output['elapsed_wall_s']}, indent=2))
    if any(value == 'FAIL' for value in output['matrix']['precision_assembly'].values()):
        raise SystemExit(1)
