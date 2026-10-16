"""Workspace transport; simulator jobs remain owned by Runtime/Supervisor."""
from typing import Annotated
import os
import asyncio
from fastapi import APIRouter, Header, Request, Query, HTTPException
from fastapi.responses import FileResponse

from .workspace_schemas import (LibraryWorld, RenameRequest, GenerationRequest, GenerationResponse, ImportMapping,
    ExperimentConfiguration, ConfigurationResponse, ResolvedConfiguration, CustomOperationRequest, RunOverrides)
from .registry import registry
from .workspace import owner
from .providers import ProviderError
from .imports import MAX_UPLOAD
from .schemas import ImportPreview

Token=Annotated[str,Header(alias='X-Workspace-Token',min_length=32,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')]
Key=Annotated[str,Header(alias='Idempotency-Key',min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')]
router=APIRouter(prefix='/v1/workspace',tags=['Worlds and experiment workspace'])

def public_world(record):
    return {k:v for k,v in record.items() if not k.startswith('_')}



@router.get('/capabilities')
def capabilities(request:Request):
    return {'schema_version':'vivacity.workspace/1.0','openai_configured':bool(os.getenv('OPENAI_API_KEY')),
            'worldlabs_configured':bool(os.getenv('WORLDLABS_API_KEY')),'registry':registry(),
            'formats':['glb','gltf','obj','stl','mjcf','xml','urdf','manifest_zip'],
            'max_upload_bytes':MAX_UPLOAD,'max_physics_trials':request.app.state.runtime.max_physics_trials,
            'generations_per_day':int(os.getenv('VIVACITY_GENERATIONS_PER_DAY','4')),
            'scope':'Library ownership uses a browser capability, not user accounts. Rendering and physical simulation remain separate.'}


@router.get('/worlds',response_model=list[LibraryWorld])
def worlds(request:Request,x_workspace_token:Token):return [public_world(w) for w in request.app.state.workspace.worlds(x_workspace_token)]


@router.get('/materials')
def materials():
    from .physical_properties import registry
    return registry()


from .workspace_schemas import PhysicsValidationResponse


@router.post('/physics-validations', status_code=201, response_model=PhysicsValidationResponse)
async def physics_validation(request: Request, x_workspace_token: Token):
    import time
    from .physics_validation import run_benchmarks
    workspace = request.app.state.workspace
    # Atomically cap public CPU requests; no unbounded benchmark load.
    with workspace.store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS physics_validation_calls(created REAL)')
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT COUNT(*) FROM physics_validation_calls WHERE created>?', (time.time()-86400,)).fetchone()[0]>=50:
            raise HTTPException(429, 'daily physics-validation budget reached')
        db.execute('INSERT INTO physics_validation_calls VALUES(?)', (time.time(),))
    record = await asyncio.to_thread(run_benchmarks)
    workspace._put('physics_validation', owner(x_workspace_token), record)
    return record


@router.get('/physics-validations/{identifier}', response_model=PhysicsValidationResponse)
def physics_validation_report(identifier: str, request: Request, x_workspace_token: Token):
    return request.app.state.workspace._get(identifier, x_workspace_token, 'physics_validation')


@router.get('/worlds/{identifier}',response_model=LibraryWorld)
def world(identifier:str,request:Request,x_workspace_token:Token):return public_world(request.app.state.workspace.world(identifier,x_workspace_token))


@router.post('/worlds',response_model=LibraryWorld,status_code=201)
def duplicate_world(body:dict,request:Request,x_workspace_token:Token):
    if set(body)!={'source_id'} or not isinstance(body['source_id'],str):raise ValueError('supply a source_id to duplicate')
    return public_world(request.app.state.workspace.duplicate(body['source_id'],x_workspace_token))


@router.patch('/worlds/{identifier}',response_model=LibraryWorld)
def rename(identifier:str,body:RenameRequest,request:Request,x_workspace_token:Token):return public_world(request.app.state.workspace.rename(identifier,x_workspace_token,body.name))


@router.post('/worlds/{identifier}/archive',response_model=LibraryWorld)
def archive(identifier:str,request:Request,x_workspace_token:Token):return public_world(request.app.state.workspace.set_deleted(identifier,x_workspace_token,True))


@router.post('/worlds/{identifier}/restore',response_model=LibraryWorld)
def restore(identifier:str,request:Request,x_workspace_token:Token):return public_world(request.app.state.workspace.set_deleted(identifier,x_workspace_token,False))


@router.get('/worlds/{identifier}/preview',response_model=ImportPreview)
def preview(identifier:str,request:Request,x_workspace_token:Token):
    record=request.app.state.workspace.world(identifier,x_workspace_token)
    if not record.get('import_id'):raise ValueError('primitive scenes use their typed scene specification for preview')
    return request.app.state.imports.get(record['import_id'],preview=True)


@router.get('/worlds/{identifier}/appearance')
def appearance(identifier:str,request:Request,x_workspace_token:Token,quality:Annotated[str|None,Query(pattern=r'^(100k|500k)$')]=None):
    try:
        path=request.app.state.workspace.visual_asset(identifier,x_workspace_token,quality)
        return FileResponse(path,media_type='model/gltf-binary' if path.suffix=='.glb' else 'application/octet-stream',filename='world'+path.suffix,
                            headers={'Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff'})
    except ProviderError as error:raise HTTPException(502,str(error)) from None


@router.get('/worlds/{identifier}/thumbnail')
def thumbnail(identifier:str,request:Request,x_workspace_token:Token):
    try:
        path=request.app.state.workspace.thumbnail_asset(identifier,x_workspace_token)
        first=path.read_bytes()[:12]
        mime='image/png' if first.startswith(b'\x89PNG') else 'image/webp' if first[:4]==b'RIFF' else 'image/jpeg'
        return FileResponse(path,media_type=mime,headers={'Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff'})
    except ProviderError as error:raise HTTPException(502,str(error)) from None


@router.get('/worlds/{identifier}/geometry')
def original_geometry(identifier:str,request:Request,x_workspace_token:Token):
    world=request.app.state.workspace.world(identifier,x_workspace_token)
    if not world.get('import_id'):raise HTTPException(404,'this world has no source GLB')
    request.app.state.imports.get(world['import_id'])
    path=request.app.state.imports.root/(world['import_id']+'.glb')
    if not path.is_file():raise HTTPException(404,'source GLB bytes unavailable')
    return FileResponse(path,media_type='model/gltf-binary',filename='source-collider.glb',headers={'X-Content-Type-Options':'nosniff'})


from .workspace_schemas import CaptureResponse
from .spatial import MAX_CAPTURE


@router.post('/captures',status_code=201,response_model=CaptureResponse)
async def capture(request:Request,x_workspace_token:Token,filename:str=Query(min_length=1,max_length=64)):
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>MAX_CAPTURE:raise ValueError('capture exceeds 16 MiB')
    return await asyncio.to_thread(request.app.state.workspace.capture,filename,bytes(content),x_workspace_token)


@router.get('/captures',response_model=list[CaptureResponse])
def captures(request:Request,x_workspace_token:Token):return request.app.state.workspace.list(x_workspace_token,'capture')


@router.post('/imports',status_code=201)
async def upload(request:Request,x_workspace_token:Token,filename:str=Query(min_length=1,max_length=180)):
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>MAX_UPLOAD:raise ValueError('upload exceeds 16 MiB')
    record=await asyncio.to_thread(request.app.state.imports.create,filename,bytes(content))
    request.app.state.workspace._put('staged_import',owner(x_workspace_token),record)
    return record


@router.post('/imports/{identifier}/map',response_model=LibraryWorld,status_code=201)
def map_import(identifier:str,body:ImportMapping,request:Request,x_workspace_token:Token):
    record=request.app.state.workspace._get(identifier,x_workspace_token,'staged_import')
    preview=request.app.state.imports.get(identifier,preview=True)
    return public_world(request.app.state.workspace.map_import(record,preview,body,x_workspace_token))


@router.get('/imports/{identifier}/preview',response_model=ImportPreview)
def staged_import_preview(identifier:str,request:Request,x_workspace_token:Token):
    request.app.state.workspace._get(identifier,x_workspace_token,'staged_import')
    return request.app.state.imports.get(identifier,preview=True)


@router.post('/generations',response_model=GenerationResponse,status_code=202)
def generate(body:GenerationRequest,request:Request,x_workspace_token:Token,idempotency_key:Key):
    try:return request.app.state.workspace.generate(body,x_workspace_token,idempotency_key)
    except ProviderError as error:raise HTTPException(503,str(error)) from None


@router.get('/generations/{identifier}',response_model=GenerationResponse)
def generation(identifier:str,request:Request,x_workspace_token:Token):return request.app.state.workspace.generation(identifier,x_workspace_token)


@router.get('/generations',response_model=list[GenerationResponse])
def generations(request:Request,x_workspace_token:Token):
    workspace=request.app.state.workspace
    return [workspace.generation(j['id'],x_workspace_token) for j in workspace.list(x_workspace_token,'generation')]


@router.post('/generations/{identifier}/retry-retrieval',response_model=GenerationResponse,status_code=202)
def retry_retrieval(identifier:str,request:Request,x_workspace_token:Token):return request.app.state.workspace.retry_retrieval(identifier,x_workspace_token)


@router.post('/configurations/resolve',response_model=ResolvedConfiguration)
def resolve(body:ExperimentConfiguration,request:Request,x_workspace_token:Token):return request.app.state.workspace.resolve(body,x_workspace_token)


@router.post('/configurations',response_model=ConfigurationResponse,status_code=201)
def save(body:ExperimentConfiguration,request:Request,x_workspace_token:Token):return request.app.state.workspace.save_configuration(body,x_workspace_token)


@router.get('/configurations',response_model=list[ConfigurationResponse])
def configurations(request:Request,x_workspace_token:Token):return request.app.state.workspace.list(x_workspace_token,'configuration')


@router.get('/configurations/{identifier}',response_model=ConfigurationResponse)
def configuration(identifier:str,request:Request,x_workspace_token:Token):return request.app.state.workspace.configuration(identifier,x_workspace_token)


@router.post('/configurations/{identifier}/runs',status_code=201)
def run(identifier:str,body:RunOverrides,request:Request,x_workspace_token:Token):return request.app.state.workspace.start_run(identifier,x_workspace_token,body.config)


@router.get('/runs')
def runs(request:Request,x_workspace_token:Token):return request.app.state.workspace.runs(x_workspace_token)


from .workspace_schemas import MeasurementRequest


@router.post('/runs/{sid}/measurements',status_code=201)
def compare_measurements(sid:str,body:MeasurementRequest,request:Request,x_workspace_token:Token):
    return request.app.state.workspace.compare_measurements(sid,body,x_workspace_token)


@router.get('/measurement-comparisons')
def measurement_comparisons(request:Request,x_workspace_token:Token):
    return request.app.state.workspace.list(x_workspace_token,'measurement_comparison')


@router.post('/operations/interpret')
def operation(body:CustomOperationRequest,request:Request,x_workspace_token:Token):
    workspace=request.app.state.workspace
    workspace.world(body.environment_id,x_workspace_token)
    # Count the call against the same bounded global budget, rather than exposing
    # an unlimited public paid inference endpoint.
    with workspace.store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS operation_calls(created REAL)')
        import time
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT COUNT(*) FROM operation_calls WHERE created>?',(time.time()-86400,)).fetchone()[0]>=20:
            raise HTTPException(429,'daily interpretation budget reached')
        db.execute('INSERT INTO operation_calls VALUES(?)',(time.time(),))
    try:
        proposal,provenance=workspace.interpreter.operation(body.prompt,body.environment_id)
        if proposal.supported:workspace.resolve(proposal.configuration,x_workspace_token)
        return {'proposal':proposal.model_dump(),'provenance':provenance}
    except ProviderError as error:raise HTTPException(503,str(error)) from None
