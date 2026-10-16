import json
from pathlib import Path
from vivacity.api import create_app

spec = json.dumps(create_app().openapi(), indent=2) + '\n'
for path in (Path('openapi.json'), Path('docs/openapi.json')):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec, encoding='utf-8')
    print(path.resolve())
