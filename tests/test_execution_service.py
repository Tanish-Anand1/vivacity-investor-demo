"""Exercise durable worker boundaries with real, inexpensive MuJoCo dynamics."""
from copy import deepcopy
import time
from pathlib import Path
import subprocess
import sys

import mujoco as mj
import numpy as np
import pytest

from vivacity.execution_checkpoint import capture, restore, ImmutableModelArtifact
from vivacity.execution_service import ExecutionService, AdmissionRejected
from vivacity.storage import Store, encode


class Controller:
    version = 'test.pendulum-memory/1'
    def __init__(self, model):
        self.integral = 0.
    def snapshot(self):
        return {'integral': self.integral}
    def restore(self, state):
        self.integral = state['integral']


class PendulumTask:
    def __init__(self, config):
        self.model = mj.MjModel.from_xml_string('''<mujoco><option timestep=".001"/>
        <worldbody><body pos="0 0 1"><joint axis="0 1 0"/>
        <geom type="capsule" fromto="0 0 0 .5 0 0" size=".025" mass="1"/></body>
        </worldbody><actuator><motor joint="0" ctrlrange="-10 10"/></actuator></mujoco>'''.replace('<joint axis', '<joint name="0" axis'))
        self.data = mj.MjData(self.model)
        self.controller, self.rng = Controller(self.model), np.random.default_rng(81)
        self.artifact = ImmutableModelArtifact(self.model)
        self.world_version = self.artifact.sha256
        self.state = {'phase': 'hold', 'steps': 0, 'status': 'running', 'cursor': 0,
                      'last_measurement': {}, 'config': config}

    def step(self):
        time.sleep(.001)  # Pace transport tests; this does not change simulated time.
        self.controller.integral += -self.data.qpos[0]*.001
        self.data.ctrl[:] = -2.4525-30*self.data.qpos[0]-3*self.data.qvel[0]+self.controller.integral+self.rng.normal(0,.001)
        mj.mj_step(self.model, self.data)
        self.state['steps'] += 1
        self.state['last_measurement'] = {'angle_rad': float(self.data.qpos[0])}
        if self.state['steps'] >= self.state['config'].get('steps', 300):
            self.state['status'] = 'completed'

    def frame(self):
        self.state['cursor'] += 1
        return {'time_s': float(self.data.time), 'qpos': self.data.qpos.tolist()}

    def snapshot(self):
        return capture(self.model, self.data, self.controller, world_version=self.world_version,
                       task_state=self.state, rng=self.rng, perception_state={}, order_ledger={},
                       next_frame_seq=self.state['cursor'], steps_completed=self.state['steps'],
                       model_artifact=self.artifact)

    def result(self):
        return {'task_success': self.state['status'] == 'completed', 'qpos': self.data.qpos.tolist(),
                'qvel': self.data.qvel.tolist(), 'controller': self.controller.snapshot()}


class Adapter:
    version = 'test.real-pendulum/1'
    def validate(self, config):
        if set(config)-{'steps'} or not 1 <= config.get('steps',300) <= 500:
            raise ValueError('Invalid step budget')
        return config
    def create(self, config):
        return PendulumTask(config)
    def restore(self, bundle):
        task = PendulumTask.__new__(PendulumTask)
        task.model, task.data, task.controller, task.rng = restore(bundle, Controller)
        task.state = deepcopy(bundle.checkpoint.task_state)
        task.state['cursor'] = bundle.checkpoint.next_frame_seq
        task.world_version = bundle.checkpoint.world_version
        task.artifact = ImmutableModelArtifact(task.model, bundle.model_binary)
        return task


def until(fn, timeout=10.):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError('Worker did not reach the expected state')


def service(path, **kwargs):
    return ExecutionService(Store(path), {'pendulum': Adapter()}, frame_stride=10, frame_batch=4, **kwargs)


def test_live_pause_restart_fork_comparison_and_export(tmp_path):
    path = tmp_path/'jobs.sqlite3'
    worker = service(path)
    identifier = worker.submit('owner', 'network', 'pendulum', {})['id']
    try:
        live = until(lambda: (p if len((p := worker.frames('owner', identifier))['frames']) >= 2 else None))
        assert live['status'] == 'running'
        assert worker.control('owner', identifier, 'pause')['status'] == 'paused'
        paused = worker.checkpoint('owner', identifier)
        time.sleep(.04)
        assert worker.checkpoint('owner', identifier) == paused
        page = worker.frames('owner', identifier)
        assert page['frames'][-1]['frame']['steps_completed'] == paused.steps_completed
        with pytest.raises(KeyError):
            worker.control('intruder', identifier, 'resume')
    finally:
        worker.close()
    restarted = service(path)
    try:
        assert restarted.get('owner', identifier)['status'] == 'paused'
        branch = restarted.fork('owner', 'network', identifier)['id']
        assert restarted.control('owner', identifier, 'resume')['status'] == 'running'
        until(lambda: restarted.get('owner', branch)['status'] in ('completed', 'interrupted'))
        original, fork = restarted.get('owner', identifier), restarted.get('owner', branch)
        assert original['status'] == fork['status'] == 'completed', (original, fork)
        assert original['result'] == fork['result']
        comparison = restarted.compare('owner', [identifier, branch])
        assert comparison['same_world_version']
        exported = restarted.export('owner', identifier)
        assert [f['seq'] for f in exported['frames']] == list(range(len(exported['frames'])))
        assert exported['checkpoint']['next_frame_seq'] == len(exported['frames'])
        assert restarted.export('owner', branch)['frames'][0]['seq'] == 0
        for read in (lambda: restarted.export('other', identifier),
                     lambda: restarted.compare('other', [identifier, branch]),
                     lambda: restarted.checkpoint('other', identifier)):
            with pytest.raises(KeyError):
                read()
    finally:
        restarted.close()


