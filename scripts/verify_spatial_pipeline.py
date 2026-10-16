"""Real HTTP/WSS probe. All simulation and provider work happens on the server."""
import argparse
import hashlib
import json
import secrets
import time
from pathlib import Path
import httpx
from websockets.sync.client import connect


def verify(base, socketbase, output, generate=False, resume=False, failure=False):
    capability=secrets.token_urlsafe(36);headers={'X-Workspace-Token':capability}
    statefile=Path('data/spatial-verification-'+('public' if base.startswith('https') else 'local')+'.json')
    resumed=json.loads(statefile.read_text(encoding='utf-8')) if resume else None
    if resumed:headers=resumed['headers']
    report={'base_url':base,'started_unix_s':time.time()}
    with httpx.Client(base_url=base,headers=headers,timeout=120,trust_env=False) as client:
        def call(method,path,body=None,extra=None):
            for attempt in range(3):
                try:response=client.request(method,path,json=body,headers=extra);break
                except httpx.TransportError:
                    if method!='GET' or attempt==2:raise
                    time.sleep(1)
            assert response.is_success,(path,response.status_code,response.text[:500])
            return response.json()
        if generate:
            # This input is an actual render of our virtual warehouse, not a
            # photograph of hardware. Never present it as hardware validation.
            if resumed:
                job=call('GET','/v1/workspace/generations/'+(resumed.get('job') or resumed['generation'])['id'])
                captured=next(c for c in call('GET','/v1/workspace/captures') if c['id']==job['inputs'][0]['capture_id'])
            else:
                capture=client.post('/v1/workspace/captures?filename=warehouse-view.jpg',content=Path('frontend/public/vivacity/world-previews/warehouse.jpg').read_bytes())
                capture.raise_for_status();captured=capture.json()
                job=call('POST','/v1/workspace/generations',{'provider':'worldlabs','model':'marble-1.1','seed':19,
                'input_type':'image','inputs':[{'capture_id':captured['id']}],
                'prompt':'Reconstruct this compact industrial warehouse with metal racks, concrete floor and an empty central robotics workbench. Preserve the room layout from the supplied virtual-scene image. No people.'},
                    {'Idempotency-Key':secrets.token_hex(16)})
            statefile.write_text(json.dumps({'headers':headers,'job':job}),encoding='utf-8')
            deadline=time.monotonic()+950;last=None
            while job['status'] not in ('completed','failed'):
                assert time.monotonic()<deadline,'generation timed out'
                if job['status']!=last:print('World generation:',job['status'],flush=True);last=job['status']
                time.sleep(5);job=call('GET','/v1/workspace/generations/'+job['id'])
            report['generation']=job
            assert job['status']=='completed',job
            world=call('GET','/v1/workspace/worlds/'+job['world_id'])
            report['generated_world']=world
            report['input_provenance']='image of an actual virtual-scene render; not a hardware recording'
            for suffix in ('appearance?quality=100k','appearance?quality=500k','geometry','thumbnail'):
                data=client.get('/v1/workspace/worlds/'+world['id']+'/'+suffix);data.raise_for_status()
                report.setdefault('assets',{})[suffix]={'bytes':len(data.content),'sha256':hashlib.sha256(data.content).hexdigest()}
            assert world['representations']['geometry']['original_glb_preserved']
            assert world['generation']['inputs'][0]['sha256']==captured['sha256']
            environment=world['id']
        else:environment='warehouse'
        if resumed and resumed.get('run'):
            run=resumed['run']
        else:
            extra={'physics':{'gripper_force_scale':.05},'object_mass_kg':.15,'object_friction':.05} if failure else {}
            saved=call('POST','/v1/workspace/configurations',{'name':'Weak-grip failure verification' if failure else 'Seeded spatial robustness verification','environment_id':environment,
            'trial_mode':'fixed','validation_trials':3,'realtime_speed':4,'randomization_cycles':3,
            'variation':{'enabled':True,'friction_min':.05 if failure else .15,'friction_max':.1 if failure else 1.2,
                'mass_min_kg':.14 if failure else .04,'mass_max_kg':.15 if failure else .1,'position_radius_m':.025},**extra})
            run=call('POST','/v1/workspace/configurations/'+saved['id']+'/runs',{})
        session=run['session'];token=run['session_token'];client.headers['X-Session-Token']=token
        statefile.write_text(json.dumps({'headers':headers,'run':run,**({'generation':report['generation']} if generate else {})}),encoding='utf-8')
        deadline=time.monotonic()+650
        while session['status'] in ('active','stopping'):
            assert time.monotonic()<deadline,'physics session timed out'
            time.sleep(2)
            session=call('GET','/v1/sessions/'+session['id'])
        assert session['status']=='completed',session
        assert [c['partition'] for c in session['conditions']]==['baseline','training','held_out']
        runs=call('GET','/v1/workspace/runs');owned=next(r for r in runs if r['session_id']==session['id'])
        assert len(owned['robustness']['configurations'])==3
        if failure:assert len(owned['robustness']['failure_regions'])==3
        report.update(session=session,robustness=owned['robustness'],experiments=[x['experiment'] for x in owned['experiments']])
        eid=session['experiments'][0];experiment=call('GET','/v1/experiments/'+eid)
        branches=call('GET','/v1/experiments/'+eid+'/branches')
        selected=next((b for b in branches if b['id']==experiment['selected_branch_id']),branches[0])
        assert selected['performance']['simulation_steps']>0 and selected['evaluation']['success']==(not failure)
        samples=[{'time_s':frame['time'],'position_m':next(b['position'] for b in frame['body_transforms'] if b['name']=='target')}
                 for frame in selected['trace'][::max(1,len(selected['trace'])//10)]]
        comparison=call('POST',f"/v1/workspace/runs/{session['id']}/measurements",{'experiment_id':eid,'branch_id':selected['id'],
            'source_label':'Recorded simulation self-reference, numerical alignment check only','source_kind':'synthetic_reference','samples':samples})
        assert comparison['rmse_position_m']<1e-10
        replay=call('GET',f'/v1/experiments/{eid}/replay');report['replay_frames']=sum(len(b['frames']) for b in replay['branches'])
        origin='https://demo.tryvivacity.com' if base.startswith('https') else 'http://127.0.0.1:5173'
        events=[]
        with connect(socketbase.replace('https://','wss://').replace('http://','ws://')+f'/v1/experiments/{eid}/events',origin=origin,
            subprotocols=['vivacity.live','vivacity.token.'+token],open_timeout=120) as socket:
            while True:
                event=json.loads(socket.recv(timeout=120));events.append(event)
                if event['kind'] in ('completed','failed','cancelled'):break
        assert events[-1]['kind']=='completed'
        report.update(measurement_comparison=comparison,websocket_events=len(events),completed_unix_s=time.time())
        output.parent.mkdir(exist_ok=True,parents=True);output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'configs':3,'partitions':owned['robustness']['partitions'],'replay_frames':report['replay_frames'],
                          'websocket_events':len(events),'measurement_rmse_m':comparison['rmse_position_m'],'output':str(output)}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8010');p.add_argument('--socket-base',default='http://127.0.0.1:8010');p.add_argument('--generate',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--failure',action='store_true');p.add_argument('--output',type=Path,default=Path('artifacts/spatial-live-local.json'))
    args=p.parse_args();verify(args.base,args.socket_base,args.output,args.generate,args.resume,args.failure)
