"""Full native simulator checkpoints plus controller/task memory.

Model binaries are immutable, content-addressed artifacts, stored once even when
many checkpoints refer to them. A binary includes mutable model configuration;
qpos alone is never a checkpoint. Loading creates a private MjModel and MjData.
This module is deliberately independent of HTTP and individual robot tasks.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import uuid
import zlib
from typing import Any, Protocol

import mujoco as mj
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from .storage import Store, encode

STATE = mj.mjtState.mjSTATE_INTEGRATION


class StatefulController(Protocol):
    version: str

    def snapshot(self) -> dict: ...
    def restore(self, state: dict) -> None: ...


class IncompatibleCheckpoint(ValueError):
    pass


class Checkpoint(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, frozen=True)
    schema_version: str = 'vivacity.execution-checkpoint/1'
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    world_version: str
    model_sha256: str
    simulator_version: str
    state_spec: int = int(STATE)
    integration_state: list[float]
    controller_version: str
    controller_state: dict[str, Any]
    previous_action: list[float]
    task_state: dict[str, Any]
    random_state: dict[str, Any]
    perception_state: dict[str, Any]
    order_ledger: dict[str, Any]
    next_frame_seq: int = Field(ge=0)
    steps_completed: int = Field(ge=0)
    parent_checkpoint_id: str | None = None


@dataclass(frozen=True)
class CheckpointBundle:
    checkpoint: Checkpoint
    model_binary: bytes


def model_bytes(model):
    buffer = np.empty(mj.mj_sizeModel(model), dtype=np.uint8)
    mj.mj_saveModel(model, buffer=buffer)
    return buffer.tobytes()


def _numpy_json(value):
    """Preserve integer RNG words without pickle or lossy float conversion."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key:_numpy_json(item) for key,item in value.items()}
    if isinstance(value, (list,tuple)):
        return [_numpy_json(item) for item in value]
    return value


def _configuration_fingerprint(model):
    """Hash exposed model arrays/options without copying large mesh buffers."""
    digest = hashlib.sha256()
    def visit(value, prefix, depth):
        for name in sorted(n for n in dir(value) if not n.startswith('_')):
            item = getattr(value, name)
            key = f'{prefix}.{name}'
            if isinstance(item, np.ndarray):
                digest.update(f'{key}:{item.dtype}:{item.shape}'.encode())
                if item.size:
                    digest.update(memoryview(np.ascontiguousarray(item)).cast('B'))
            elif isinstance(item, (int, float, str, bool)):
                digest.update(f'{key}:{item!r}'.encode())
            elif depth and type(item).__module__ == 'mujoco._structs' and not callable(item):
                visit(item, key, depth-1)
    visit(model, 'model', 3)
    return digest.hexdigest()


class ImmutableModelArtifact:
    """Reuse a version's binary; refuse capture if its model was mutated.

    Hashing direct array views avoids reserializing 100+ MB of immutable visual
    meshes for every frame batch. Generic capture still supports changing model
    configuration by creating a fresh binary when no artifact is supplied.
    """
    def __init__(self, model, binary=None):
        self.binary = model_bytes(model) if binary is None else binary
        self.sha256 = hashlib.sha256(self.binary).hexdigest()
        self.fingerprint = _configuration_fingerprint(model)

    def verify(self, model):
        if _configuration_fingerprint(model) != self.fingerprint:
            raise IncompatibleCheckpoint('immutable model changed; create a new world version')


def capture(model, data, controller: StatefulController, *, world_version: str,
            task_state: dict, rng: np.random.Generator, perception_state: dict,
            order_ledger: dict, next_frame_seq: int, steps_completed: int,
            parent_checkpoint_id=None, model_artifact: ImmutableModelArtifact | None = None) -> CheckpointBundle:
    if model_artifact is not None:
        model_artifact.verify(model)
    binary = model_artifact.binary if model_artifact is not None else model_bytes(model)
    integration = np.empty(mj.mj_stateSize(model, STATE))
    mj.mj_getState(model, data, integration, STATE)
    checkpoint = Checkpoint(
        world_version=world_version, model_sha256=model_artifact.sha256 if model_artifact else hashlib.sha256(binary).hexdigest(),
        simulator_version=mj.__version__, integration_state=integration.tolist(),
        controller_version=controller.version, controller_state=deepcopy(controller.snapshot()),
        previous_action=data.ctrl.tolist(), task_state=deepcopy(task_state),
        random_state=_numpy_json(rng.bit_generator.state),
        perception_state=deepcopy(perception_state), order_ledger=deepcopy(order_ledger),
        next_frame_seq=next_frame_seq, steps_completed=steps_completed,
        parent_checkpoint_id=parent_checkpoint_id)
    # Reject non-JSON and nonfinite nested controller/task/perception values.
    encode(checkpoint.model_dump())
    return CheckpointBundle(checkpoint, binary)


