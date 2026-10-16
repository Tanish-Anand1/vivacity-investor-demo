"""Versioned, bounded configuration interchange. Imported results are never trusted."""
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal
import hashlib
import json
import platform
import mujoco
import numpy
import scipy
import sys
from pydantic import BaseModel, ConfigDict, Field
from .factory import FactorySettings, LAYOUT
from .factory_benchmark import BenchmarkRequest, definition

def digest(value):
    # Reports hash complete trajectories. Preserve the canonical bytes without
    # allocating an additional complete JSON string and UTF-8 copy in memory.
    result=hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(value):
        result.update(chunk.encode())
    return result.hexdigest()

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class Units(Strict):
    length:Literal['m']='m'
    time:Literal['s']='s'
    mass:Literal['kg']='kg'
    angle:Literal['rad']='rad'
    force:Literal['N']='N'
    torque:Literal['N m']='N m'
    energy:Literal['J']='J'
    power:Literal['W']='W'

class Software(Strict):
    engine:Literal['MuJoCo']='MuJoCo'
    engine_version:str
    numpy_version:str
    scipy_version:str
    python_version:str
    controller_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    robot_assets_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    world_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')

@lru_cache(maxsize=1)
def software():
    from .robotics import asset_digest
    # Normalize line endings so Git checkout settings cannot change compatibility.
    source='\n'.join(Path(__file__).with_name(name).read_text(encoding='utf-8') for name in
                     ('factory.py','factory_controller.py','factory_measurements.py','factory_benchmark.py',
                      'robotics.py','pick_place.py','pickup_planning.py','physical_properties.py','headless.py'))
    return Software(engine_version=mujoco.__version__,numpy_version=numpy.__version__,
                    scipy_version=scipy.__version__,python_version=f'{sys.version_info.major}.{sys.version_info.minor}',
                    controller_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    robot_assets_sha256=asset_digest(),world_sha256=digest(LAYOUT)).model_dump()

class Provenance(Strict):
    exported_at:datetime
    source_record_id:str=Field(min_length=1,max_length=80)
    source:Literal['vivacity_backend']='vivacity_backend'
    platform:str=Field(max_length=120)

class Exchange(Strict):
    schema_version:Literal['vivacity.factory-exchange/1.0']='vivacity.factory-exchange/1.0'
    kind:Literal['configuration','benchmark']
    units:Units=Field(default_factory=Units)
    coordinates:Literal['right-handed Z-up; XY horizontal; quaternion wxyz']='right-handed Z-up; XY horizontal; quaternion wxyz'
    software:Software
    world_version:str
    robot:Literal['MuJoCo Menagerie Franka Panda']='MuJoCo Menagerie Franka Panda'
    provenance:Provenance
    configuration:FactorySettings
    initial_state_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    model_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    benchmark_request:BenchmarkRequest|None=None
    benchmark_definition_sha256:str|None=Field(None,pattern=r'^[0-9a-f]{64}$')
    content_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')

METRICS={
    'cartons_sorted':'Count of cartons with verified contact with their mass-selected bin floor.',
    'success_rate':'Completed full-batch trials / all trials in the named condition and partition.',
    'simulation_time_s':'Elapsed MuJoCo integration time, not wall time.',
    'mechanical_work_j':'Integral of summed actuator force times actuator velocity at every physics step.',
    'missing':'null means unavailable, never zero-filled. Electrical energy is not modeled.'}

def configuration_export(cell,benchmark=None):
    value={'kind':'benchmark' if benchmark else 'configuration','software':cell['software'],
           'world_version':cell['world_version'],'provenance':{'exported_at':datetime.now(timezone.utc).isoformat(),
             'source_record_id':benchmark['id'] if benchmark else cell['id'],'platform':platform.system()+' '+platform.machine()},
           'configuration':cell['config'],'initial_state_sha256':digest(cell['initial_state']),
           'model_sha256':cell['initial_state']['model_hash'],
           'benchmark_request':benchmark['request'] if benchmark else None,
           'benchmark_definition_sha256':benchmark['definition']['definition_sha256'] if benchmark else None,
           'content_sha256':'0'*64}
    value=Exchange.model_validate(value).model_dump(mode='json')
    value['content_sha256']=digest({k:v for k,v in value.items() if k!='content_sha256'})
    return value

def validate_import(value,backend):
    value=Exchange.model_validate(value).model_dump(mode='json')
    if value['content_sha256']!=digest({k:v for k,v in value.items() if k!='content_sha256'}):
        raise ValueError('The interchange checksum does not match. Export the file again; edited files must be regenerated.')
    if value['software']!=software() or value['world_version']!=LAYOUT['version']:
        raise ValueError('Incompatible simulator, controller, robot assets or factory version. Use the versions listed in the file.')
    if value['kind']=='benchmark':
        if not value['benchmark_request']:raise ValueError('Benchmark request is missing.')
        expected=definition(value['configuration'],value['benchmark_request'])['definition_sha256']
        if expected!=value['benchmark_definition_sha256']:raise ValueError('Benchmark definition does not match its configuration.')
    elif value['benchmark_request'] is not None or value['benchmark_definition_sha256'] is not None:
        raise ValueError('Configuration files cannot contain benchmark fields.')
    state=backend.snapshot(backend.create_world(value['configuration']))
    if state['model_hash']!=value['model_sha256'] or digest(state)!=value['initial_state_sha256']:
        raise ValueError('Initial state cannot be reproduced on this runtime. No simulation was started.')
    return value
