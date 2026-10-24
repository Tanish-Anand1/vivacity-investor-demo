"""Opt-in research interface for checkpointable native contact tasks.

The public production routes and historical humanoid results remain compatible.
This adapter is disabled unless an operator explicitly enables the research gate.
"""
from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .bimanual import BimanualConfig
from .execution_checkpoint import Checkpoint
from .execution_service import AdmissionRejected
from .physical_parameters import parameter_manifest
from .workspace import owner


router = APIRouter(prefix='/v1/robotics/contact', tags=['Experimental contact execution'])
Token = Annotated[str, Header(min_length=32, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')]


class ContactRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['vivacity.contact-request/1'] = 'vivacity.contact-request/1'
    task: Literal['g1_stationary_bimanual', 'g1_constrained_carton'] = 'g1_stationary_bimanual'
    config: BimanualConfig = Field(default_factory=BimanualConfig)


class JobResponse(BaseModel):
    schema_version: Literal['vivacity.checkpoint-job/1'] = 'vivacity.checkpoint-job/1'
    id: str
    task: str
    adapter_version: str
    config: dict
    status: Literal['queued','running','pausing','paused','cancelling','cancelled','suspended','completed','failed','interrupted']
    created_unix_s: float
    run_id: str | None
    parent_id: str | None
    checkpoint_id: str | None
    world_version: str | None
    next_cursor: int
    steps_completed: int
    current_phase: str | None
    partial_measurements: dict
    compute_wall_s: float
    result: dict | None
    error: str | None
    pause_deadline_unix_s: float | None = None


class FrameEntry(BaseModel):
    seq: int
    frame: dict


class FramesResponse(BaseModel):
    schema_version: Literal['vivacity.checkpoint-frames/1'] = 'vivacity.checkpoint-frames/1'
    id: str
    status: str
    frames: list[FrameEntry]
    next_cursor: int
    steps_completed: int
    current_phase: str | None
    partial_measurements: dict


class ForkRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    checkpoint_id: str | None = Field(default=None, max_length=64)


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[str] = Field(min_length=2, max_length=4)


class BufferRange(BaseModel):
    byte_offset: int
    count: int


class SceneMesh(BaseModel):
    id: int
    positions: BufferRange
    indices: BufferRange


class SceneBody(BaseModel):
    id: int
    name: str
    parent_id: int


class SceneGeom(BaseModel):
    id: int
    name: str
    body_id: int
    type: str
    group: int
    mesh_id: int | None
    position: tuple[float, float, float]
    quaternion_wxyz: tuple[float, float, float, float]
    size: tuple[float, float, float]
    rgba: tuple[float, float, float, float]
    contype: int
    conaffinity: int


class CompiledSceneResponse(BaseModel):
    schema_version: Literal['vivacity.compiled-render-geometry/1']
    model_hash: str
    world_version: str
    simulator_version: str
    source: Literal['compiled_mujoco_model']
    coordinates: str
    bodies: list[SceneBody]
    geoms: list[SceneGeom]
    meshes: list[SceneMesh]
    mesh_buffer_sha256: str
    mesh_buffer_bytes: int


def runtime(request: Request):
    service = getattr(request.app.state, 'contact_execution', None)
    if service is None:
        raise HTTPException(503, 'Contact-only research tasks are disabled pending the Physical Truth release gates')
    return service


def admission_key(request):
    # The ASGI server must trust forwarding headers only from the hosting proxy.
    # Do not accept a caller-supplied X-Forwarded-For directly here.
    address = request.client.host if request.client else 'unknown'
    return hashlib.sha256(address.encode()).hexdigest()


@router.get('/capabilities')
def capabilities(request: Request):
    return {'schema_version': 'vivacity.contact-capabilities/1',
            'enabled': getattr(request.app.state, 'contact_execution', None) is not None,
            'release_status': 'experimental', 'observation_modes': ['simulator_state'],
            'tasks': [{'id': 'g1_stationary_bimanual', 'embodiment': 'unitree_g1_with_hands',
                       'tooling': 'native articulated hands', 'motion_source': 'native MuJoCo steps',
                       'scope': 'Stationary contact-only carton transfer. Whole-body inverse dynamics, locomotion, camera-controlled operation and hardware validation have not passed release gates.'},
                      {'id':'g1_constrained_carton', 'embodiment':'unitree_g1_with_hands',
                       'tooling':'native articulated hands', 'motion_source':'native MuJoCo steps',
                       'scope':'Experimental constrained contact-wrench controller using the unchanged native actuator model. Full robustness, locomotion, camera control and hardware release gates remain open.'}],
            'parcel_parameters': parameter_manifest()}


@router.post('/experiments', response_model=JobResponse, status_code=202)
def start(body: ContactRequest, request: Request, x_workspace_token: Token, service=Depends(runtime)):
    try:
        return service.submit(owner(x_workspace_token), admission_key(request), body.task, body.config.model_dump())
    except AdmissionRejected as exc:
        raise HTTPException(429, str(exc), headers={'Retry-After':'60'}) from exc


@router.get('/experiments', response_model=list[JobResponse])
def history(x_workspace_token: Token, limit: int=Query(default=20,ge=1,le=20), service=Depends(runtime)):
    return service.history(owner(x_workspace_token), limit)


@router.get('/experiments/{identifier}', response_model=JobResponse)
def status(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    return service.get(owner(x_workspace_token), identifier)


@router.get('/experiments/{identifier}/frames', response_model=FramesResponse)
def frames(identifier: str, x_workspace_token: Token, cursor: int=Query(default=0,ge=0),
           limit: int=Query(default=32,ge=1,le=64), service=Depends(runtime)):
    return service.frames(owner(x_workspace_token), identifier, cursor, limit)


@router.post('/experiments/{identifier}/pause', response_model=JobResponse)
def pause(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    return service.control(owner(x_workspace_token), identifier, 'pause')


@router.post('/experiments/{identifier}/resume', response_model=JobResponse)
def resume(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    return service.control(owner(x_workspace_token), identifier, 'resume')


@router.post('/experiments/{identifier}/cancel', response_model=JobResponse)
def cancel(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    return service.control(owner(x_workspace_token), identifier, 'cancel')


@router.get('/experiments/{identifier}/checkpoint', response_model=Checkpoint)
def checkpoint(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    return service.checkpoint(owner(x_workspace_token), identifier)


@router.get('/experiments/{identifier}/scene', response_model=CompiledSceneResponse)
def scene(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    try:
        return service.scene(owner(x_workspace_token), identifier)[0]
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/experiments/{identifier}/meshes', response_class=Response,
            responses={200:{'content':{'application/octet-stream':{'schema':{'type':'string','format':'binary'}}}}})
def meshes(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    try:
        manifest, binary = service.scene(owner(x_workspace_token), identifier)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(binary, media_type='application/octet-stream', headers={
        'ETag':'"'+manifest['mesh_buffer_sha256']+'"', 'Cache-Control':'private, max-age=3600',
        'X-Content-Type-Options':'nosniff'})


@router.post('/experiments/{identifier}/fork', response_model=JobResponse, status_code=202)
def fork(identifier: str, body: ForkRequest, request: Request, x_workspace_token: Token, service=Depends(runtime)):
    try:
        return service.fork(owner(x_workspace_token), admission_key(request), identifier, body.checkpoint_id)
    except AdmissionRejected as exc:
        raise HTTPException(429, str(exc), headers={'Retry-After':'60'}) from exc


@router.post('/compare')
def compare(body: CompareRequest, x_workspace_token: Token, service=Depends(runtime)):
    return service.compare(owner(x_workspace_token), body.ids)


@router.get('/experiments/{identifier}/export')
def export(identifier: str, response: Response, x_workspace_token: Token, service=Depends(runtime)):
    exported = service.export(owner(x_workspace_token), identifier)
    response.headers['Content-Disposition'] = 'attachment; filename="contact-experiment.json"'
    return exported


@router.get('/experiments/{identifier}/replay')
def replay(identifier: str, x_workspace_token: Token, service=Depends(runtime)):
    exported = service.export(owner(x_workspace_token), identifier)
    return {'schema_version': 'vivacity.checkpoint-replay/1', 'id': identifier,
            'status': exported['trial']['status'], 'frames': exported['frames'],
            'world_version': exported['trial']['world_version']}
