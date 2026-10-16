"""Real provider/API verification; capabilities and asset URLs remain ignored."""
from pathlib import Path
import httpx,json,secrets,time,hashlib,sys

if __name__=='__main__':
    headers={'X-Workspace-Token':secrets.token_urlsafe(40),'Idempotency-Key':secrets.token_hex(12)}
    client=httpx.Client(base_url='http://127.0.0.1:8010',timeout=90)
    request={'provider':'worldlabs','model':'marble-1.1','seed':7,
        'prompt':'A compact industrial warehouse with realistic steel pallet racks and cardboard cartons along the back wall, concrete flooring, steel ceiling beams and overhead lighting. Keep the central floor empty for a robotic workbench. No people.'}
    if '--resume' in sys.argv:
        state=json.loads(Path('data/visual-generation-state.json').read_text(encoding='utf-8'));headers=state['headers']
        r=client.get('/v1/workspace/generations/'+state['job']['id'],headers=headers)
    else:r=client.post('/v1/workspace/generations',headers=headers,json=request)
    r.raise_for_status();job=r.json()
    Path('data/visual-generation-state.json').write_text(json.dumps({'headers':headers,'job':job}),encoding='utf-8')
    last=None
    deadline=time.monotonic()+950
    while job['status'] not in ('completed','failed') and time.monotonic()<deadline:
        time.sleep(5);r=client.get('/v1/workspace/generations/'+job['id'],headers=headers);r.raise_for_status();job=r.json()
        if job['status']!=last:print('Provider stage:',job['status'],flush=True);last=job['status']
    report={'generation':job}
    if job['status']=='completed':
        r=client.get('/v1/workspace/worlds/'+job['world_id'],headers=headers);r.raise_for_status();world=r.json()
        asset=client.get('/v1/workspace/worlds/'+world['id']+'/appearance',headers=headers);asset.raise_for_status()
        output=Path('frontend/public/environments/warehouse');output.mkdir(parents=True,exist_ok=True)
        (output/'world.spz').write_bytes(asset.content)
        (output/'provenance.json').write_text(json.dumps({'provider_world_id':world['provider_world_id'],
            'appearance':world['appearance'],'sha256':hashlib.sha256(asset.content).hexdigest(),
            'generation_prompt':request['prompt'],'cost_credits':job['provider_cost_credits']},indent=2),encoding='utf-8')
        report.update(world=world,asset_bytes=len(asset.content),asset_sha256=hashlib.sha256(asset.content).hexdigest())
    Path('artifacts/visual-real-generation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':job['status'],'error':job.get('error'),'credits':job.get('provider_cost_credits'),'asset_bytes':report.get('asset_bytes')}),flush=True)
