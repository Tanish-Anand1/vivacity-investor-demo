"""Only validated in-memory model data crosses the native-process boundary."""
import base64
import json
import os
from pathlib import PurePosixPath, Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from .imports import inspect_xml, safe_name

ORBITAL_SHA256 = '6d623c9fbd7aa337b195282f55dbbcc83432ffad69a95090dde2a831a4763354'


def native_probe(source, source_sha256):
    content = base64.b64decode(source['content'], validate=True)
    assets = {name: base64.b64decode(value, validate=True) for name, value in source['assets'].items()}
    extension = PurePosixPath(source['entrypoint']).suffix.lower()
    inspect_xml(content, extension, assets)
    root = ET.fromstring(content.decode('utf-8-sig'))
    # Bound allocations that structural inspection alone cannot constrain.
    for node in root.iter():
        if node.tag in ('composite', 'flexcomp', 'skin', 'hfield', 'keyframe'):
            raise ValueError('this native probe does not support generated deformable or heightfield assets')
        for key in ('width', 'height', 'nrow', 'ncol', 'nconmax', 'njmax', 'memory'):
            if key in node.attrib:
                try:
                    number = int(node.attrib[key])
                except ValueError:
                    raise ValueError('native allocation attributes must be bounded integers')
                if not 1 <= number <= (512 if key in ('width', 'height') else 2048):
                    raise ValueError('native allocation exceeds probe bounds')
        if node.tag == 'compiler':
            for key in ('meshdir', 'texturedir', 'assetdir'):
                if key in node.attrib:
                    safe_name(node.attrib[key])
        for key in ('file', 'filename'):
            if key in node.attrib:
                if node.attrib[key] not in assets:
                    raise ValueError('native asset must exist in the scoped in-memory bundle')
    trusted = source_sha256 == ORBITAL_SHA256
    if not sys.platform.startswith('linux') and not trusted:
        raise ValueError('untrusted native execution requires the Linux sandbox; only the exact supplied fixture is enabled on this development host')
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    environment |= {'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'PYTHONIOENCODING': 'utf-8'}
    payload = {'xml': base64.b64encode(content).decode(),
               'assets': source['assets'], 'trusted_fixture': trusted}
    try:
        import tempfile
        with tempfile.TemporaryDirectory(prefix='vivacity-native-') as directory:
            result = subprocess.run([sys.executable, '-I', '-u', str(Path(__file__).with_name('import_worker.py'))],
                                    input=json.dumps(payload), text=True, capture_output=True,
                                    cwd=directory, env=environment, close_fds=True, timeout=120,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired:
        raise ValueError('native probe exceeded its 120-second wall bound') from None
    lines = result.stdout.strip().splitlines()
    if not lines or len(result.stdout) > 1024**2:
        raise ValueError('native probe failed its process/resource limits')
    try:
        response = json.loads(lines[-1])
    except (ValueError, TypeError):
        raise ValueError('native probe returned an invalid bounded response') from None
    if result.returncode or not response.get('ok'):
        # Do not export stderr, Python traces, environment or private host paths.
        error = response.get('error', 'native probe failed')
        if str(Path(__file__).parent) in error or directory in error:
            error = 'native probe failed'
        raise ValueError(error)
    return response['result'] | {'source_sha256': source_sha256}
