from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]
ScenePosition = Annotated[list[Annotated[float,Field(ge=-8,le=8)]],Field(min_length=3,max_length=3)]
SceneSize = Annotated[list[Annotated[float,Field(ge=.005,le=8)]],Field(min_length=3,max_length=3)]


class StaticGeometry(Schema):
    name: str = Field(min_length=1, max_length=60, pattern=r'^[A-Za-z][A-Za-z0-9_-]*$')
    type: Literal['box', 'cylinder'] = 'box'
    position: ScenePosition
    size: SceneSize
    rgba: Annotated[list[float], Field(min_length=4, max_length=4)] = [.4, .45, .5, 1.]
    friction: float = Field(.8, ge=.05, le=2.)

    @model_validator(mode='after')
    def bounded_geometry(self):
        if any(abs(v) > 8 for v in self.position) or any(not .005 <= v <= 8 for v in self.size):
            raise ValueError('static geometry exceeds the 16 m scene bounds')
        if any(not 0 <= v <= 1 for v in self.rgba) or self.rgba[3] != 1:
            raise ValueError('collision geometry requires opaque RGBA values in 0..1')
        return self


class EnvironmentProvenance(Schema):
    id: str = Field(max_length=80)
    name: str = Field(max_length=100)
    version: int = Field(1, ge=1)
    source: Literal['prebuilt', 'openai', 'worldlabs', 'imported']
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    collision_scope: str = Field(max_length=400)


class SortingRule(Schema):
    property: Literal['mass','width'] = 'mass'
    threshold: float = Field(.08, ge=.01, le=.2)


MaterialId = Literal['custom', 'steel', 'aluminium', 'rubber', 'wood', 'plastic', 'glass', 'concrete', 'cardboard']


class PhysicsSettings(Schema):
    schema_version: Literal['vivacity.physics/1.0'] = 'vivacity.physics/1.0'
    gravity_m_s2: float = Field(9.81, ge=0., le=20.)
    air_density_kg_m3: float = Field(0., ge=0., le=5.)
    air_viscosity_pa_s: float = Field(0., ge=0., le=.001)
    wind_velocity_m_s: Vec3 = [0., 0., 0.]
    blunt_drag_coefficient: float = Field(.5, ge=0., le=3.)
    contact_damping_ratio: float = Field(1., ge=.2, le=1.)
    gripper_force_scale: float = Field(1., ge=.05, le=1.)
    object_force_n: Vec3 = [0., 0., 0.]
    object_torque_nm: Vec3 = [0., 0., 0.]

    @model_validator(mode='after')
    def bounded_inputs(self):
        if any(abs(v)>20. for v in self.wind_velocity_m_s):
            raise ValueError('wind components must be within ±20 m/s')
        if any(abs(v)>2. for v in self.object_force_n) or any(abs(v)>.2 for v in self.object_torque_nm):
            raise ValueError('object forces must be within ±2 N; torques within ±0.2 Nm')
        return self


