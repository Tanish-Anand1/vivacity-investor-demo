"""Verify live progress, reconnect and API responsiveness during CPU work."""
import asyncio
import json
from pathlib import Path
import time
import httpx
import websockets


async def main():
    base = 'http://127.0.0.1:8000'
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        w = (await client.post('/v1/worlds', json={'backend': 'mujoco'})).json()
        tic = time.perf_counter()
        response = await client.post(f"/v1/worlds/{w['id']}/experiments", json={})
        response.raise_for_status()
        submit_seconds = time.perf_counter()-tic
        e = response.json(); events = []; health_times = []
        ws_url = f"ws://127.0.0.1:8000/v1/experiments/{e['id']}/events"
        done = asyncio.Event()

        async def measure_health():
            while not done.is_set():
                tic = time.perf_counter()
                r = await client.get('/health'); r.raise_for_status()
                health_times.append(time.perf_counter()-tic)
                await asyncio.sleep(0.1)

        health = asyncio.create_task(measure_health())
        try:
            async with websockets.connect(ws_url) as ws:
                first = json.loads(await ws.recv()); events.append(first)
                assert first['kind'] == 'queued'
                # Disconnect, then recover all remaining persisted events by sequence.
            async with websockets.connect(ws_url + f"?after={first['seq']}") as ws:
                async for message in ws:
                    events.append(json.loads(message))
        finally:
            done.set(); await health
        assert events[-1]['kind'] == 'completed'
        assert len({e['seq'] for e in events}) == len(events)
        assert sum(e['kind'] == 'branch_completed' for e in events) == 3
        final = (await client.get(f"/v1/experiments/{e['id']}")).json()
        report = {'status': 'passed', 'experiment_id': e['id'], 'submit_wall_seconds': submit_seconds, 'health_request_count_during_experiment': len(health_times), 'max_health_wall_seconds': max(health_times), 'events': events, 'performance': final['performance'], 'checks': ['live_progress_delivery', 'sequence_reconnect_without_duplicates', 'api_responds_during_simulation']}
        Path('artifacts/live-events.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print({k: v for k, v in report.items() if k not in ('events', 'performance')})


if __name__ == '__main__':
    asyncio.run(main())
