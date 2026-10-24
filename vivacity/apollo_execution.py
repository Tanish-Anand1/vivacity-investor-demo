"""Run the measured Apollo door primitive through the shared checkpoint worker.

The primitive is an experimental latch-and-door task. A successful primitive
does not imply cartridge service or completion of the cabinet benchmark.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import mujoco as mj
from pydantic import BaseModel, ConfigDict, Field

from .cabinet_mechanism import CabinetConfig
from .simulated_tooling import ParallelGripperConfig


ADAPTER_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class ApolloDoorSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    cabinet: CabinetConfig = Field(default_factory=lambda: CabinetConfig(front_x_m=.75))
    tooling: ParallelGripperConfig = Field(default_factory=ParallelGripperConfig)
    opening_angle_rad: float = Field(default=.25, ge=.25, le=1.2)
    seed: int = Field(default=7, ge=0, le=2**31-1)


class ApolloDoorExecutable:
    """Translate the primitive's measured state into the common task protocol."""

    def __init__(self, primitive):
        self.primitive = primitive
        self.world_version = primitive.world_version
        self.state = primitive.state
        self.state.setdefault('execution_adapter_source_sha256', ADAPTER_SOURCE_SHA256)
        self.state.setdefault('steps', self.state['steps_completed'])
        self.state.setdefault('last_measurement', primitive.observe())

    def step(self):
        self.primitive.step()
        self.state['steps'] = self.state['steps_completed']

    def frame(self):
        packed = self.primitive.frame()
        self.state['last_measurement'] = packed['measurements']
        return {**packed['frame'], 'phase': packed['phase'],
                'measurement': deepcopy(packed['measurements']),
                'grasp_constraint_active': False}

    def snapshot(self):
        if self.state['execution_adapter_source_sha256'] != ADAPTER_SOURCE_SHA256:
            raise ValueError('Apollo execution adapter changed')
        if self.state['steps'] != self.state['steps_completed']:
            raise ValueError('Apollo step counters disagree')
        return self.primitive.snapshot()

    @classmethod
    def from_checkpoint(cls, bundle):
        if bundle.checkpoint.task_state.get('execution_adapter_source_sha256') != ADAPTER_SOURCE_SHA256:
            raise ValueError('Apollo execution adapter changed')
        from .apollo_door import CabinetDoorPrimitive

        primitive = CabinetDoorPrimitive.from_checkpoint(bundle)
        # A fork starts a new frame stream at zero while retaining the same
        # simulator time and controller memory as its parent checkpoint.
        primitive.state['next_frame_seq'] = bundle.checkpoint.next_frame_seq
        return cls(primitive)

    def result(self):
        primitive = self.primitive
        state = self.state
        return {'schema_version': 'vivacity.apollo-door-execution/1-experimental',
                'controller': primitive.controller.version,
                'status': state['status'],
                'task_success': bool(state['status'] == 'completed' and state['success']),
                'cabinet_service_complete': False,
                'failure_reason': state['failure'],
                'failure_detail': deepcopy(state.get('failure_detail')),
                'parameters': {'cabinet': primitive.config.model_dump(),
                               'tooling': primitive.tooling.model_dump(),
                               'opening_angle_rad': state['opening_angle_rad'],
                               'seed': state['seed']},
                'world_version': self.world_version,
                'simulator_version': mj.__version__,
                'model_sha256': primitive.artifact.sha256,
                'source_sha256': {**state['source_hashes'],
                                  'apollo_execution.py': ADAPTER_SOURCE_SHA256},
                'equality_constraints': primitive.model.neq,
                'mocap_bodies': primitive.model.nmocap,
                'measurements': deepcopy(state['last_measurement']),
                'phase_events': deepcopy(state['phase_events']),
                'planning_events': deepcopy(state['planning_events']),
                'scope': 'Experimental contact-operated latch and door opening. '
                         'No cartridge extraction, replacement, or full cabinet service.'}


class ApolloDoorAdapter:
    version = 'vivacity.apollo-door-checkpoint-adapter/3-experimental'

    def validate(self, config):
        return ApolloDoorSettings.model_validate(config).model_dump()

    def create(self, config):
        from .apollo_door import CabinetDoorPrimitive

        settings = ApolloDoorSettings.model_validate(config)
        return ApolloDoorExecutable(CabinetDoorPrimitive(
            settings.cabinet, settings.tooling, settings.seed, settings.opening_angle_rad))

    def restore(self, checkpoint):
        return ApolloDoorExecutable.from_checkpoint(checkpoint)
