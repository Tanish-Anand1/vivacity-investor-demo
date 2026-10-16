"""Real REST/WSS diagnostic. A 100 ms rollout intentionally cannot finish pickup.

This verifies timeout honesty and recorded physics, not successful manipulation.
Successful full task runs are covered by the template suite and public UI checks.
"""
import argparse
import json
from pathlib import Path
import time
import httpx
from websockets.sync.client import connect


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--origin',default='http://127.0.0.1:5173')
    parser.add_argument('--output',default='artifacts/template-boundary.json')
    args=parser.parse_args();base=args.base_url.rstrip('/')
    with httpx.Client(base_url=base,timeout=60) as client:
        selected=client.post('/v1/templates/resolve',json={'world':'warehouse'})
        selected.raise_for_status()
        created=client.post('/v1/worlds',json=selected.json());created.raise_for_status()
        world=created.json();assert world['history']==[]
        submitted=client.post(f"/v1/worlds/{world['id']}/experiments",json={
            'search_candidates':8,'physics_budget':3,'max_simulation_seconds':.1})
        submitted.raise_for_status();eid=submitted.json()['id']
        uri=base.replace('https://','wss://').replace('http://','ws://')+f'/v1/experiments/{eid}/events'
        events=[];start=time.monotonic()
        with connect(uri,origin=args.origin,open_timeout=60) as socket:
            while True:
                event=json.loads(socket.recv(timeout=180));events.append(event)
                if event['kind'] in ('completed','failed','cancelled'):break
        result=client.get(f'/v1/experiments/{eid}');result.raise_for_status();experiment=result.json()
        branches=client.get(f'/v1/experiments/{eid}/branches');branches.raise_for_status();rows=branches.json()
        replay=client.get(f'/v1/experiments/{eid}/replay');replay.raise_for_status()
        assert experiment['status']=='completed' and experiment['selected_branch_id'] is None
        assert all(not b['evaluation']['success'] and b['performance']['simulation_steps']>0 for b in rows)
        assert all(r['frames']==b['trace'] for r,b in zip(replay.json()['branches'],rows))
        assert all(a['seq']<b['seq'] for a,b in zip(events,events[1:]))
        report={'status':'passed','base_url':base,'diagnostic':'deliberate 100 ms timeout; not a successful task',
                'wall_seconds':time.monotonic()-start,'world_id':world['id'],
                'experiment':experiment,'branches':rows,'events':events,'replay_matches':True}
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
        print({'status':'passed','experiment':eid,'websocket_messages':len(events),
               'steps':[b['performance']['simulation_steps'] for b in rows],
               'statuses':[b['evaluation']['status'] for b in rows],'replay_matches':True})


if __name__=='__main__':main()
