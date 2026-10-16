"""Wire contracts for factory clients; simulator-specific fields stay in adapters."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,JsonValue
from .factory import FactorySettings

class Wire(BaseModel):
    model_config=ConfigDict(extra='allow',allow_inf_nan=False)

class BodyTransform(Wire):
    name:str
    position:list[float]=Field(min_length=3,max_length=3)
    quaternion_wxyz:list[float]=Field(min_length=4,max_length=4)

class Carton(Wire):
    id:str
    position_m:list[float]=Field(min_length=3,max_length=3)
    quaternion_wxyz:list[float]=Field(min_length=4,max_length=4)
    linear_velocity_m_s:list[float]=Field(min_length=3,max_length=3)
    angular_velocity_rad_s:list[float]=Field(min_length=3,max_length=3)
    mass_kg:float

class FactoryFrame(Wire):
    schema_version:Literal['vivacity.factory-frame/1.0']
    time:float=Field(ge=0,description='Native MuJoCo simulation time in seconds.')
    qpos:list[float]
    qvel:list[float]
    ctrl:list[float]
    body_transforms:list[BodyTransform]
    cartons:list[Carton]
    carton_half_size_m:float
    end_effector:list[float]
    conveyors:dict[str,dict[str,JsonValue]]
    measurements:dict[str,JsonValue]=Field(description='SI native joint/contact/object data, power and per-step work integrals. See FACTORY_MEASUREMENTS.md. Null means unavailable.')
    source:Literal['mujoco']

class FactoryCellResponse(Wire):
    schema_version:Literal['vivacity.factory-cell/1.0']
    id:str
    created_at:float
    config:FactorySettings
    world_version:str
    engine:dict[str,str]
    initial_state:dict[str,JsonValue]=Field(description='Full mjSTATE_INTEGRATION, model hash, settings, seed and work ledger.')
    frame:FactoryFrame
    last_run_id:str|None
    collision_geometry:list[dict[str,JsonValue]]

class FactoryRunResponse(Wire):
    schema_version:Literal['vivacity.factory-run/1.0']
    id:str
    cell_id:str
    created_at:float
    config:FactorySettings
    world_version:str
    engine:dict[str,str]
    status:Literal['queued','running','paused','completed','failed','stopped','emergency_stopped','interrupted']
    phase:str
    mode:Literal['production','conveyor']
    frame:FactoryFrame
    events:list[dict[str,JsonValue]]
    metrics:dict[str,JsonValue]
    error:str|None

class FactorySamplesResponse(Wire):
    schema_version:Literal['vivacity.factory-samples/1.0']
    run_id:str
    frames:list[FactoryFrame]
    next_index:int
    total_samples:int
    status:str

class DiscoveryMetrics(Wire):
    rmse:float=Field(ge=0)
    mae:float=Field(ge=0)
    r2:float|None

class DiscoveryModelResponse(Wire):
    model:Literal['constant','linear','quadratic','cubic','exponential','sinusoidal','damped_sinusoidal','piecewise_linear']
    validation_status:Literal['validated_approximation','poor_fit']|None=None
    parameters:list[float]
    parameter_count:int
    equation_latex:str
    display_latex:str|None=None
    equation_text:str|None=None
    editable_latex:str
    training:DiscoveryMetrics
    validation:DiscoveryMetrics
    selection_score:float
    predicted_curve:list[list[float]]
    domain_s:list[float]
    origin_s:float
    scale_s:float

class DiscoverySeriesResponse(Wire):
    schema_version:Literal['vivacity.factory-discovery/1.0']
    run_id:str
    quantity:str
    label:str
    unit:str
    x_unit:Literal['s']
    sample_count:int
    train_count:int|None=None
    held_out_count:int|None=None
    status:Literal['insufficient_data','validated_approximation','poor_fit']
    fit_stage:Literal['provisional','final']|None=None
    fit_wall_s:float|None=None
    fit_cpu_s:float|None=None
    source_sample_count:int|None=None
    reason:str
    models:list[DiscoveryModelResponse]
    selected_model:str|None
    updated_at:float
    provenance:dict[str,JsonValue]|None=None

class FactoryDiscoveryResponse(Wire):
    schema_version:Literal['vivacity.factory-discoveries/1.0']
    run_id:str
    sample_count:int
    processing:bool
    series:dict[str,DiscoverySeriesResponse]
    relationships:list['FactoryRelationshipResponse']
    source:str

class FactoryRelationshipResponse(Wire):
    schema_version:Literal['vivacity.factory-relationship/1.0']
    name:str
    run_id:str
    sample_count:int
    updated_at:float
    dependent:dict[str,str]
    independent:list[dict[str,str]]
    provenance:dict[str,JsonValue]
    scope:str
    status:Literal['insufficient_signal','validated_association','poor_fit']
    reason:str
    models:list[dict[str,JsonValue]]
    selected_model:str|None
    train_count:int|None=None
    held_out_count:int|None=None
    baseline_validation_rmse:float|None=None

class FactoryBenchmarkResponse(Wire):
    schema_version:Literal['vivacity.factory-benchmark-record/1.0']
    id:str
    name:str
    created_at:float
    status:str
    phase:str
    cell_id:str
    definition:dict[str,JsonValue]
    request:dict[str,JsonValue]
    trials:list[dict[str,JsonValue]]
    comparison:dict[str,JsonValue]
    error:str|None
    total_trials:int
