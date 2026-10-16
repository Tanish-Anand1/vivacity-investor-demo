"""Run the unchanged Pytest suite with temporary databases on the project drive."""
from pathlib import Path
import os
import subprocess
import sys
from uuid import uuid4


def main():
    root = Path(__file__).resolve().parents[1]
    temp = (root / 'data' / 'backend-test-temp').resolve()
    if not temp.is_relative_to(root):
        raise RuntimeError('Test temporary directory must stay within this workspace')
    temp.mkdir(parents=True, exist_ok=True)
    # Unique, initially absent targets avoid removing other runs or user files.
    run = temp / uuid4().hex
    env = os.environ | {'TEMP': str(temp), 'TMP': str(temp)}
    return subprocess.call([sys.executable, '-m', 'pytest', '--basetemp', str(run), *sys.argv[1:]], cwd=root, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
