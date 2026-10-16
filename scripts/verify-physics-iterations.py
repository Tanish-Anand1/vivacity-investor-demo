"""Execute and audit 5,000 independent real MuJoCo trials, never a counter loop.

Run: .venv/Scripts/python.exe scripts/verify-physics-iterations.py
The SQLite database contains each command, measured evaluation and final full
integration state. Only the best trajectories retain complete replay frames.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import platform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vivacity.runtime import Runtime
from vivacity.schemas import CreateWorld, ExperimentRequest
from vivacity.storage import encode


def main():
    root=Path(__file__).resolve().parents[1]
    database=root/'data/run/physics-5000.sqlite3'
    output=root/'artifacts/physics-5000.json'
    started=time.perf_counter()
    r=Runtime(database)
    try:
        world=r.create_world(CreateWorld(backend='mujoco',seed=7,
            config={'task':'pick_place','obstacle_enabled':False}))
        parent_hash=hashlib.sha256(encode(world['state']).encode()).hexdigest()
        e=r.submit(world['id'],ExperimentRequest(physics_trials=5000,search_candidates=5000,
            execute_selected=True,max_simulation_seconds=40))
        print(json.dumps({'started':True,'experiment_id':e['id'],'database':str(database)}),flush=True)
        last=-1
        while e['status'] in ('queued','running'):
            search=e['result'].get('search',{})
            completed=search.get('fully_simulated',0)
            if completed//100!=last:
                last=completed//100
                print(json.dumps({'actual_trials':completed,'steps':search.get('trial_simulation_steps',0),
                    'elapsed_seconds':round(time.perf_counter()-started,2)}),flush=True)
            time.sleep(1)
            e=r.get_experiment(e['id'])
        records=[];after=-1
        while True:
            page=r.store.trials(e['id'],after,100)
            if not page['items']:break
            records.extend(page['items']);after=page['next_after']
        assert e['status']=='completed',e
        assert len(records)==5000 and {x['candidate_index'] for x in records}==set(range(5000))
        assert len({x['control_sha256'] for x in records})==5000
        assert all(x['performance']['simulation_steps']>0 for x in records)
        assert all(x['final_state']['integration_state'] for x in records)
        assert len({x['parent_state_reference'] for x in records})==1
        assert parent_hash==hashlib.sha256(encode(r.get_world(world['id'])['initial_state']).encode()).hexdigest()
        assert sum(x['performance']['simulation_steps'] for x in records)==e['performance']['trial_simulation_steps']
        assert e['result']['execution_evaluation']['success'],e
        chosen=r.store.get('branches',e['selected_branch_id'])
        from vivacity.native_pick_place import NativePickup
        engine=NativePickup(r.backends['mujoco'].pick_place,world['state'])
        result,evaluation,final=engine.simulate(chosen['action'],{'max_simulation_seconds':40})
        assert final==chosen['final_state'] and evaluation==chosen['evaluation']
        proof={'status':'passed','experiment_id':e['id'],'world_id':world['id'],'seed':7,
            'python':platform.python_version(),'mujoco':r.backends['mujoco'].version,
            'database':str(database),'actual_trials':len(records),'distinct_commands':5000,
            'positive_step_trials':sum(x['performance']['simulation_steps']>0 for x in records),
            'feasible_trials':sum(x['evaluation']['success'] for x in records),
            'failed_trials':sum(not x['evaluation']['success'] for x in records),
            'failure_statuses':sorted({x['evaluation']['status'] for x in records if not x['evaluation']['success']}),
            'selected_native_repeat_exact':True,'immutable_parent_state':True,
            'authoritative_execution_evaluation':e['result']['execution_evaluation'],
            'performance':e['performance'],'total_verification_seconds':time.perf_counter()-started,
            'trial_storage_bytes':database.stat().st_size,
            'scope':'Default Panda pickup; independent full physics trials, not 5,000 cloth or scientific experiments.'}
        output.write_text(json.dumps(proof,indent=2),encoding='utf-8')
        print(json.dumps(proof,indent=2),flush=True)
    finally:r.close()


if __name__=='__main__':main()
