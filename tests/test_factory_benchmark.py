import time
import pytest
from fastapi.testclient import TestClient
from vivacity.api import create_app
from vivacity.factory import FactorySettings
from vivacity.factory_benchmark import BenchmarkRequest,definition,comparison

TOKEN={'X-Workspace-Token':'benchmark-owner-capability-123456789000'}
OTHER={'X-Workspace-Token':'benchmark-other-capability-123456789000'}
REQUEST={'name':'Grip force intervention','repeats':2,'held_out_repeats':1,'changes':{'gripper_force_scale':.005,'carton_mass_kg':.15,'carton_friction':.05}}

def test_benchmark_definition_is_frozen_paired_and_reproducible():
    base=FactorySettings(carton_count=1,carton_start_y_m=-.4).model_dump()
    a=definition(base,REQUEST);b=definition(base,REQUEST)
    assert a==b and len(a['trial_configurations'])==6
    training=[t for t in a['trial_configurations'] if t['partition']=='training']
    held=[t for t in a['trial_configurations'] if t['partition']=='held_out']
    assert {t['config']['seed'] for t in training}.isdisjoint({t['config']['seed'] for t in held})
    assert held[0]['config']['carton_start_x_m']==held[1]['config']['carton_start_x_m']
    assert held[0]['config']['carton_start_y_m']==held[1]['config']['carton_start_y_m']
    with pytest.raises(ValueError):BenchmarkRequest.model_validate(REQUEST|{'repeats':5000})
    with pytest.raises(ValueError):BenchmarkRequest.model_validate(REQUEST|{'changes':{'fabricated_success':True}})

def test_selection_does_not_use_held_out_outcomes_and_preserves_failure():
    rows=[{'partition':'training','condition':'baseline','status':'failed','failure_kind':'grasp_failure','metrics':{}},
          {'partition':'training','condition':'candidate','status':'failed','failure_kind':'timeout','metrics':{}}]
    assert comparison(rows)['selected_condition'] is None
    rows.append({'partition':'held_out','condition':'candidate','status':'completed','failure_kind':None,'metrics':{'simulation_time_s':10}})
    assert comparison(rows)['selected_condition'] is None
    assert comparison(rows)['partitions']['training']['baseline']['failures']=={'grasp_failure':1}

def test_real_repeated_benchmark_retains_success_failure_and_held_out_records(tmp_path):
    database=tmp_path/'factory.sqlite3'
    with TestClient(create_app(database)) as c:
        cell=c.post('/v1/factory/cells',headers=TOKEN,json={'carton_count':1,'carton_start_y_m':-.4}).json()
        response=c.post('/v1/factory/cells/'+cell['id']+'/benchmarks',headers=TOKEN,json=REQUEST)
        assert response.status_code==202;identifier=response.json()['id'];url='/v1/factory/benchmarks/'+identifier
        assert c.get(url,headers=OTHER).status_code==404
        assert c.post('/v1/factory/cells/'+cell['id']+'/runs',headers=TOKEN,json={}).status_code==429
        assert c.post(url+'/control',headers=TOKEN,json={'action':'pause'}).status_code==200
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if c.get(url,headers=TOKEN).json()['status']=='paused':break
            time.sleep(.05)
        assert c.get(url,headers=TOKEN).json()['status']=='paused'
        c.post(url+'/control',headers=TOKEN,json={'action':'resume'})
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            row=c.get(url,headers=TOKEN).json()
            if row['status'] in ('completed','failed'):break
            time.sleep(.2)
        assert row['status']=='completed',row
        assert len(row['trials'])==6
        assert row['comparison']['selected_condition']=='baseline'
        assert all(t['status']=='completed' for t in row['trials'] if t['condition']=='baseline')
        assert all(t['status']=='failed' for t in row['trials'] if t['condition']=='candidate')
        for trial in row['trials']:
            record=c.get('/v1/factory/runs/'+trial['run_id']+'/record',headers=TOKEN).json()
            assert record['benchmark_id']==identifier and len(record['trace'])>5
            assert record['final_state']!=record['initial_state']
        assert row['worker_cpu_time_s']>0
    with TestClient(create_app(database)) as c:
        assert c.get(url,headers=TOKEN).json()==row

def test_partial_training_cannot_select_a_winner():
    rows=[{'partition':'training','condition':condition,'status':'completed','failure_kind':None,'metrics':{'simulation_time_s':10 if condition=='baseline' else 12}} for condition in ('baseline','candidate')]
    assert comparison(rows,expected_repeats=2)['selected_condition'] is None
