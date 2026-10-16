"""Deterministic physical conditions and measured, partitioned robustness reports."""
from copy import deepcopy
import math
import numpy as np
from .schemas import RoboticsConfig


def conditions(config, seed, cycle, total, settings):
    result=deepcopy(config)
    held_out=max(1,math.ceil((total-1)*settings['held_out_fraction']))
    partition='baseline' if cycle==0 else 'held_out' if cycle>=total-held_out else 'training'
    if cycle:
        rng=np.random.default_rng(seed)
        half=(result.get('cube_half_sizes') or [result.get('cube_half_size',.025)]*3)
        radius=settings['position_radius_m']
        for _ in range(32):
            for key in ('cube_position','placement_position'):
                base=config[key];result[key]=[float(base[0]+rng.uniform(-radius,radius)),float(base[1]+rng.uniform(-radius,radius)),half[2]+.001]
            result.update(cube_mass=float(rng.uniform(settings['mass_min_kg'],settings['mass_max_kg'])),
                          cube_friction=float(rng.uniform(settings['friction_min'],settings['friction_max'])),object_material='custom')
            try:RoboticsConfig.model_validate(result);break
            except ValueError:continue
        else:raise ValueError('could not sample a valid physical configuration inside the requested bounds')
    return result,partition


def report(experiments, recorded_conditions):
    rows=[]
    for experiment,branches in experiments:
        metadata=next((c for c in recorded_conditions if c['world_id']==experiment['world_id']),{})
        selected=next((b for b in branches if b['id']==experiment.get('selected_branch_id')),None)
        fresh=experiment.get('result',{}).get('execution_evaluation')
        evaluation=fresh or (selected or {}).get('evaluation') or (branches[0].get('evaluation') if branches else None)
        if not evaluation or experiment['status']!='completed':continue
        config=experiment['config']
        rows.append({'experiment_id':experiment['id'],'world_id':experiment['world_id'],'seed':metadata.get('seed'),
            'partition':metadata.get('partition','unpartitioned'),'configuration_sha256':metadata.get('configuration_sha256'),
            'conditions':{'object_position_m':config.get('cube_position'),'placement_position_m':config.get('placement_position'),
                          'mass_kg':config.get('cube_mass'),'friction':config.get('cube_friction')},
            'success':bool(evaluation.get('success')),'status':evaluation.get('status'),
            'goal_error_m':evaluation.get('goal_error_m'),'execution_duration_s':evaluation.get('execution_duration_s'),
            'collision_events':len(evaluation.get('contact_violations',[])),
            'evaluation_source':'fresh authoritative execution' if fresh else 'selected validation branch' if selected else 'failed validation branch; no feasible selection'})
    partitions={}
    for name in ('baseline','training','held_out','unpartitioned'):
        subset=[row for row in rows if row['partition']==name]
        if subset:
            passed=sum(row['success'] for row in subset)
            partitions[name]={'completed_configurations':len(subset),'successes':passed,'failures':len(subset)-passed,
                              'success_rate':passed/len(subset),'failure_rate':1-passed/len(subset)}
    failures=[row for row in rows if not row['success']]
    return {'schema_version':'vivacity.robustness/1.0','partitions':partitions,'configurations':rows,'failure_regions':failures,
            'recommended_next_experiments':[{'around_configuration_sha256':row['configuration_sha256'],'conditions':row['conditions'],
                'reason':'repeat this measured failure and vary one physical input at a time'} for row in failures[:3]],
            'scope':'Seeded simulated conditions, with replanning on each configuration. Held-out seeds are assigned before execution. Small-sample descriptive rates, not hardware predictive accuracy or a trained-policy benchmark.',
            'hardware_validation':'not performed','unrandomized':['orientation','clutter','initial joints','lighting','camera','object geometry']}