def test_cancel_and_queue_admission_are_persistent(tmp_path):
    path = tmp_path/'admission.sqlite3'
    worker = service(path, max_pending=1, owner_hourly=1)
    identifier = worker.submit('owner', 'network', 'pendulum', {'steps':500})['id']
    try:
        until(lambda: worker.get('owner',identifier)['checkpoint_id'])
        with pytest.raises(AdmissionRejected, match='queue'):
            worker.submit('other', 'network', 'pendulum', {})
        worker.control('owner', identifier, 'cancel')
        until(lambda: worker.get('owner',identifier)['status'] == 'cancelled')
        assert worker.export('owner',identifier)['frames']
    finally:
        worker.close()
    restarted = service(path, owner_hourly=1)
    try:
        with pytest.raises(AdmissionRejected, match='Hourly'):
            restarted.submit('owner', 'network', 'pendulum', {})
        assert restarted.get('owner',identifier)['status'] == 'cancelled'
    finally:
        restarted.close()


def test_incompatible_recovery_is_interrupted_without_replacement(tmp_path):
    path = tmp_path/'version.sqlite3'
    worker = service(path)
    identifier = worker.submit('owner','network','pendulum',{})['id']
    until(lambda: worker.get('owner',identifier)['checkpoint_id'])
    worker.control('owner',identifier,'pause')
    worker.close()
    with Store(path).connect() as db:
        record = worker.get('owner',identifier)
        record['adapter_version'] = 'incompatible'
        db.execute('UPDATE execution_jobs SET payload=? WHERE id=?', (encode(record),identifier))
    restarted = service(path)
    try:
        until(lambda: restarted.get('owner',identifier)['status']=='interrupted')
        assert 'version changed' in restarted.get('owner',identifier)['error']
        assert restarted.get('owner',identifier)['steps_completed'] == record['steps_completed']
    finally:
        restarted.close()


def test_execution_budget_is_an_explicit_failure(tmp_path):
    worker = service(tmp_path/'budget.sqlite3', max_steps=15)
    try:
        identifier = worker.submit('owner','network','pendulum',{})['id']
        until(lambda: worker.get('owner',identifier)['status']=='failed')
        record = worker.get('owner',identifier)
        assert record['error'] == 'execution_budget_exceeded'
        assert record['steps_completed'] == 15
        assert record['result'] is None
    finally:
        worker.close()


def test_storage_admission_reserves_native_model_headroom(tmp_path):
    worker = service(tmp_path/'storage.sqlite3', storage_budget_bytes=150_000_000)
    try:
        with pytest.raises(AdmissionRejected,match='storage'):
            worker.submit('owner','network','pendulum',{})
    finally:
        worker.close()


def test_expired_pause_releases_compute_capacity_and_preserves_evidence(tmp_path):
    worker = service(tmp_path/'pause-lease.sqlite3', pause_lease_s=.2)
    try:
        identifier = worker.submit('owner','network','pendulum',{})['id']
        until(lambda:worker.get('owner',identifier)['checkpoint_id'])
        assert worker.control('owner',identifier,'pause')['pause_deadline_unix_s'] is not None
        until(lambda:worker.get('owner',identifier)['status']=='cancelled')
        assert worker.get('owner',identifier)['error']=='pause_lease_expired'
        assert worker.export('owner',identifier)['frames']
    finally:
        worker.close()


def test_abrupt_process_exit_recovers_committed_state_without_duplicate_frames(tmp_path):
    path = tmp_path/'crash.sqlite3'
    code = '''
import os,sys,time
sys.path.insert(0,sys.argv[1])
from test_execution_service import service,until
worker=service(sys.argv[2])
identifier=worker.submit('owner','network','pendulum',{})['id']
until(lambda:worker.get('owner',identifier)['steps_completed']>=30)
print(identifier,flush=True)
os._exit(0)
'''
    child = subprocess.run([sys.executable,'-u','-c',code,str(Path(__file__).parent),str(path)],
                           capture_output=True,text=True,timeout=30)
    assert child.returncode == 0,child.stderr
    identifier = child.stdout.strip().splitlines()[-1]
    worker = service(path)
    try:
        until(lambda:worker.get('owner',identifier)['status']=='completed')
        result = worker.get('owner',identifier)['result']
        baseline = PendulumTask({})
        while baseline.state['status']=='running':
            baseline.step()
        assert result == baseline.result()
        frames = worker.export('owner',identifier)['frames']
        assert [frame['seq'] for frame in frames] == list(range(len(frames)))
        assert all(a['frame']['time_s']<b['frame']['time_s'] for a,b in zip(frames,frames[1:]))
    finally:
        worker.close()
