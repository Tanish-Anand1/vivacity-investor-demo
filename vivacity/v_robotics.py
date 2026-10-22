"""V-Robotics program boundary over the existing measured MuJoCo runtime.

Only a program with a tested task controller is executable. Catalogue entries
for the remaining research targets cannot create worlds or imply task success.
"""
from typing import Literal

import mujoco as mj
from .schemas import Schema, AssemblySettings
from .workspace_schemas import ExperimentConfiguration


class RoboticsProgram(Schema):
    id: str
    category: Literal['robotic_arms', 'humanoids']
    name: str
    robot_type: str
    environment_id: str
    task_id: str
    status: Literal['executable', 'not_implemented']
    scope: str
    missing_capability: str | None = None
    default_configuration: ExperimentConfiguration | None = None


class RoboticsProgramCatalog(Schema):
    schema_version: Literal['vivacity.v-robotics.catalog/1.0'] = 'vivacity.v-robotics.catalog/1.0'
    coordinate_system: Literal['right_handed_z_up'] = 'right_handed_z_up'
    units: Literal['SI'] = 'SI'
    programs: list[RoboticsProgram]


class RoboticsExperimentReport(Schema):
    schema_version: Literal['vivacity.v-robotics.report/1.0'] = 'vivacity.v-robotics.report/1.0'
    experiment_id: str
    program_id: Literal['precision_assembly']
    robot_id: str
    environment_id: str
    task_id: str
    world_id: str
    world_revision: int
    controller_version: str
    solver_configuration: dict
    random_seed: int
    parameters: dict
    initial_state: dict
    terminal_state: dict | None
    termination_reason: str | None
    measurements: dict
    constraint_violations: list[dict]
    events: list[dict]
    branch_ids: list[str]
    selected_branch_id: str | None
    replay_path: str
    export_path: str | None
    validation_status: Literal['verified', 'failed', 'incomplete']
    stale: bool
    error: str | None = None


def catalog() -> RoboticsProgramCatalog:
    # The UR5e source is MuJoCo Menagerie. Its Panda parallel-jaw flange is a
    # modeled simulation fixture, not a UR manufacturer-approved end effector.
    baseline = ExperimentConfiguration(
        name='V-Robotics / Precision assembly', environment_id='desktop',
        robot_id='ur5e', gripper_id='panda_parallel', operation_id='assembly',
        program_id='precision_assembly', assembly=AssemblySettings(),
        target_position=[.5, -.15, .026], destination_position=[.5, .18, .026],
        object_mass_kg=.15, trial_mode='fixed', validation_trials=3,
    )
    records = [
        RoboticsProgram(id='precision_assembly', category='robotic_arms', name='Precision assembly',
                        robot_type='Six-axis UR5e with modeled parallel-jaw flange', environment_id='desktop',
                        task_id='single_part_fixture_seating', status='executable',
                        scope='Contact-driven pickup, transfer, release and seating in a passive fixture. No fastening or physical-robot validation.',
                        default_configuration=baseline),
        RoboticsProgram(id='heavy_payload', category='robotic_arms', name='Heavy payload handling',
                        robot_type='High-payload six-axis manipulator', environment_id='heavy_industrial_cell',
                        task_id='payload_transfer', status='not_implemented',
                        scope='Research target, not an executable experiment.',
                        missing_capability='Validated high-payload model, grasp/attachment and effort-limited transfer controller.'),
        RoboticsProgram(id='high_speed_sorting', category='robotic_arms', name='High-speed sorting',
                        robot_type='Delta or validated high-speed sorting arm', environment_id='conveyor_sorting_cell',
                        task_id='moving_object_sort', status='not_implemented',
                        scope='The existing factory carton cell is separate and does not validate a delta-arm sorter.',
                        missing_capability='Moving-object interception, compatible arm model and repeated physical bin placement.'),
        RoboticsProgram(id='collaborative_manipulation', category='robotic_arms', name='Collaborative manipulation',
                        robot_type='Lightweight articulated arm', environment_id='collaborative_workcell',
                        task_id='clearance_constrained_transfer', status='not_implemented',
                        scope='Existing obstacle-aware pickup is a component, not a certified collaborative workflow.',
                        missing_capability='Explicit minimum-clearance enforcement, moving-obstacle handling and planner comparison.'),
        RoboticsProgram(id='humanoid_maintenance', category='humanoids', name='Industrial maintenance',
                        robot_type='Apptronik Apollo · 32 actuators', environment_id='industrial_maintenance',
                        task_id='operate_constrained_switch', status='not_implemented',
                        scope='Full-body model, 3D cabinet and joint-driven reach probe are available. Switch actuation is measured but not yet validated.',
                        missing_capability='Reliable hand contact and switch actuation while maintaining balance.'),
        RoboticsProgram(id='humanoid_terrain', category='humanoids', name='Terrain mobility',
                        robot_type='Unitree H1 · 19 actuators', environment_id='terrain_mobility',
                        task_id='terrain_traversal', status='not_implemented',
                        scope='Full-body model, collision course and joint-driven gait probe are available. Falls and slips are measured.',
                        missing_capability='Stable feedback locomotion over ramps, steps and uneven terrain.'),
        RoboticsProgram(id='humanoid_logistics', category='humanoids', name='Warehouse logistics',
                        robot_type='Unitree G1 with hands · 43 actuators', environment_id='warehouse_logistics',
                        task_id='parcel_navigation_and_place', status='not_implemented',
                        scope='A separate stationary G1 parcel pickup-and-placement trial executes in MuJoCo with measured bilateral contact, a documented rigid-grasp constraint and destination support. Full warehouse logistics is not validated.',
                        missing_capability='Validated walking/carrying controller and same-world handoff from the sorting arm to the humanoid.'),
    ]
    return RoboticsProgramCatalog(programs=records)


