"""Run an actual hosted six-trial adaptive experiment and verify budget reporting."""
import argparse
import json
from pathlib import Path
import time
import httpx


def verify(base,output):
    start=time.perf_counter()
    with httpx.Client(base_url=base,timeout=90) as client:
        def request(method,path,body=None):
            response=client.request(method,path,json=body);response.raise_for_status();return response.json()
        health=request('GET','/health')
        assert health['limits']['physics_trial_workers']==2
        world=request('POST','/v1/worlds',{'backend':'mujoco','seed':7,'config':{'task':'pick_place','obstacle_enabled':False}})
        experiment=request('POST',f"/v1/worlds/{world['id']}/experiments",{
            'adaptive_trials':True,'search_candidates':32,'physics_budget':6,
            'max_simulation_seconds':40,'execute_selected':True})
        deadline=time.monotonic()+600
        while experiment['status'] in ('queued','running'):
            assert time.monotonic()<deadline
            time.sleep(1);experiment=request('GET',f"/v1/experiments/{experiment['id']}")
        assert experiment['status']=='completed'
        performance=experiment['performance']
        assert performance['trial_count']==performance['integrated_trial_count']==6
        assert performance['stopping_reason']=='host_compute_budget'
        assert performance['peak_parallel_trials']==2
        assert experiment['result']['execution_evaluation']['success']
        replay=request('GET',f"/v1/experiments/{experiment['id']}/replay")
        assert replay['branches'] and all(b['frames'] for b in replay['branches'])
        result={'base_url':base,'experiment_id':experiment['id'],'performance':performance,
            'fresh_execution':experiment['result']['execution_evaluation'],
            'replay_branches':len(replay['branches']),'replay_frames':sum(len(b['frames']) for b in replay['branches']),
            'wall_seconds':time.perf_counter()-start}
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('experiment_id','replay_branches','replay_frames','wall_seconds')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='https://demo.tryvivacity.com/runtime')
    parser.add_argument('--output',type=Path,default=Path('artifacts/runtime-final-budget-live.json'))
    args=parser.parse_args();verify(args.base,args.output)
