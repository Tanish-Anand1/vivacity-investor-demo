import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from vivacity.imports import ImportService, unpack
from vivacity.import_physics import native_probe, ORBITAL_SHA256

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/imports/orbital_salvage_lab.zip'


def source(data=None):
    entry, content, assets, _ = unpack(data or FIXTURE.read_bytes())
    return {'entrypoint': entry, 'content': base64.b64encode(content).decode(),
            'assets': {k: base64.b64encode(v).decode() for k, v in assets.items()}}


def test_original_orbital_model_compiles_and_actuates_without_claiming_grasp():
    result = native_probe(source(), ORBITAL_SHA256)
    assert result['physics_model_valid'] and result['robot_actuation_verified']
    assert result['simulation_steps'] == 125 and result['joint_displacement'] > .01
    assert len(result['actuators']) == 3
    assert result['task_execution_verified'] is False
    assert result['state_encoding'] == 'mjSTATE_INTEGRATION'
    assert result['initial_state'] != result['final_state']


def test_native_verification_is_explicit_background_work_and_persists(tmp_path):
    service = ImportService(tmp_path)
    record = service.create('orbital.zip', FIXTURE.read_bytes())
    assert record['physics_ready'] is False
    with ThreadPoolExecutor(max_workers=1) as executor:
        queued = service.verify(record['id'], executor)
        assert queued['status'] == 'physics_verifying'
        deadline = time.monotonic() + 30
        while service.get(record['id'])['status'] == 'physics_verifying':
            assert time.monotonic() < deadline
            time.sleep(.02)
    final = service.get(record['id'])
    assert final['status'] == 'actuation_verified'
    assert final['physics_ready'] is False  # A probe is not a configured task.
    assert ImportService(tmp_path).get(record['id']) == final


def test_restart_does_not_claim_an_interrupted_probe_completed(tmp_path):
    service = ImportService(tmp_path)
    record = service.create('orbital.zip', FIXTURE.read_bytes())
    payload = service._load(record['id'])
    payload['record']['status'] = 'physics_verifying'
    service._save(payload)
    restored = ImportService(tmp_path).get(record['id'])
    assert restored['status'] == 'physics_failed'
    assert 'interrupted' in restored['diagnostics'][-1]


@pytest.mark.parametrize('unsafe', [
    '<mujoco><compiler meshdir="/etc"/></mujoco>',
    '<mujoco><asset><texture type="2d" builtin="flat" width="100000" height="100000"/></asset></mujoco>',
    '<mujoco><size memory="1024M"/></mujoco>',
    '<mujoco><include file="private.xml"/></mujoco>',
])
def test_unsafe_native_descriptions_fail_before_process_creation(unsafe):
    value = {'entrypoint': 'scene.xml', 'content': base64.b64encode(unsafe.encode()).decode(), 'assets': {}}
    with pytest.raises(ValueError):
        native_probe(value, 'untrusted')


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux syscall sandbox boundary')
def test_linux_filter_denies_host_files_network_and_children():
    worker = Path(__file__).resolve().parents[1] / 'vivacity/import_worker.py'
    program = f'''import importlib.util, socket, subprocess, sys, json
spec=importlib.util.spec_from_file_location('worker',{str(worker)!r});m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.restrict_linux()
denied=[]
for operation in (lambda:open('/proc/self/environ','rb'),lambda:socket.socket(),lambda:subprocess.run([sys.executable,'-c','pass'])):
    try:operation()
    except PermissionError:denied.append(True)
    else:denied.append(False)
print(json.dumps(denied))
'''
    result = subprocess.run([sys.executable, '-I', '-c', program], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [True, True, True]