class RoboticsConfig(Schema):
    physics: PhysicsSettings = PhysicsSettings()
    object_material: MaterialId = 'custom'
    robot_model: Literal['panda','ur5e','iiwa','gen3','xarm7','scara','dual_arm'] = 'panda'
    physical_operation: Literal['pick_place','sorting','assembly','stacking','insertion','machine_tending'] = 'pick_place'
    sorting_rule: SortingRule | None = None
    task: Literal['reach', 'pick_place'] = 'reach'
    scene_profile: Literal['workcell', 'orbital_salvage'] = 'workcell'
    source_import_id: str | None = None
    obstacle_enabled: bool = True
    cube_position: Vec3 = [0.5, -0.15, 0.026]
    placement_position: Vec3 = [0.5, 0.18, 0.026]
    cube_half_size: float = Field(0.025, ge=0.02, le=0.03)
    cube_half_sizes: Vec3 | None = None
    cube_mass: float = Field(0.06, ge=0.02, le=0.15)
    cube_friction: float = Field(1.0, ge=0.05, le=1.5)
    obstacle_position: Vec3 = [0.45, 0.04, 0.22]
    obstacle_size: Vec3 = [0.055, 0.13, 0.22]
    target_position: Vec3 = [0.55, 0.28, 0.22]
    scene_geometries: Annotated[list[StaticGeometry], Field(max_length=24)] = []
    environment: EnvironmentProvenance | None = None

    @model_validator(mode='after')
    def bounds(self):
        if self.physical_operation=='sorting' and self.sorting_rule is None:
            raise ValueError('sorting requires a bounded physical-property classification rule')
        if len({g.name for g in self.scene_geometries}) != len(self.scene_geometries):
            raise ValueError('static geometry names must be unique')
        half_sizes = self.cube_half_sizes or [self.cube_half_size] * 3
        if any(not 0.02 <= half <= 0.03 for half in half_sizes):
            raise ValueError('object half-dimensions must be 0.02..0.03 m')
        if self.scene_profile == 'orbital_salvage':
            if self.robot_model!='panda' or self.physical_operation!='pick_place':raise ValueError('Orbital fixture currently uses Panda pickup only')
            if self.task != 'pick_place' or not self.source_import_id:
                raise ValueError('Orbital task requires pickup and a verified source import')
            if abs(self.obstacle_size[0]-self.obstacle_size[1]) > 1e-8:
                raise ValueError('reactor radial half-sizes must match')
            if abs(self.cube_half_size - .025) > 1e-9:
                raise ValueError('Orbital cargo geometry is fixed by its adapted source fixture')
            if self.cube_half_sizes is not None:
                raise ValueError('Orbital cargo dimensions are fixed by its adapted source fixture')
        for index,point in enumerate((self.cube_position, self.placement_position)):
            if self.task == 'pick_place' and self.scene_profile == 'workcell':
                inside = (-.3 + half_sizes[0] + .001 <= point[0] <= 1.1 - half_sizes[0] - .001
                          and -.65 + half_sizes[1] + .001 <= point[1] <= .65 - half_sizes[1] - .001)
            else:
                inside = .15 <= point[0] <= .8 and abs(point[1]) <= .45
            z_ok=.02 <= point[2] <= .032 if not (index==1 and self.physical_operation=='stacking') else abs(point[2]-(3*half_sizes[2]+.001))<=.002
            if not (inside and z_ok):
                raise ValueError('pickup and placement centers must be on the supported table workspace')
        if self.task == 'pick_place' and any(abs(point[2] - ((3 if index==1 and self.physical_operation=='stacking' else 1)*half_sizes[2] + .001)) > .002 for index,point in enumerate((self.cube_position, self.placement_position))):
            raise ValueError('pickup and placement center heights must match the cube size')
        # Coordinates supplied by range controls are binary floats. Accept the
        # exact 10 cm boundary despite harmless representation error.
        if self.task == 'pick_place' and sum((a-b)**2 for a,b in zip(self.cube_position[:2], self.placement_position[:2])) < (.1 - 1e-9)**2:
            raise ValueError('pickup and placement must be at least 0.1 m apart')
        x, y, z = self.obstacle_position
        if not (0.15 <= x <= 0.8 and -0.5 <= y <= 0.5 and 0.05 <= z <= 0.6):
            raise ValueError('obstacle outside workcell bounds')
        if not all(0.01 <= v <= 0.4 for v in self.obstacle_size):
            raise ValueError('obstacle half-sizes must be 0.01..0.4 m')
        if not (0.15 <= self.target_position[0] <= 0.8 and abs(self.target_position[1]) <= 0.5 and 0.1 <= self.target_position[2] <= 0.7):
            raise ValueError('target outside workcell bounds')
        return self


class ClothConfig(Schema):
    robot_model: Literal['panda'] = 'panda'
    side_length: float = Field(.4,ge=.3,le=.5)
    mass: float = Field(.08,ge=.03,le=.2)
    friction: float = Field(.6,ge=.1,le=1.5)


class ScienceConfig(Schema):
    """Bounded, nondimensional 2D gravitational observation experiment."""
    central_mu: float = Field(1., ge=.7, le=1.3)
    hidden_mass: float = Field(.12, ge=0., le=.3)
    perturbing_position: Annotated[list[float], Field(min_length=2, max_length=2)] = [2.5, .4]
    initial_state: Annotated[list[float], Field(min_length=4, max_length=4)] = [1., 0., 0., 1.]
    noise_std: float = Field(.001, ge=.00001, le=.05)
    samples: int = Field(70, ge=30, le=200)
    horizon: float = Field(5., ge=2., le=8.)
    train_fraction: float = Field(.7, ge=.5, le=.85)

    @model_validator(mode='after')
    def bounds(self):
        import math
        radius = math.hypot(*self.perturbing_position)
        initial_radius = math.hypot(*self.initial_state[:2])
        initial_speed = math.hypot(*self.initial_state[2:])
        if not 2. <= radius <= 5.:
            raise ValueError('fixed perturber radius must be 2..5')
        if not .8 <= initial_radius <= 1.2:
            raise ValueError('initial orbital radius must be .8..1.2')
        if not .85 <= initial_speed <= 1.15:
            raise ValueError('initial orbital speed must be .85..1.15')
        return self