def experiment_report(runtime, experiment_id: str) -> RoboticsExperimentReport:
    public = runtime.get_experiment(experiment_id)
    saved = runtime.store.get('experiments', experiment_id)
    config = saved['config']
    if config.get('program_id') != 'precision_assembly':
        raise ValueError('this experiment is not a V-Robotics precision-assembly run')
    branches = runtime.store.branches(experiment_id)
    selected = next((branch for branch in branches if branch['id'] == public['selected_branch_id']), None)
    backend = runtime.backends[saved['backend']]
    instance = backend.fork(saved['snapshot'])
    model = instance.model
    evaluation = (selected or (branches[0] if branches else {})).get('evaluation', {})
    fresh = public.get('result', {}).get('execution_evaluation')
    verified = public['status'] == 'completed' and bool(evaluation.get('success')) and (fresh is None or fresh.get('success'))
    status = ('verified' if verified else 'failed' if public['status'] == 'completed' else 'incomplete')
    return RoboticsExperimentReport(
        experiment_id=experiment_id, program_id='precision_assembly', robot_id=config['robot_model'],
        environment_id=(config.get('environment') or {}).get('id', 'desktop'),
        task_id='single_part_fixture_seating', world_id=public['world_id'], world_revision=saved['revision'],
        controller_version='staged-dls-rrt-contact/1.0',
        solver_configuration={'backend': saved['backend'], 'version': backend.version,
            'model_sha256': saved['snapshot']['model_hash'], 'timestep_s': float(model.opt.timestep),
            'integrator': mj.mjtIntegrator(int(model.opt.integrator)).name,
            'solver': mj.mjtSolver(int(model.opt.solver)).name,
            'iterations': int(model.opt.iterations), 'tolerance': float(model.opt.tolerance),
            'gravity_m_s2': model.opt.gravity.tolist(), 'state_dtype': str(instance.data.qpos.dtype)},
        random_seed=saved['snapshot']['seed'], parameters=config, initial_state=saved['snapshot'],
        terminal_state=selected['final_state'] if selected else None,
        termination_reason=evaluation.get('status') or public.get('error') or public['status'],
        measurements={'evaluation': evaluation, 'performance': (selected or (branches[0] if branches else {})).get('performance', {}),
                      'fresh_execution': fresh,
                      'candidate_evaluations': [{'branch_id':branch['id'], 'evaluation':branch['evaluation'],
                                                 'performance':branch['performance']} for branch in branches]},
        constraint_violations=[violation for branch in branches for violation in branch['evaluation'].get('contact_violations', [])],
        events=runtime.store.events(experiment_id, 0), branch_ids=[branch['id'] for branch in branches],
        selected_branch_id=public['selected_branch_id'],
        replay_path=f'/v1/experiments/{experiment_id}/replay',
        export_path=f'/v1/experiments/{experiment_id}/branches/{selected["id"]}/export' if selected else None,
        validation_status=status, stale=public['stale'], error=public['error'],
    )