def restore(bundle: CheckpointBundle, controller_factory):
    checkpoint = bundle.checkpoint
    if checkpoint.schema_version != 'vivacity.execution-checkpoint/1':
        raise IncompatibleCheckpoint('unknown checkpoint schema')
    if checkpoint.simulator_version != mj.__version__ or checkpoint.state_spec != int(STATE):
        raise IncompatibleCheckpoint('simulator version or state specification changed')
    if hashlib.sha256(bundle.model_binary).hexdigest() != checkpoint.model_sha256:
        raise IncompatibleCheckpoint('model artifact checksum mismatch')
    model = mj.MjModel.from_binary_path('checkpoint.mjb', assets={'checkpoint.mjb': bundle.model_binary})
    data = mj.MjData(model)
    if len(checkpoint.integration_state) != mj.mj_stateSize(model, STATE):
        raise IncompatibleCheckpoint('integration state does not match model')
    controller = controller_factory(model)
    if controller.version != checkpoint.controller_version:
        raise IncompatibleCheckpoint('controller version changed')
    mj.mj_setState(model, data, np.asarray(checkpoint.integration_state), STATE)
    # mj_forward refreshes derived quantities but can update warmstart buffers.
    # Restore the full integration state again so continuation uses the saved
    # warmstart, controls and applied forces exactly.
    mj.mj_forward(model, data)
    mj.mj_setState(model, data, np.asarray(checkpoint.integration_state), STATE)
    if data.ctrl.tolist() != checkpoint.previous_action:
        raise IncompatibleCheckpoint('stored action disagrees with integration state')
    controller.restore(deepcopy(checkpoint.controller_state))
    bit_generator_name = checkpoint.random_state.get('bit_generator')
    generators = {name: getattr(np.random, name) for name in
                  ('PCG64', 'PCG64DXSM', 'Philox', 'SFC64', 'MT19937')}
    if bit_generator_name not in generators:
        raise IncompatibleCheckpoint('unsupported random generator')
    rng = np.random.Generator(generators[bit_generator_name]())
    rng.bit_generator.state = deepcopy(checkpoint.random_state)
    return model, data, controller, rng


