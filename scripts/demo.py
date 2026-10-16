"""Run the investor journey against a real HTTP and WebSocket server."""
import argparse
import asyncio
import json
from pathlib import Path
import time
import httpx
import websockets


async def read_events(base, eid):
    url = base.replace('http://', 'ws://').replace('https://', 'wss://') + f'/v1/experiments/{eid}/events'
    events = []
    async with websockets.connect(url) as ws:
        async for message in ws:
            event = json.loads(message)
            events.append(event)
            # The terminal event is the protocol's completion signal. Do not
            # depend on a reverse proxy forwarding the server's close frame.
            if event['kind'] in ('completed', 'failed', 'cancelled'):
                break
    return events


def run(base, output, timeout_seconds=120):
    evidence = {'schema_version': '1.0', 'base_url': base, 'source': 'executed_live_api_experiments', 'experiments': []}
    with httpx.Client(base_url=base, timeout=60) as client:
        def post(route, body=None):
            r = client.post(route, json=body); r.raise_for_status(); return r.json()

        def experiment(world, settings=None):
            e = post(f"/v1/worlds/{world['id']}/experiments", settings or {})
            eid = e['id']; deadline = time.monotonic()+timeout_seconds
            while e['status'] in ('queued', 'running'):
                if time.monotonic() > deadline:
                    raise RuntimeError('live experiment timed out')
                time.sleep(0.5)
                r = client.get(f'/v1/experiments/{eid}'); r.raise_for_status(); e = r.json()
            branches = client.get(f'/v1/experiments/{eid}/branches').json()
            replay = client.get(f'/v1/experiments/{eid}/replay').json()
            events = asyncio.run(read_events(base, eid))
            evidence['experiments'].append({'world_id': world['id'], 'experiment': e, 'branches': branches, 'replay': replay, 'events': events})
            print(world['backend'], e['status'], e['result'].get('conclusion', e['error']))
            for b in branches:
                print(' ', b['action'].get('planner', b['action'].get('hypothesis')), b['evaluation']['status'], b['evaluation'].get('goal_error_m', b['evaluation'].get('heldout_rmse')))
            if e['status'] != 'completed':
                raise RuntimeError(e['error'])
            assert events[-1]['kind'] == 'completed'
            assert all(item['frames'] for item in replay['branches'])
            return e, branches

        try:
            evidence['health'] = client.get('/health').json()
            robot = post('/v1/worlds', {'backend': 'mujoco', 'seed': 7})
            evidence['robot_initialization'] = robot['performance']
            e, branches = experiment(robot)
            assert e['selected_branch_id'], 'default fixture found no successful reach'
            assert any(b['evaluation']['status'] == 'collision_failure' for b in branches), 'no measured collision failure'
            selected = next(b for b in branches if b['id'] == e['selected_branch_id'])
            # Repeat exactly from uncommitted parent. Fixed seed must reproduce actions and state.
            repeated, repeat_branches = experiment(robot)
            assert [b['action'] for b in branches] == [b['action'] for b in repeat_branches]
            assert [b['final_state'] for b in branches] == [b['final_state'] for b in repeat_branches]
            changed = client.patch(f"/v1/worlds/{robot['id']}/environment", json={'config': {'obstacle_position': [0.75, -0.4, 0.2]}})
            changed.raise_for_status()
            assert client.get(f"/v1/experiments/{e['id']}").json()['stale']
            stale_commit = client.post(f"/v1/worlds/{robot['id']}/commit", json={'experiment_id': e['id'], 'branch_id': selected['id']})
            assert stale_commit.status_code == 409
            new, _ = experiment(robot)
            assert new['selected_branch_id']
            post(f"/v1/worlds/{robot['id']}/commit", {'experiment_id': new['id'], 'branch_id': new['selected_branch_id']})
            post(f"/v1/worlds/{robot['id']}/reset")
            blocked = client.patch(f"/v1/worlds/{robot['id']}/environment", json={'config': {'obstacle_position': [0.5, 0.1, 0.3], 'obstacle_size': [0.35, 0.35, 0.3]}})
            blocked.raise_for_status()
            failed, _ = experiment(robot, {'planner_iterations': 100})
            assert failed['selected_branch_id'] is None, 'blocked fixture must remain an honest failure'
            selection=post('/v1/templates/resolve', {'arm':'panda','world':'textile','task':'cloth_fold'})
            cloth = post('/v1/worlds', selection)
            folded, folds = experiment(cloth, {'search_candidates':50,'physics_budget':3,'execute_selected':True,'max_simulation_seconds':40})
            assert folded['result']['execution_evaluation']['success']
            assert any(b['performance']['simulation_steps']>0 for b in folds)
            assert client.post('/v1/worlds',json={'backend':'scipy'}).status_code==422
            evidence['checks'] = {'live_http':True,'live_websocket':True,'deterministic_physics_reexecution':True,'failed_and_successful_reach':True,'geometry_replan':True,'stale_commit_rejection':True,'all_paths_fail':True,'real_fixture_fold':True,'scientific_backend_retired':True}
            evidence['status'] = 'passed'
            print('Live demonstration checks passed.')
        finally:
            path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(evidence, indent=2, allow_nan=False), encoding='utf-8')
            print('Evidence:', path.resolve())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', default='artifacts/live-demo.json')
    parser.add_argument('--timeout-seconds', type=float, default=120)
    args = parser.parse_args()
    run(args.base_url.rstrip('/'), args.output, args.timeout_seconds)
