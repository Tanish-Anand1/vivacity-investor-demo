"""Development launcher; optionally reads the ignored, local provider secret file."""
import os
from pathlib import Path
import uvicorn

if __name__=='__main__':
    secret=Path('data/server-secrets.json').resolve()
    if secret.is_file():os.environ['VIVACITY_PROVIDER_SECRETS_FILE']=str(secret)
    os.environ.setdefault('VIVACITY_DATABASE','data/workspace-dev.sqlite3')
    os.environ.setdefault('VIVACITY_CORS_ORIGINS','http://127.0.0.1:5174,http://localhost:5174,https://demo.tryvivacity.com')
    os.environ.setdefault('VIVACITY_IMMUTABLE_MODEL_FORKS','1')
    os.environ.setdefault('VIVACITY_MAX_PHYSICS_TRIALS','8')
    uvicorn.run('vivacity.api:app',host='127.0.0.1',port=int(os.getenv('VIVACITY_DEV_PORT','8010')),access_log=False)
