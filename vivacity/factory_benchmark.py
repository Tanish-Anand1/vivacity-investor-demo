"""A bounded, paired simulation benchmark; not a hardware reliability claim."""
from copy import deepcopy
from typing import Literal
import hashlib
import json
import statistics
import numpy as np
from pydantic import BaseModel,ConfigDict,Field,model_validator
from .factory import FactorySettings,LAYOUT

class ConditionChanges(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    carton_mass_kg:float|None=Field(None,ge=.02,le=.15)
    carton_friction:float|None=Field(None,ge=.05,le=1.5)
    conveyor_speed_m_s:float|None=Field(None,ge=.02,le=.18)
    gripper_force_scale:float|None=Field(None,ge=.005,le=1)

class BenchmarkRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    schema_version:Literal['vivacity.factory-benchmark-request/1.0']='vivacity.factory-benchmark-request/1.0'
    name:str=Field('Contact sorting comparison',min_length=1,max_length=80)
    repeats:int=Field(2,ge=2,le=3)
    held_out_repeats:int=Field(1,ge=1,le=2)
    changes:ConditionChanges

    @model_validator(mode='after')
    def changes_exist(self):
        if not self.changes.model_dump(exclude_none=True):raise ValueError('Change at least one physical condition to compare.')
        return self

def trial_configurations(baseline,request):
    """Matched seeds/held-out offsets across conditions, fixed before execution."""
    request=BenchmarkRequest.model_validate(request);base=FactorySettings.model_validate(baseline).model_dump()
    changed=FactorySettings.model_validate(base|request.changes.model_dump(exclude_none=True)).model_dump()
    trials=[]
    for partition,count in [('training',request.repeats),('held_out',request.held_out_repeats)]:
        for repeat in range(count):
            seed=(base['seed']+repeat+(100003 if partition=='held_out' else 0))%4294967296
            rng=np.random.default_rng(seed)
            offsets=[float(rng.uniform(-.015,.015)),float(rng.uniform(-.035,.035))] if partition=='held_out' else [0.,0.]
            for condition,config in [('baseline',base),('candidate',changed)]:
                value=deepcopy(config);value['seed']=seed
                value['carton_start_x_m']=float(np.clip(value['carton_start_x_m']+offsets[0],.465,.535))
                lower=LAYOUT['infeed']['start_y']+value['carton_half_size_m']+(value['carton_count']-1)*.16
                value['carton_start_y_m']=float(np.clip(value['carton_start_y_m']+offsets[1],max(-1.28,lower),-.35))
                trials.append({'partition':partition,'repeat':repeat,'condition':condition,'config':FactorySettings.model_validate(value).model_dump()})
    return trials

def comparison(trials,expected_repeats=None):
    groups={}
    for partition in ('training','held_out'):
        groups[partition]={}
        for condition in ('baseline','candidate'):
            subset=[r for r in trials if r['partition']==partition and r['condition']==condition]
            successful=[r for r in subset if r['status']=='completed']
            durations=[r['metrics']['simulation_time_s'] for r in successful]
            failures={}
            for r in subset:
                if r['status']!='completed':failures[r['failure_kind']]=failures.get(r['failure_kind'],0)+1
            groups[partition][condition]={'trials':len(subset),'successes':len(successful),
                'success_rate':len(successful)/len(subset) if subset else None,
                'successful_duration_mean_s':statistics.mean(durations) if durations else None,
                'successful_duration_variance_s2':statistics.variance(durations) if len(durations)>1 else None,
                'failures':failures}
    training=groups['training'];a,b=training['baseline'],training['candidate']
    if not a['trials'] or not b['trials'] or (expected_repeats is not None and (a['trials']<expected_repeats or b['trials']<expected_repeats)):selection=None;reason='Training trials have not completed.'
    elif a['successes']==b['successes']==0:selection=None;reason='Neither configuration completed a training trial.'
    else:
        def score(g):return (g['success_rate'],-(g['successful_duration_mean_s'] or float('inf')))
        if score(a)==score(b):selection='tie';reason='Training success rate and mean successful duration are equal.'
        else:selection='baseline' if score(a)>score(b) else 'candidate';reason='Higher training success rate, then shorter mean successful simulation duration.'
    return {'partitions':groups,'selected_condition':selection,'selection_reason':reason,
            'scope':'Small seeded simulation sample. Held-out trials do not change selection. No hardware reliability or statistical significance is inferred.'}

def definition(config,request):
    trials=trial_configurations(config,request)
    value={'schema_version':'vivacity.factory-benchmark/1.0','task':'small_carton_grip_transfer_and_mass_sort',
           'world_version':LAYOUT['version'],'robot':'MuJoCo Menagerie Franka Panda',
           'physics_timestep_s':.002,'trial_configurations':trials,
           'success_criterion':'Every configured carton has bilateral grip, retained lift/transfer, release onto transfer rollers and contact with its mass-selected bin floor; no prohibited robot contact, controller, joint-limit or timeout failure.',
           'selection_criterion':'Training full-batch success rate, then mean successful simulation duration. Ties remain ties; no successes means no selected condition.',
           'held_out_protocol':'Seed offset 100003; matched unseen starting X/Y perturbations up to 15/35 mm, clipped to the supported infeed. Settings frozen before any trial.'}
    value['definition_sha256']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return value
