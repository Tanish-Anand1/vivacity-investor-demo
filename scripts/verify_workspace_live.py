"""Real HTTP/WSS workspace journey; never imports the server's Runtime locally.

Creates private verification records and executes actual remote MuJoCo jobs.
No provider keys or session capabilities are written to the evidence report.
"""
import argparse
import json
from pathlib import Path
import secrets
import time
import httpx
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosedOK


def verify(base,output,arm,resume=False,websocket_base=None):
    started=time.perf_counter();state_path=Path('data')/('workspace-live-'+arm+'-'+('public' if base.startswith('https://') else 'local')+'.json')
    prior=json.loads(state_path.read_text()) if resume else None
    capability=prior['workspace_token'] if prior else secrets.token_urlsafe(36)
    client=httpx.Client(base_url=base,timeout=120,headers={'X-Workspace-Token':capability})
    def request(method,path,body=None):
        response=client.request(method,path,json=body)
        if response.status_code>=400:raise AssertionError((path,response.status_code,response.text[:700]))
        return response.json()
    capabilities=request('GET','/v1/workspace/capabilities')
    worlds=request('GET','/v1/workspace/worlds')
    robots=[r['id'] for r in capabilities['registry']['robots'] if r['status']=='available']
    assert len(robots)==7 and len(worlds)==13
    if prior:
        assert prior['base']==base and prior['robot']==arm
        session=prior['session'];client.headers['X-Session-Token']=prior['session_token']
    else:
        configuration=request('POST','/v1/workspace/configurations',{
            'name':f'{arm} remote HTTP verification','environment_id':'desktop','robot_id':arm,
            'operation_id':'pick_place','trial_mode':'fixed','validation_trials':3,'seed':7,'realtime_speed':4})
        run=request('POST',f"/v1/workspace/configurations/{configuration['id']}/runs",{})
        session=run['session'];client.headers['X-Session-Token']=run['session_token']
        state_path.parent.mkdir(exist_ok=True)
        state_path.write_text(json.dumps({'base':base,'robot':arm,'workspace_token':capability,'session_token':run['session_token'],'session':session}),encoding='utf-8')
    session_token=client.headers['X-Session-Token']
    print(json.dumps({'base_url':base,'session_id':session['id'],'robot':arm}),flush=True)
    deadline=time.monotonic()+600
    while session['status'] in ('active','stopping'):
        assert time.monotonic()<deadline,session
        time.sleep(1)
        session=request('GET',f"/v1/sessions/{session['id']}")
    assert session['status']=='completed',session
    eid=session['experiments'][-1];experiment=request('GET',f'/v1/experiments/{eid}')
    assert experiment['result']['execution_evaluation']['success'],experiment
    assert experiment['performance']['trial_count']==3
    replay=request('GET',f'/v1/experiments/{eid}/replay')
    assert replay['branches'] and all(b['frames'] for b in replay['branches'])
    ws=(websocket_base or base).replace('https://','wss://').replace('http://','ws://')
    protocols=['vivacity.live','vivacity.token.'+session_token]
    events=[]
    with connect(f'{ws}/v1/experiments/{eid}/events',origin='https://demo.tryvivacity.com',subprotocols=protocols,open_timeout=120) as socket:
        try:
            while True:
                events.append(json.loads(socket.recv(timeout=120)))
                if events[-1]['kind'] in ('completed','failed','cancelled'):break
        except ConnectionClosedOK:pass
    assert events and events[-1]['kind']=='completed',events
    with connect(f'{ws}/v1/experiments/{eid}/live',origin='https://demo.tryvivacity.com',subprotocols=protocols,open_timeout=120) as socket:
        live=json.loads(socket.recv(timeout=120))
    assert live['frame']['time']>0
    exported=request('GET',f"/v1/experiments/{eid}/branches/{experiment['selected_branch_id']}/export")
    assert exported['success'] and exported['recorded_frames'] and exported['initial_state']['integration_state']
    before=request('GET',f"/v1/worlds/{session['world_id']}")
    changed=request('PATCH',f"/v1/worlds/{session['world_id']}/environment",{'config':before['config']|{'cube_position':[.5,-.25,.026]}})
    assert changed['revision']>before['revision']
    assert request('GET',f'/v1/experiments/{eid}')['stale']
    fresh=request('POST',f"/v1/worlds/{session['world_id']}/experiments",{'physics_trials':2,'search_candidates':2,'max_simulation_seconds':40})
    while fresh['status'] in ('queued','running'):
        assert time.monotonic()<deadline,fresh
        time.sleep(1);fresh=request('GET',f"/v1/experiments/{fresh['id']}")
    branches=request('GET',f"/v1/experiments/{fresh['id']}/branches")
    assert fresh['status']=='completed' and len(branches)==2
    assert all(b['performance']['simulation_steps']>0 for b in branches)
    result={'base_url':base,'robot':arm,'available_robots':robots,'prebuilt_world_count':len(worlds),
        'provider_configuration':{k:capabilities[k] for k in ('openai_configured','worldlabs_configured')},
        'experiment_id':eid,'validation_trials':experiment['performance']['trial_count'],
        'fresh_execution':experiment['result']['execution_evaluation'],'performance':experiment['performance'],
        'replay_bytes':len(json.dumps(replay).encode()),'event_count':len(events),'live_sequence':live['sequence'],
        'live_simulation_time':live['frame']['time'],'invalidation_verified':True,'new_experiment_id':fresh['id'],
        'new_branch_evaluations':[b['evaluation'] for b in branches],'wall_seconds':time.perf_counter()-started}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('base_url','robot','experiment_id','validation_trials','event_count','invalidation_verified','wall_seconds')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:8000')
    parser.add_argument('--arm',default='ur5e');parser.add_argument('--output',type=Path,default=Path('artifacts/workspace-live.json'))
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--websocket-base',help='Native backend URL when HTTP goes through a same-origin proxy')
    args=parser.parse_args();verify(args.base,args.output,args.arm,args.resume,args.websocket_base)
