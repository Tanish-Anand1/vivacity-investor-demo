"""Execute real factory experiments through HTTP and save inspectable evidence.

python -m scripts.demo_factory --base http://127.0.0.1:8010 --output artifacts/factory-live
Add --benchmark for six independent physical trials. No experiment is simulated here.
"""
import argparse
import json
from pathlib import Path
import secrets
import time
import httpx

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8010')
    parser.add_argument('--output',default='artifacts/factory-live')
    parser.add_argument('--benchmark',action='store_true')
    parser.add_argument('--token-file',default='data/factory-demo-token.txt')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    token=Path(args.token_file);token.parent.mkdir(parents=True,exist_ok=True)
    if not token.exists():token.write_text(secrets.token_urlsafe(32),encoding='utf-8')
    client=httpx.Client(base_url=args.base.rstrip('/'),headers={'X-Workspace-Token':token.read_text().strip()},timeout=120)
    def get(path):
        response=client.get(path);response.raise_for_status();return response.json()
    def post(path,body):
        response=client.post(path,json=body);response.raise_for_status();return response.json()
    def save(name,value):
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
    def wait(path,states):
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            row=get(path)
            if row['status'] in states:return row
            time.sleep(1)
        raise TimeoutError('Backend experiment did not reach the requested state: '+path)
    health=get('/health');assert health
    cell=post('/v1/factory/cells',{'carton_count':1,'carton_start_y_m':-.4,'realtime_speed':8})
    assert cell['frame']['time']==0
    observation=get('/v1/factory/cells/'+cell['id']+'/observation')
    assert observation['camera']['detections'][0]['detected']
    save('camera.json',observation)
    run=post('/v1/factory/cells/'+cell['id']+'/runs',{'mode':'production','creator_label':'HTTP verification script'})
    url='/v1/factory/runs/'+run['id']
    post(url+'/control',{'action':'pause'});paused=wait(url,{'paused'})
    time.sleep(1);assert get(url)['frame']['time']==paused['frame']['time']
    post(url+'/control',{'action':'resume'});run=wait(url,{'completed','failed','interrupted'})
    assert run['status']=='completed' and run['metrics']['cartons_sorted']==1,run
    replay=get(url+'/samples');assert len(replay['frames'])>10
    record=get(url+'/export');save('run.json',record)
    definition=get('/v1/factory/cells/'+cell['id']+'/export');save('configuration.json',definition)
    imported=post('/v1/factory/imports',definition)
    assert imported['cell']['initial_state']==cell['initial_state'] and imported['cell']['last_run_id'] is None
    failure=post('/v1/factory/cells',cell['config']|{'carton_mass_kg':.15,'carton_friction':.05,'gripper_force_scale':.005})
    bad=post('/v1/factory/cells/'+failure['id']+'/runs',{'mode':'production'})
    bad=wait('/v1/factory/runs/'+bad['id'],{'completed','failed'})
    assert bad['status']=='failed' and bad['metrics']['cartons_sorted']==0,bad
    save('failure.json',get('/v1/factory/runs/'+bad['id']+'/export'))
    summary={'base':args.base,'run':run,'failure':bad,'camera_detected':True,'import_reproduced_initial_state':True,
             'replay_page_bytes':len(json.dumps(replay).encode()),'verified_at_unix_s':time.time()}
    if args.benchmark:
        bench=post('/v1/factory/cells/'+cell['id']+'/benchmarks',{'name':'Contact robustness verification','repeats':2,'held_out_repeats':1,'changes':{'carton_mass_kg':.15,'carton_friction':.05,'gripper_force_scale':.005}})
        bench=wait('/v1/factory/benchmarks/'+bench['id'],{'completed','failed','interrupted'})
        assert bench['status']=='completed' and len(bench['trials'])==6,bench
        assert bench['comparison']['selected_condition']=='baseline',bench
        save('benchmark.json',bench);summary['benchmark_id']=bench['id']
    for format in ('pdf','zip'):
        response=client.get('/v1/factory/reports/run/'+run['id'],params={'format':format});response.raise_for_status()
        (out/('report.'+format)).write_bytes(response.content)
    save('verification.json',summary)
    print(json.dumps({'output':str(out.resolve()),'success_run':run['id'],'failed_run':bad['id'],
                      'simulation_steps':run['metrics']['simulation_steps']+bad['metrics']['simulation_steps'],
                      'benchmark_id':summary.get('benchmark_id')}))
    client.close()

if __name__=='__main__':main()