class CreateWorld(Schema):
    schema_version: Literal['1.0'] = '1.0'
    backend: Literal['mujoco', 'scipy', 'cloth']
    seed: int = Field(7, ge=0, le=2**32-1)
    config: RoboticsConfig | ScienceConfig | ClothConfig | None = None

    @model_validator(mode='after')
    def matching_config(self):
        expected = {'mujoco':RoboticsConfig,'scipy':ScienceConfig,'cloth':ClothConfig}[self.backend]
        if self.config is None:
            self.config = expected()
        if not isinstance(self.config, expected):
            raise ValueError('config does not match backend')
        return self


class ExperimentRequest(Schema):
    realtime_speed: float = Field(1., ge=.25, le=4.)
    physics_trials: int = Field(0, ge=0, le=5000)
    adaptive_trials: bool = False
    execute_selected: bool = False
    realtime_execution: bool = False
    candidates: int = Field(3, ge=2, le=5)
    planner_iterations: int = Field(1500, ge=100, le=4000)
    max_simulation_seconds: float = Field(25, ge=0.1, le=40)
    policy: Literal['deterministic', 'llm'] = 'deterministic'
    search_candidates: int = Field(0, ge=0, le=10000)
    physics_budget: int = Field(12, ge=3, le=24)

    @model_validator(mode='after')
    def trial_count_matches_generation(self):
        if self.physics_trials and self.physics_trials != self.search_candidates:
            raise ValueError('full physics trials require matching search_candidates')
        if self.adaptive_trials and (self.physics_trials or not self.search_candidates):
            raise ValueError('adaptive trials require search candidates and no fixed trial count')
        return self


class HostedProposal(Schema):
    candidates: int = Field(ge=2, le=5)
    planner_iterations: int = Field(ge=100, le=4000)


class EnvironmentPatch(Schema):
    config: RoboticsConfig | ScienceConfig | ClothConfig


class CommitRequest(Schema):
    experiment_id: str
    branch_id: str


class ImportResponse(Schema):
    schema_version: Literal['vivacity.import/1.0']='vivacity.import/1.0'
    id: str
    filename: str
    entrypoint: str
    format: str
    status: Literal['visual_only','configuration_required','physics_verifying','physics_valid','actuation_verified','physics_failed','manipulation_configured']
    physics_ready: bool=False
    preview_available: bool
    sha256: str
    uploaded_bytes: int
    created_unix_s: float
    summary: dict
    diagnostics: list[str]
    readiness: list[str]=[]
    capabilities: dict | None=None
    configured_world_id: str | None=None


class ImportPreview(Schema):
    source_bounds_m: list[Vec3] | None = None
    positions: list[Vec3]
    indices: list[int]
    vertex_count: int
    triangle_count: int
    coordinate_system: str


class WorldResponse(Schema):
    schema_version: Literal['1.0'] = '1.0'
    id: str
    backend: str
    config: dict
    state: dict
    initial_state: dict
    action_schema: dict
    simulator_version: str
    seed: int
    revision: int
    history: list[str]
    branches: list[dict]
    evaluations: list[dict]
    performance: dict


class ExperimentResponse(Schema):
    schema_version: Literal['1.0'] = '1.0'
    id: str
    world_id: str
    revision: int
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled']
    request: dict
    selected_branch_id: str | None = None
    result: dict = {}
    performance: dict = {}
    error: str | None = None
    stale: bool = False


class BranchResponse(Schema):
    schema_version: Literal['1.0'] = '1.0'
    id: str
    experiment_id: str
    parent_state_reference: str
    initial_state: dict
    action: dict
    trace: list[dict]
    final_state: dict | None
    evaluation: dict
    performance: dict


