"""Export only deployable backend source; never copy credentials or demo data."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
target = root / 'data' / ('render-source-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
target.mkdir(parents=True, exist_ok=False)
files = [p for directory in ('vivacity', 'tests') for p in (root / directory).rglob('*.py')]
files += [root / 'vivacity/visual_catalog.json', root / 'vivacity/factory_layout.json']
files += [root / 'fixtures/imports/orbital_salvage_lab.zip', root / 'fixtures/imports/ORBITAL_SOURCE.md']
files += [root / name for name in ('Dockerfile', '.dockerignore', 'requirements-lock.txt', 'render.yaml', '.github/workflows/backend-linux.yml', '.github/workflows/backend-host-memory.yml', '.github/workflows/backend-physics-5000.yml', 'scripts/audit-varied-physics.py')]
files += [root / name for name in subprocess.check_output(
    ['git', 'ls-files', 'assets/menagerie/franka_emika_panda'], cwd=root, text=True).splitlines()]
for model in ('universal_robots_ur5e','kuka_iiwa_14','kinova_gen3','ufactory_xarm7'):
    files += [p for p in (root/'assets/menagerie'/model).rglob('*') if p.is_file()]
manifest = {}
for source in sorted(set(files)):
    relative = source.relative_to(root)
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f'Unexpected deployment source: {relative}')
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    manifest[relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
(target / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
(target / '.gitignore').write_text('__pycache__/\n*.pyc\nartifacts/\ndata/\n.env*\n', encoding='utf-8')
(target / '.gitattributes').write_text('* -text\n', encoding='utf-8')
(target / 'README.md').write_text('''# Vivacity simulation backend
Private deployment snapshot of the real FastAPI and MuJoCo robotics runtime.
SOURCE_MANIFEST.json identifies the exact source content exported from the
development workspace. Credentials, frontend work and experiment databases
are excluded.

Render: import render.yaml as a Blueprint. It proposes paid 1 CPU / 2 GB compute
and a 5 GB disk at /data. Review actual account pricing before creating it.
Keep one instance and one Uvicorn process. /health is the HTTP readiness path.
Only the two deployed Vivacity frontend origins are allowed. No LLM key is
required. The main workspace contains the complete API/frontend handoff.

The GitHub Actions workflow builds this exact Dockerfile and executes the full
backend test suite inside the Linux image. A workflow/configuration is not proof
of a successful build: inspect the actual run and uploaded JUnit evidence.
''', encoding='utf-8')
print(json.dumps({'directory': str(target), 'source_files': len(manifest), 'source_bytes': sum(p.stat().st_size for p in files)}))