class CheckpointStore:
    """Commit a frame batch and its matching checkpoint in one SQLite transaction.

    Compare-and-swap on the previous checkpoint prevents stale workers and
    concurrent writers from duplicating or skipping authoritative frame numbers.
    Owner scoping is checked for every lookup, including model artifact retrieval.
    """
    def __init__(self, store: Store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS execution_models(
              sha256 TEXT PRIMARY KEY, compressed_binary BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS execution_runs(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL, world_version TEXT NOT NULL,
              checkpoint_id TEXT, parent_run_id TEXT);
            CREATE TABLE IF NOT EXISTS execution_checkpoints(
              id TEXT PRIMARY KEY, run_id TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS execution_frames(
              run_id TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY(run_id,seq));
            ''')

    def create(self, owner, world_version, *, parent_run_id=None):
        run_id = str(uuid.uuid4())
        with self.store.connect() as db:
            if parent_run_id is not None:
                self._owned(db, parent_run_id, owner)
            db.execute('INSERT INTO execution_runs VALUES(?,?,?,?,?)',
                       (run_id, owner, world_version, None, parent_run_id))
        return run_id

    @staticmethod
    def _owned(db, run_id, owner):
        row = db.execute('SELECT world_version,checkpoint_id FROM execution_runs WHERE id=? AND owner=?',
                         (run_id, owner)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return row

    def commit(self, run_id, owner, bundle: CheckpointBundle, frames: list[dict], *, expected_checkpoint_id,
               transaction_hook=None):
        checkpoint = bundle.checkpoint
        if hashlib.sha256(bundle.model_binary).hexdigest() != checkpoint.model_sha256:
            raise IncompatibleCheckpoint('model artifact checksum mismatch')
        encoded_checkpoint = encode(checkpoint.model_dump())
        encoded_frames = [encode(frame) for frame in frames]
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            version, previous_id = self._owned(db, run_id, owner)
            if version != checkpoint.world_version:
                raise IncompatibleCheckpoint('world version changed')
            if previous_id != expected_checkpoint_id:
                raise ValueError('stale checkpoint writer')
            next_seq = db.execute('SELECT COALESCE(MAX(seq)+1,0) FROM execution_frames WHERE run_id=?',
                                  (run_id,)).fetchone()[0]
            if next_seq+len(frames) != checkpoint.next_frame_seq:
                raise ValueError('frame batch does not match checkpoint cursor')
            if previous_id:
                previous = json.loads(db.execute('SELECT payload FROM execution_checkpoints WHERE id=?',
                                                  (previous_id,)).fetchone()[0])
                if checkpoint.steps_completed < previous['steps_completed']:
                    raise ValueError('simulation step counter moved backwards')
                if checkpoint.model_sha256 != previous['model_sha256']:
                    raise IncompatibleCheckpoint('model changed within immutable world version')
            if db.execute('SELECT 1 FROM execution_models WHERE sha256=?', (checkpoint.model_sha256,)).fetchone() is None:
                db.execute('INSERT INTO execution_models VALUES(?,?)',
                           (checkpoint.model_sha256, zlib.compress(bundle.model_binary, level=1)))
            db.execute('INSERT INTO execution_checkpoints VALUES(?,?,?)',
                       (checkpoint.id, run_id, encoded_checkpoint))
            db.executemany('INSERT INTO execution_frames VALUES(?,?,?)',
                           [(run_id, next_seq+i, frame) for i, frame in enumerate(encoded_frames)])
            db.execute('UPDATE execution_runs SET checkpoint_id=? WHERE id=?', (checkpoint.id, run_id))
            if transaction_hook is not None:
                transaction_hook(db)

    def _metadata(self, db, run_id, owner, checkpoint_id):
        _, latest = self._owned(db, run_id, owner)
        row = db.execute('SELECT payload FROM execution_checkpoints WHERE id=? AND run_id=?',
                         (checkpoint_id or latest, run_id)).fetchone()
        if row is None:
            raise KeyError(checkpoint_id or run_id)
        checkpoint = Checkpoint.model_validate_json(row[0])
        if db.execute('SELECT 1 FROM execution_models WHERE sha256=?',
                      (checkpoint.model_sha256,)).fetchone() is None:
            raise IncompatibleCheckpoint('model artifact missing')
        return checkpoint

    def metadata(self, run_id, owner, checkpoint_id=None):
        # Inspection must not inflate a large native mesh/model artifact.
        # Full binaries are needed only when actually restoring a simulator.
        with self.store.connect() as db:
            return self._metadata(db, run_id, owner, checkpoint_id)

    def load(self, run_id, owner, checkpoint_id=None):
        with self.store.connect() as db:
            checkpoint = self._metadata(db, run_id, owner, checkpoint_id)
            binary = db.execute('SELECT compressed_binary FROM execution_models WHERE sha256=?',
                                (checkpoint.model_sha256,)).fetchone()
            if binary is None:
                raise IncompatibleCheckpoint('model artifact missing')
            return CheckpointBundle(checkpoint, zlib.decompress(binary[0]))

    def frames(self, run_id, owner, cursor=0, limit=32):
        if cursor < 0 or not 1 <= limit <= 256:
            raise ValueError('invalid frame pagination')
        with self.store.connect() as db:
            self._owned(db, run_id, owner)
            return [{'seq': row[0], 'frame': json.loads(row[1])} for row in db.execute(
                'SELECT seq,payload FROM execution_frames WHERE run_id=? AND seq>=? ORDER BY seq LIMIT ?',
                (run_id, cursor, limit))]

    def fork(self, run_id, owner, checkpoint_id=None, *, transaction_hook=None):
        parent = self.metadata(run_id, owner, checkpoint_id)
        checkpoint = parent.model_copy(update={'id': str(uuid.uuid4()), 'next_frame_seq': 0,
                                               'parent_checkpoint_id': parent.id}, deep=True)
        branch = str(uuid.uuid4())
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._owned(db, run_id, owner)
            db.execute('INSERT INTO execution_runs VALUES(?,?,?,?,?)',
                       (branch, owner, parent.world_version, checkpoint.id, run_id))
            db.execute('INSERT INTO execution_checkpoints VALUES(?,?,?)',
                       (checkpoint.id, branch, encode(checkpoint.model_dump())))
            if transaction_hook is not None:
                transaction_hook(db, branch, checkpoint)
        return branch