class TrialResponse(Schema):
    schema_version: Literal['vivacity.trial/1.0'] = 'vivacity.trial/1.0'
    completion_seq: int
    candidate_index: int
    parent_state_reference: str
    action: dict
    engine: str
    control_sha256: str
    final_state: dict
    evaluation: dict
    performance: dict


class TrialsResponse(Schema):
    schema_version: Literal['vivacity.trials/1.0'] = 'vivacity.trials/1.0'
    completed: int
    items: list[TrialResponse]
    next_after: int | None


class StateResponse(Schema):
    schema_version: Literal['1.0'] = '1.0'
    world_id: str
    revision: int
    observation: dict


class ReplayResponse(Schema):
    schema_version: Literal['1.0'] = '1.0'
    experiment_id: str
    backend: str
    config: dict
    stale: bool
    branches: list[dict]


class EventResponse(Schema):
    schema_version: Literal['1.0'] = '1.0'
    seq: int
    kind: Literal['queued', 'running', 'planned', 'progress', 'branch_completed', 'completed', 'failed', 'cancelled']
    details: dict


class BranchExport(Schema):
    schema_version: Literal['vivacity.branch/1.0'] = 'vivacity.branch/1.0'
    experiment_id: str
    branch_id: str
    world_type: str
    simulation_backend: str
    simulator_version: str
    initial_configuration: dict
    initial_state_reference: str
    state_encoding: str
    initial_state: dict
    final_state: dict | None
    action: dict
    recorded_frames: list[dict]
    evaluation: dict
    constraint_violations: list[dict]
    success: bool
    seed: int
    configuration_sha256: str
    model_hash: str | None
    timestamps: dict
    performance: dict


class VariationSettings(Schema):
    enabled: bool = False
    position_radius_m: float = Field(.04,ge=0,le=.08)
    friction_min: float = Field(.15,ge=.05,le=1.5)
    friction_max: float = Field(1.2,ge=.05,le=1.5)
    mass_min_kg: float = Field(.04,ge=.02,le=.15)
    mass_max_kg: float = Field(.10,ge=.02,le=.15)
    held_out_fraction: float = Field(.25,ge=.2,le=.5)

    @model_validator(mode='after')
    def ranges(self):
        if self.friction_min>self.friction_max or self.mass_min_kg>self.mass_max_kg:
            raise ValueError('variation minimum must not exceed maximum')
        return self


class SessionRequest(CreateWorld):
    variation: VariationSettings = VariationSettings()
    realtime_speed: float = Field(1., ge=.25, le=4.)
    physics_trials: int = Field(0, ge=0, le=5000)
    adaptive_trials: bool = False
    max_cycles: int = Field(4, ge=1, le=8)
    realtime_execution: bool = True
    search_candidates: int = Field(0, ge=0, le=10000)
    physics_budget: int = Field(3, ge=3, le=12)

    @model_validator(mode='after')
    def trial_backend(self):
        if self.variation.enabled and (self.backend!='mujoco' or self.config.task!='pick_place' or self.config.physical_operation!='pick_place' or self.max_cycles<3):
            raise ValueError('physical variation requires pick-and-place and at least three cycles for baseline/training/held-out')
        if self.physics_trials and (self.backend!='mujoco' or self.config.task!='pick_place' or self.physics_trials!=self.search_candidates):
            raise ValueError('full physics trials require Panda pickup and matching search_candidates')
        if self.adaptive_trials and (self.backend!='mujoco' or self.config.task!='pick_place' or self.physics_trials or not self.search_candidates):
            raise ValueError('adaptive trials require Panda pickup, search candidates and no fixed trial count')
        return self


class SessionResponse(Schema):
    pause_requested: bool = False
    paused: bool = False
    paused_seconds: float = 0.
    schema_version: Literal['vivacity.session/1.0'] = 'vivacity.session/1.0'
    id: str
    backend: str
    status: Literal['active', 'stopping', 'stopped', 'completed', 'failed']
    world_id: str
    experiment_id: str | None = None
    cycle: int
    max_cycles: int
    experiments: list[str]
    world_ids: list[str]
    error: str | None = None
    started_unix_s: float
    last_heartbeat_unix_s: float
    conditions: list[dict]


class LiveState(Schema):
    schema_version: Literal['vivacity.live/1.0'] = 'vivacity.live/1.0'
    experiment_id: str
    world_id: str
    sequence: int
    timestamp_unix_s: float
    stage: str
    frame: dict
