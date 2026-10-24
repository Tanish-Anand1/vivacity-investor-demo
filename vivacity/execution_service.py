"""Bounded, durable task execution over atomic frame/state checkpoints.

This service accepts a shared executor so the application uses its existing
single humanoid worker. Controller-specific code remains behind a task adapter.
It does not certify the capabilities of a task or replace its physical evaluator.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from copy import deepcopy
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Protocol

from .execution_checkpoint import CheckpointStore, CheckpointBundle
from .storage import Store, encode


class ExecutableTask(Protocol):
    world_version: str
    state: dict
    def step(self) -> None: ...
    def frame(self) -> dict: ...
    def snapshot(self) -> CheckpointBundle: ...
    def result(self) -> dict: ...


class TaskAdapter(Protocol):
    version: str
    def validate(self, config: dict) -> dict: ...
    def create(self, config: dict) -> ExecutableTask: ...
    def restore(self, checkpoint: CheckpointBundle) -> ExecutableTask: ...


class AdmissionRejected(ValueError):
    pass


TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


class ExecutionService:
    """One active task; a bounded persistent queue; explicit pause acknowledgement.

    A graceful shutdown commits pending physics before suspending. An abrupt
    restart resumes only from an atomic checkpoint. A changed adapter reports an
    interrupted run instead of silently initializing a new simulation.
    """
    def __init__(self, store: Store, adapters: dict[str, TaskAdapter], *, executor=None,
                 max_pending=2, owner_hourly=12, ip_hourly=24, compute_budget_s=120.,
                 frame_stride=25, frame_batch=16, max_steps=15000, storage_budget_bytes=3_000_000_000,
                 pause_lease_s=900.):
        self.store, self.adapters = store, adapters
        self.checkpoints = CheckpointStore(store)
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix='checkpoint-physics')
        self.owns_executor = executor is None
        self.condition = threading.Condition(threading.RLock())
        self.stopping = False
        self.max_pending, self.owner_hourly, self.ip_hourly = max_pending, owner_hourly, ip_hourly
        self.compute_budget_s, self.frame_stride = compute_budget_s, frame_stride
        self.frame_batch, self.max_steps = frame_batch, max_steps
        self.storage_budget_bytes = storage_budget_bytes
        self.pause_lease_s = pause_lease_s
        self.futures = []
        self.requested = {}
        self.render_cache = OrderedDict()
        self.render_lock = threading.Lock()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS execution_jobs('
                       'id TEXT PRIMARY KEY, owner TEXT NOT NULL, admission_key TEXT NOT NULL, '
                       'created REAL NOT NULL, payload TEXT NOT NULL)')
            queued = []
            for identifier, owner, payload in db.execute('SELECT id,owner,payload FROM execution_jobs ORDER BY created,id'):
                record = json.loads(payload)
                if record['status'] not in TERMINAL:
                    if record['status'] == 'cancelling':
                        record['status'] = 'cancelled'
                    elif record['status'] in ('paused', 'pausing'):
                        record['status'] = 'paused'
                        queued.append((owner, identifier))
                    else:
                        record['status'] = 'queued'
                        queued.append((owner, identifier))
                    self._save(db, owner, record)
                    self.requested[identifier] = record['status']
        for owner, identifier in queued:
            self.futures.append(self.executor.submit(self._run, owner, identifier))

    @staticmethod
    def _save(db, owner, record):
        db.execute('UPDATE execution_jobs SET payload=? WHERE id=? AND owner=?',
                   (encode(record), record['id'], owner))

    def _get(self, db, owner, identifier):
        row = db.execute('SELECT payload FROM execution_jobs WHERE id=? AND owner=?', (identifier, owner)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return json.loads(row[0])

    def get(self, owner, identifier):
        with self.store.connect() as db:
            return self._get(db, owner, identifier)

    def history(self, owner, limit=20):
        if not 1 <= limit <= 20:
            raise ValueError('history limit must lie in [1,20]')
        with self.store.connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM execution_jobs WHERE owner=? ORDER BY created DESC,id LIMIT ?', (owner,limit))]

    def scene(self, owner, identifier):
        import mujoco as mj
        from .render_geometry import render_geometry
        record = self.get(owner, identifier)  # Authorize even on a cache hit.
        if record['run_id'] is None or record['checkpoint_id'] is None:
            raise ValueError('The compiled scene is not ready yet')
        checkpoint = self.checkpoint(owner, identifier)
        digest = checkpoint['model_sha256'] if isinstance(checkpoint, dict) else checkpoint.model_sha256
        with self.render_lock:
            if digest not in self.render_cache:
                bundle = self.checkpoints.load(record['run_id'], owner, record['checkpoint_id'])
                model = mj.MjModel.from_binary_path('scene.mjb', assets={'scene.mjb':bundle.model_binary})
                self.render_cache[digest] = render_geometry(model, digest)
                while len(self.render_cache) > 2:
                    self.render_cache.popitem(last=False)
            self.render_cache.move_to_end(digest)
            manifest, binary = self.render_cache[digest]
            return dict(manifest, world_version=record['world_version']), binary

    def _admit(self, db, owner, admission_key):
        occupied = sum(path.stat().st_size for path in
                       (Path(self.store.path), Path(self.store.path+'-wal')) if path.exists())
        # Keep at least one large native-model artifact of headroom; admission
        # stops before the operator's persistent-disk allocation is exhausted.
        if occupied+150_000_000 > self.storage_budget_bytes:
            raise AdmissionRejected('Experiment storage budget reached; operator maintenance is required')
        active = db.execute("SELECT COUNT(*) FROM execution_jobs WHERE json_extract(payload,'$.status') "
                            "NOT IN ('completed','failed','cancelled','interrupted')").fetchone()[0]
        if active >= self.max_pending:
            raise AdmissionRejected('Simulation queue is full; retry after a trial finishes')
        since = time.time()-3600.
        owned = db.execute('SELECT COUNT(*) FROM execution_jobs WHERE owner=? AND created>?', (owner, since)).fetchone()[0]
        network = db.execute('SELECT COUNT(*) FROM execution_jobs WHERE admission_key=? AND created>?', (admission_key, since)).fetchone()[0]
        if owned >= self.owner_hourly or network >= self.ip_hourly:
            raise AdmissionRejected('Hourly simulation admission limit reached')

    def submit(self, owner, admission_key, task_name, config):
        if task_name not in self.adapters:
            raise ValueError('Unknown task adapter')
        config = self.adapters[task_name].validate(config)
        with self.condition, self.store.connect() as db:
            if self.stopping:
                raise AdmissionRejected('Runtime is draining for maintenance')
            db.execute('BEGIN IMMEDIATE')
            self._admit(db, owner, admission_key)
            record = {'schema_version': 'vivacity.checkpoint-job/1', 'id': str(uuid.uuid4()),
                      'task': task_name, 'adapter_version': self.adapters[task_name].version,
                      'config': config, 'status': 'queued', 'created_unix_s': time.time(),
                      'run_id': None, 'parent_id': None, 'checkpoint_id': None, 'world_version': None,
                      'next_cursor': 0, 'steps_completed': 0, 'current_phase': None,
                      'partial_measurements': {}, 'compute_wall_s': 0., 'result': None, 'error': None}
            record['pause_deadline_unix_s'] = None
            db.execute('INSERT INTO execution_jobs VALUES(?,?,?,?,?)',
                       (record['id'], owner, admission_key, record['created_unix_s'], encode(record)))
            self.requested[record['id']] = 'queued'
        self.futures.append(self.executor.submit(self._run, owner, record['id']))
        return record

    def control(self, owner, identifier, action, *, wait_s=10.):
        with self.condition, self.store.connect() as db:
            record = self._get(db, owner, identifier)
            if action == 'pause' and record['status'] in ('queued', 'running'):
                record['status'] = 'pausing'
                record['pause_deadline_unix_s'] = time.time()+self.pause_lease_s
            elif action == 'resume' and record['status'] == 'paused':
                record['status'] = 'running'
                record['pause_deadline_unix_s'] = None
            elif action == 'cancel' and record['status'] not in TERMINAL:
                record['status'] = 'cancelling'
            else:
                raise ValueError(f"Cannot {action} a {record['status']} trial")
            self._save(db, owner, record)
            self.requested[identifier] = record['status']
            self.condition.notify_all()
        if action == 'pause':
            deadline = time.monotonic()+wait_s
            with self.condition:
                while time.monotonic() < deadline:
                    record = self.get(owner, identifier)
                    if record['status'] != 'pausing':
                        break
                    self.condition.wait(min(.1, max(0., deadline-time.monotonic())))
        return self.get(owner, identifier)

    def frames(self, owner, identifier, cursor=0, limit=32):
        if cursor < 0 or not 1 <= limit <= 256:
            raise ValueError('Invalid frame pagination')
        # One read snapshot prevents newer frames being paired with older
        # checkpoint/progress metadata while a worker commits another batch.
        with self.store.connect() as db:
            db.execute('BEGIN')
            record = self._get(db, owner, identifier)
            frames = [{'seq':row[0], 'frame':json.loads(row[1])} for row in db.execute(
                'SELECT seq,payload FROM execution_frames WHERE run_id=? AND seq>=? ORDER BY seq LIMIT ?',
                (record['run_id'],cursor,limit))] if record['run_id'] else []
        return {key: record[key] for key in ('status', 'steps_completed', 'current_phase', 'partial_measurements')} | {
            'schema_version': 'vivacity.checkpoint-frames/1', 'id': identifier, 'frames': frames,
            'next_cursor': frames[-1]['seq']+1 if frames else cursor}

    def checkpoint(self, owner, identifier):
        record = self.get(owner, identifier)
        if not record['checkpoint_id']:
            raise ValueError('No checkpoint has been committed yet')
        return self.checkpoints.metadata(record['run_id'], owner, record['checkpoint_id'])

    def fork(self, owner, admission_key, identifier, checkpoint_id=None):
        with self.condition:
            source = self.get(owner, identifier)
            if not source['checkpoint_id'] or self.stopping:
                raise ValueError('A committed checkpoint and an available runtime are required')
            record = deepcopy(source)
            record.update(id=str(uuid.uuid4()), status='queued', parent_id=identifier,
                          created_unix_s=time.time(), next_cursor=0, compute_wall_s=0., result=None, error=None,
                          pause_deadline_unix_s=None)
            def insert(db, run_id, checkpoint):
                self._admit(db, owner, admission_key)
                record.update(run_id=run_id, checkpoint_id=checkpoint.id,
                              steps_completed=checkpoint.steps_completed)
                db.execute('INSERT INTO execution_jobs VALUES(?,?,?,?,?)',
                           (record['id'], owner, admission_key, record['created_unix_s'], encode(record)))
            self.checkpoints.fork(source['run_id'], owner, checkpoint_id, transaction_hook=insert)
            self.requested[record['id']] = 'queued'
        self.futures.append(self.executor.submit(self._run, owner, record['id']))
        return record

    def compare(self, owner, identifiers):
        if not 2 <= len(set(identifiers)) <= 4:
            raise ValueError('Compare two to four distinct trials')
        records = [self.get(owner, identifier) for identifier in identifiers]
        return {'schema_version': 'vivacity.checkpoint-comparison/1',
                'same_world_version': len({r['world_version'] for r in records}) == 1 and all(r['world_version'] for r in records),
                'trials': [{key: r[key] for key in ('id', 'status', 'task', 'config', 'world_version',
                                                  'steps_completed', 'partial_measurements', 'result', 'error')}
                           for r in records]}

    def export(self, owner, identifier):
        record = self.get(owner, identifier)
        if record['status'] not in TERMINAL:
            raise ValueError('Finish or cancel a trial before exporting it')
        frames, cursor = [], 0
        while record['run_id']:
            page = self.checkpoints.frames(record['run_id'], owner, cursor, 256)
            frames.extend(page)
            if len(page) < 256:
                break
            cursor = page[-1]['seq']+1
        return {'schema_version': 'vivacity.checkpoint-report/1', 'trial': record,
                'frames': frames, 'checkpoint': self.checkpoint(owner, identifier).model_dump() if record['checkpoint_id'] else None,
                'export_scope': 'Measured report, frames and checkpoint metadata. The native compiled-model artifact remains in the runtime database; this JSON alone is not a portable simulator.'}

    def _run(self, owner, identifier):
        if self.stopping:
            return
        task, pending, last_frame_step = None, [], -1
        record = self.get(owner, identifier)
        def emit():
            nonlocal last_frame_step
            frame = task.frame()
            frame['steps_completed'] = task.state['steps']
            pending.append(frame)
            last_frame_step = task.state['steps']
        def flush(status=None):
            nonlocal record, pending
            if status in TERMINAL | {'paused', 'suspended'} and last_frame_step != task.state['steps']:
                emit()
            bundle = task.snapshot()
            with self.condition:
                current = self.get(owner, identifier)
                record['pause_deadline_unix_s'] = current.get('pause_deadline_unix_s')
                record.update(status=status or current['status'], checkpoint_id=bundle.checkpoint.id,
                              world_version=task.world_version, next_cursor=bundle.checkpoint.next_frame_seq,
                              steps_completed=bundle.checkpoint.steps_completed,
                              current_phase=task.state['phase'], partial_measurements=deepcopy(task.state.get('last_measurement', {})))
                self.checkpoints.commit(record['run_id'], owner, bundle, pending,
                                        expected_checkpoint_id=current['checkpoint_id'],
                                        transaction_hook=lambda db: self._save(db, owner, record))
                pending = []
                self.requested[identifier] = record['status']
                self.condition.notify_all()

        def boundary():
            with self.condition:
                status = self.requested[identifier]
                if status == 'cancelling':
                    flush('cancelled')
                    return False
                if self.stopping:
                    flush('paused' if status in ('paused', 'pausing') else 'suspended')
                    return False
                if status == 'pausing':
                    flush('paused')
                    status = 'paused'
                while status == 'paused' and not self.stopping:
                    current = self.get(owner, identifier)
                    deadline = current.get('pause_deadline_unix_s') or current['created_unix_s']+self.pause_lease_s
                    if time.time() >= deadline:
                        record['error'] = 'pause_lease_expired'
                        flush('cancelled')
                        return False
                    self.condition.wait(.25)
                    status = self.requested[identifier]
                if self.stopping or status == 'cancelling':
                    return boundary()
                return True
        try:
            adapter = self.adapters.get(record['task'])
            if adapter is None or adapter.version != record['adapter_version']:
                raise ValueError('Task adapter version changed')
            if record['checkpoint_id']:
                task = adapter.restore(self.checkpoints.load(record['run_id'], owner, record['checkpoint_id']))
                last_frame_step = task.state['steps']
                if not record['next_cursor']:
                    emit()
            else:
                started = time.perf_counter()
                task = adapter.create(record['config'])
                record['compute_wall_s'] += time.perf_counter()-started
                record['run_id'] = self.checkpoints.create(owner, task.world_version)
                emit()
            # Honor a recovered paused/cancelled request before advancing physics.
            with self.condition:
                status = self.get(owner, identifier)['status']
                flush('running' if status == 'queued' else status)
            while boundary():
                if task.state['status'] != 'running':
                    with self.condition:
                        if not boundary():
                            break
                        record['result'] = task.result()
                        flush('completed' if record['result']['task_success'] else 'failed')
                    break
                if record['compute_wall_s'] >= self.compute_budget_s or task.state['steps'] >= self.max_steps:
                    record['error'] = 'execution_budget_exceeded'
                    flush('failed')
                    break
                started = time.perf_counter()
                task.step()
                record['compute_wall_s'] += time.perf_counter()-started
                if task.state['steps'] % self.frame_stride == 0 or task.state['status'] != 'running':
                    emit()
                    if len(pending) >= self.frame_batch or record['next_cursor'] < 2:
                        flush()
        except Exception as exc:
            # A failed restore never initializes a replacement simulation.
            with self.condition, self.store.connect() as db:
                current = self._get(db, owner, identifier)
                current.update(status='interrupted', error=f'{type(exc).__name__}: {exc}')
                self._save(db, owner, current)
                self.condition.notify_all()
        finally:
            # The recursive boundary closure forms a Python reference cycle.
            # Release large native models now, rather than waiting for cyclic GC.
            task = None
            pending.clear()

    def close(self):
        with self.condition:
            self.stopping = True
            self.condition.notify_all()
        for future in self.futures:
            future.result()
        if self.owns_executor:
            self.executor.shutdown(wait=True)


class BimanualAdapter:
    version = 'vivacity.stationary-g1-contact-adapter/1-experimental'
    def validate(self, config):
        from .bimanual import BimanualConfig
        return BimanualConfig.model_validate(config).model_dump()
    def create(self, config):
        from .bimanual import BimanualConfig, BimanualTask
        return BimanualTask(BimanualConfig.model_validate(config))
    def restore(self, checkpoint):
        from .bimanual import BimanualTask
        return BimanualTask.from_checkpoint(checkpoint)


class ConstrainedBimanualAdapter(BimanualAdapter):
    version = 'vivacity.constrained-g1-contact-adapter/1-experimental'

    def create(self, config):
        from .bimanual import BimanualConfig
        from .constrained_bimanual import ConstrainedBimanualTask
        return ConstrainedBimanualTask(BimanualConfig.model_validate(config))

    def restore(self, checkpoint):
        from .constrained_bimanual import ConstrainedBimanualTask
        return ConstrainedBimanualTask.from_checkpoint(checkpoint)
