"""Run the research G1 task through real HTTP; export measured evidence.

Start an isolated server with VIVACITY_EXPERIMENTAL_CONTACT_TASKS=1 first.
No workspace capability is logged or retained in the exported evidence.
"""
import argparse
import json
from pathlib import Path
import secrets
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8192')
    parser.add_argument('--output', default='artifacts/physical-truth-runtime/http-journey.json')
    args = parser.parse_args()
    prefix = '/v1/robotics/contact'
    evidence = {'base_url':args.base_url,'started_unix_s':time.time(),'checks':[]}
    with httpx.Client(base_url=args.base_url, headers={'X-Workspace-Token':secrets.token_urlsafe(40)},timeout=90.) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            response.raise_for_status()
            return response.json()
        def wait(path,predicate,timeout=300.):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                payload=call('GET',path)
                if predicate(payload):return payload
                if payload['status']=='interrupted':raise RuntimeError(payload)
                time.sleep(.25)
            raise TimeoutError(payload)
        assert call('GET','/health')['status']=='ok'
        assert call('GET',prefix+'/capabilities')['enabled']
        job=call('POST',prefix+'/experiments',json={})
        path=prefix+'/experiments/'+job['id']
        frames=wait(path+'/frames',lambda p:len(p['frames'])>=2)
        assert frames['status']=='running'
        evidence['checks'].append('authoritative_frames_before_completion')
        call('POST',path+'/pause')
        wait(path,lambda p:p['status']=='paused')
        checkpoint=call('GET',path+'/checkpoint')
        time.sleep(.2)
        assert call('GET',path+'/checkpoint')==checkpoint
        evidence['checks'].append('pause_freezes_complete_checkpoint')
        branch=call('POST',path+'/fork',json={})
        call('POST',path+'/resume')
        completed=wait(path,lambda p:p['status'] in ('completed','failed'))
        branch_done=wait(prefix+'/experiments/'+branch['id'],lambda p:p['status'] in ('completed','failed'))
        assert completed['result']['task_success'] and branch_done['result']['task_success']
        assert completed['result']['measurements']['last_measurement']==branch_done['result']['measurements']['last_measurement']
        evidence['checks'].append('independent_fork_reproduces_measured_final_state')
        evidence['comparison']=call('POST',prefix+'/compare',json={'ids':[job['id'],branch['id']]})
        evidence['replay']=call('GET',path+'/replay')
        evidence['export']=call('GET',path+'/export')
        assert evidence['replay']['frames']==evidence['export']['frames']
        evidence['checks'].append('replay_matches_exported_authoritative_frames')
        failed=call('POST',prefix+'/experiments',json={'config':{'parcel':{
            'sliding_friction':.001,'torsional_friction_m':0.,'rolling_friction_m':0.}}})
        failed=wait(prefix+'/experiments/'+failed['id'],lambda p:p['status'] in ('failed','completed'))
        assert failed['status']=='failed' and not failed['result']['task_success']
        assert failed['result']['failure_reason'] in ('grip_slipped','retention_lost','lift_not_clear','bilateral_load_not_sustained')
        evidence['failure_trial']=failed
        evidence['checks'].append('changed_friction_produces_measured_failure')
        assert failed['world_version']!=completed['world_version']
        evidence['checks'].append('parameter_change_uses_new_immutable_world_version')
    evidence['finished_unix_s']=time.time()
    destination=Path(args.output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(evidence,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps({'checks':evidence['checks'],'report':str(destination.resolve())}),flush=True)


if __name__=='__main__':main()
