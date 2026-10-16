"""Optional host-managed secret file; never part of frontend or Git artifacts."""
import json
import os
from pathlib import Path


def load_host_credentials():
    path=Path(os.getenv('VIVACITY_PROVIDER_SECRETS_FILE','/etc/secrets/server-secrets.json'))
    if not path.is_file():return
    values=json.loads(path.read_text(encoding='utf-8'))
    allowed={'OPENAI_API_KEY','WORLDLABS_API_KEY','OPENAI_WORLD_MODEL'}
    if not isinstance(values,dict) or not set(values)<=allowed or any(not isinstance(v,str) or not 1<=len(v)<=4096 for v in values.values()):
        raise RuntimeError('Invalid server provider secret file; values omitted.')
    for key,value in values.items():os.environ.setdefault(key,value)
