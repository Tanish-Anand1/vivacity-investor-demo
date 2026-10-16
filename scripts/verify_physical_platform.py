"""Real HTTP/WSS verification. No simulator executes inside this client script."""
import argparse
import json
import time
import secrets
from pathlib import Path
import httpx
from websockets.sync.client import connect


def verify(base, websocket_base, output):
    start=time.perf_counter()
    with httpx.Client(base_url=base,timeout=120,headers={'X-Workspace-Token':secrets.token_urlsafe(36)}) as client:
        def call(method,path,body=None):
            r=client.request(method,path,json=body)
            assert r.is_success,(path,r.status_code,r.text[:500])
            return r.json()
        report=call('POST','/v1/workspace/physics-validations')
        assert report['passed']==report['total']==8,report
        assert call('GET','/v1/workspace/physics-validations/'+report['id'])['cases']==report['cases']
        materials=call('GET','/v1/workspace/materials')['materials']
        assert len(materials)==8
        saved=call('POST','/v1/workspace/configurations',{'name':'Verified rubber / air experiment','environment_id':'warehouse',
            'object_material':'rubber','physics':{'air_density_kg_m3':1.225},'validation_trials':3,'trial_mode':'fixed','realtime_speed':4})
        run=call('POST','/v1/workspace/configurations/'+saved['id']+'/runs',{})
        token=run['session_token'];client.headers['X-Session-Token']=token
        session=run['session'];deadline=time.monotonic()+300
        while session['status'] in ('active','stopping'):
            assert time.monotonic()<deadline,session
            time.sleep(1);session=call('GET','/v1/sessions/'+session['id'])
        assert session['status']=='completed',session
        eid=session['experiments'][-1]
        experiment=call('GET','/v1/experiments/'+eid)
        assert experiment['result']['execution_evaluation']['success'],experiment['result']
        assert experiment['performance']['trial_count']==3
        replay=call('GET',f'/v1/experiments/{eid}/replay')
        frames=[f for b in replay['branches'] for f in b['frames']]
        assert frames and all(f['inspection']['object']['material']=='rubber' for f in frames)
        assert all(f['inspection']['environment']['air_density_kg_m3']==1.225 for f in frames)
        contact_frames=[f for f in frames if any('cube' in c['geoms'] and c['normal_force_n']>0 for c in f['inspection']['contacts'])]
        assert contact_frames
        socketbase=websocket_base.replace('https://','wss://').replace('http://','ws://')
        events=[]
        origin='https://demo.tryvivacity.com' if base.startswith('https://') else 'http://127.0.0.1:5173'
        with connect(f'{socketbase}/v1/experiments/{eid}/events',origin=origin,subprotocols=['vivacity.live','vivacity.token.'+token],open_timeout=120) as socket:
            while True:
                event=json.loads(socket.recv(timeout=120));events.append(event)
                if event['kind'] in ('completed','failed','cancelled'):break
        assert events[-1]['kind']=='completed'
        export=call('GET',f"/v1/experiments/{eid}/branches/{experiment['selected_branch_id']}/export")
        assert export['initial_configuration']['physics']['air_density_kg_m3']==1.225
        before=call('GET','/v1/worlds/'+session['world_id'])
        changed=call('PATCH','/v1/worlds/'+session['world_id']+'/environment',{'config':before['config']|{'object_material':'custom','cube_friction':.05,'cube_mass':.15,'physics':before['config']['physics']|{'gripper_force_scale':.05}}})
        assert changed['revision']>before['revision'] and call('GET','/v1/experiments/'+eid)['stale']
        new=call('POST','/v1/worlds/'+session['world_id']+'/experiments',{'physics_trials':2,'search_candidates':2,'max_simulation_seconds':40})
        while new['status'] in ('queued','running'):
            assert time.monotonic()<deadline,new
            time.sleep(1);new=call('GET','/v1/experiments/'+new['id'])
        branches=call('GET','/v1/experiments/'+new['id']+'/branches')
        assert new['status']=='completed' and len(branches)==2
        assert all(b['performance']['simulation_steps']>0 and not b['evaluation']['success'] for b in branches),branches
        result={'base_url':base,'backend_url':websocket_base,'experiment_id':eid,'changed_experiment_id':new['id'],
                'benchmarks':report,'material_count':len(materials),'validation_trials':3,
                'fresh_execution':experiment['result']['execution_evaluation'], 'performance':experiment['performance'],
                'replay_frames':len(frames),'replay_bytes':len(json.dumps(replay).encode()),'measured_contact_frames':len(contact_frames),
                'websocket_event_count':len(events),'invalidation_verified':True,'weak_grip_failures':[b['evaluation'] for b in branches],
                'wall_seconds':time.perf_counter()-start}
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('base_url','experiment_id','replay_frames','websocket_event_count','invalidation_verified','wall_seconds')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8000');p.add_argument('--websocket-base',default='http://127.0.0.1:8000');p.add_argument('--output',type=Path,default=Path('artifacts/physical-platform-live.json'))
    args=p.parse_args();verify(args.base,args.websocket_base,args.output)
