"""Inspect provider output without emitting credentials or signed asset URLs."""
import json
import os
from pathlib import Path
import httpx
from vivacity.credentials import load_host_credentials
from vivacity.providers import WorldLabs, download_asset

os.environ['VIVACITY_PROVIDER_SECRETS_FILE']=str(Path('data/server-secrets.json').resolve())
load_host_credentials()
if __name__=='__main__':
    resource=json.loads(Path('data/worldlabs-resource.json').read_text())
    result=WorldLabs().world(resource['world_id'])
    world=result.get('world',result)
    Path('data/visual-provider-world.json').write_text(json.dumps(world))
    assets=world['assets']
    print(json.dumps({'id':world.get('id',world.get('world_id')),'name':world.get('display_name'),
        'splats':list(assets.get('splats',{}).get('spz_urls',{})),
        'semantics':assets.get('splats',{}).get('semantics_metadata'), 'mesh':list(assets.get('mesh',{}))}))
    output=Path('frontend/public/environments/laboratory');output.mkdir(parents=True,exist_ok=True)
    content=download_asset(assets['splats']['spz_urls']['500k'])
    (output/'world.spz').write_bytes(content)
    print('SPZ bytes:',len(content))
    doc=httpx.get('https://docs.worldlabs.ai/api/rendering-spz.md').text
    Path('data/worldlabs-rendering-doc.md').write_text(doc,encoding='utf-8')
    print(doc[:6500])
