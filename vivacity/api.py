from contextlib import asynccontextmanager
from typing import Annotated
import asyncio
import os
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .runtime import Runtime, Conflict, Busy, Unavailable
from .schemas import CreateWorld, ExperimentRequest, EnvironmentPatch, CommitRequest, WorldResponse, ExperimentResponse, BranchResponse, StateResponse, ReplayResponse, EventResponse, BranchExport, WorldEditorResponse, EditorChange, EditorGeometryAction, EditorMove, WorldVersion, RestoreWorldVersion
from .schemas import ImportResponse,ImportPreview
from .schemas import SessionRequest,SessionResponse,LiveState,TrialsResponse
from .imports import ImportService,MAX_UPLOAD
from pathlib import Path
from starlette.requests import HTTPConnection
from .templates import TemplateSelection, TemplateCatalog, catalog, resolve
from .v_robotics import RoboticsProgramCatalog, RoboticsExperimentReport, catalog as robotics_catalog, experiment_report as robotics_report
from .humanoids import HumanoidFramesResponse, HumanoidModelResponse, HumanoidTrialRequest, HumanoidTrialResponse, HumanoidTrialService, model_info as humanoid_model_info
from .workspace import owner as workspace_owner


def create_app(database=None):
    from .credentials import load_host_credentials
    load_host_credentials()
    @asynccontextmanager
    async def lifespan(app):
        path=database or os.getenv('VIVACITY_DATABASE', 'data/vivacity.sqlite3')
        app.state.runtime = Runtime(path)
        app.state.humanoids = HumanoidTrialService(app.state.runtime.store)
        app.state.imports = app.state.runtime.imports
        from .workspace import WorkspaceService
        app.state.workspace = WorkspaceService(app.state.runtime)
        from .factory_service import FactoryService
        app.state.factory = FactoryService(app.state.workspace)
        from .fulfillment import FulfillmentService
        app.state.fulfillment = FulfillmentService(app.state.factory)
        yield
        await asyncio.to_thread(app.state.humanoids.close)
        await asyncio.to_thread(app.state.factory.close)
        await asyncio.to_thread(app.state.workspace.close)
        await asyncio.to_thread(app.state.runtime.close)

    def authorize_request(request:HTTPConnection):
        if request.scope['type']!='http':return
        parts=request.url.path.strip('/').split('/')
        if len(parts)<3 or parts[0]!='v1':return
        runtime=request.app.state.runtime
        if parts[1]=='worlds':
            world_id=parts[2]
        elif parts[1]=='experiments':
            world_id=runtime.get_experiment(parts[2])['world_id']
        elif parts[1]=='imports':
            from .workspace import owner
            with runtime.store.connect() as db:
                owners=db.execute("SELECT DISTINCT owner FROM library_items WHERE (kind='staged_import' AND id=?) OR (kind='world' AND json_extract(payload,'$.import_id')=?)",(parts[2],parts[2])).fetchall()
            if owners and owner(request.headers.get('x-workspace-token','')) not in {r[0] for r in owners}:
                raise HTTPException(403,'workspace capability required for this imported asset')
            return
        else:return
        try:runtime.supervisor.authorize_world(world_id,request.headers.get('x-session-token'))
        except PermissionError:raise HTTPException(403,'session capability required')

    app = FastAPI(title='Vivacity Execution Runtime', version='1.0.0', lifespan=lifespan,
                  dependencies=[Depends(authorize_request)],
                  description='Versioned experiment runtime: MuJoCo robotics and bounded SciPy orbital-inference experiments. Branches retain measured results and numerical failures. Single-process demo.')
    origins = [o.strip() for o in os.getenv('VIVACITY_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Content-Type', 'Idempotency-Key','X-Session-Token','X-Workspace-Token'])
    from .workspace_api import router
    app.include_router(router)
    from .factory_api import router as factory_router
    app.include_router(factory_router)
    from .fulfillment_api import router as fulfillment_router
    app.include_router(fulfillment_router)

    @app.exception_handler(PermissionError)
    async def permission(request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403,content={'detail':'session capability required'})

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={'detail': 'record not found'})

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={'detail': str(exc)})

    @app.exception_handler(Busy)
    async def busy(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={'detail': str(exc)}, headers={'Retry-After': '5'})

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=422, content={'detail': str(exc)})

    @app.exception_handler(Unavailable)
    async def unavailable(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={'detail': str(exc)}, headers={'Retry-After': '5'})

    @app.get('/health')
    def health():
        return {'status': 'ok', 'schema_version': '1.0', 'backends': {k: b.version for k, b in app.state.runtime.backends.items()}, 'limits': {'max_physics_trials': app.state.runtime.max_physics_trials,'physics_trial_workers':app.state.runtime.physics_trial_workers}}

    @app.head('/health', include_in_schema=False)
    def health_head():
        return Response(status_code=200)
    @app.get('/v1/templates', response_model=TemplateCatalog)
    def templates():
        return catalog()
    @app.post('/v1/templates/resolve', response_model=CreateWorld)
    def resolve_template(selection: TemplateSelection):
        return resolve(selection)

    @app.get('/v1/robotics/programs', response_model=RoboticsProgramCatalog)
    def robotics_programs():
        return robotics_catalog()

    @app.get('/v1/robotics/humanoids/models/{robot_id}', response_model=HumanoidModelResponse)
    def humanoid_model(robot_id: str):
        try:
            return humanoid_model_info(robot_id)
        except FileNotFoundError as exc:
            raise HTTPException(503, str(exc)) from exc

    HumanoidToken = Annotated[str, Header(min_length=32, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')]

    @app.post('/v1/robotics/humanoids/experiments', response_model=HumanoidTrialResponse, status_code=202)
    def submit_humanoid(request: HumanoidTrialRequest, x_workspace_token: HumanoidToken):
        try:
            return app.state.humanoids.submit(workspace_owner(x_workspace_token), request)
        except FileNotFoundError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get('/v1/robotics/humanoids/experiments', response_model=list[HumanoidTrialResponse])
    def list_humanoid(robot_id: str, x_workspace_token: HumanoidToken):
        return app.state.humanoids.list(workspace_owner(x_workspace_token), robot_id)

    @app.get('/v1/robotics/humanoids/experiments/{trial_id}', response_model=HumanoidTrialResponse)
    def get_humanoid(trial_id: str, x_workspace_token: HumanoidToken):
        return app.state.humanoids.get(workspace_owner(x_workspace_token), trial_id)

    @app.get('/v1/robotics/humanoids/experiments/{trial_id}/frames', response_model=HumanoidFramesResponse)
    def humanoid_frames(trial_id: str, x_workspace_token: HumanoidToken,
                        cursor: int = Query(default=0, ge=0), limit: int = Query(default=32, ge=1, le=64)):
        return app.state.humanoids.frames(workspace_owner(x_workspace_token), trial_id, cursor, limit)

    @app.post('/v1/robotics/humanoids/experiments/{trial_id}/pause', response_model=HumanoidTrialResponse)
    def pause_humanoid(trial_id: str, x_workspace_token: HumanoidToken):
        return app.state.humanoids.control(workspace_owner(x_workspace_token), trial_id, 'pause')

    @app.post('/v1/robotics/humanoids/experiments/{trial_id}/resume', response_model=HumanoidTrialResponse)
    def resume_humanoid(trial_id: str, x_workspace_token: HumanoidToken):
        return app.state.humanoids.control(workspace_owner(x_workspace_token), trial_id, 'resume')

    @app.post('/v1/robotics/humanoids/experiments/{trial_id}/cancel', response_model=HumanoidTrialResponse)
    def cancel_humanoid(trial_id: str, x_workspace_token: HumanoidToken):
        return app.state.humanoids.control(workspace_owner(x_workspace_token), trial_id, 'cancel')

    @app.get('/v1/robotics/humanoids/experiments/{trial_id}/replay')
    def replay_humanoid(trial_id: str, x_workspace_token: HumanoidToken):
        trial = app.state.humanoids.get(workspace_owner(x_workspace_token), trial_id)
        if trial['status'] != 'completed':
            raise HTTPException(409, 'This trial has no completed physics trace')
        result = trial['result']
        return {'schema_version': 'vivacity.humanoid-replay/1.0', 'trial_id': trial_id,
                'model_hash': result['model_hash'], 'frames': result['frames'],
                'measurements': result['measurements'], 'task_success': result['task_success']}

    @app.get('/v1/robotics/experiments/{experiment_id}/report', response_model=RoboticsExperimentReport)
    def robotics_experiment_report(experiment_id:str, x_session_token:Annotated[str | None,Header()]=None):
        world_id=app.state.runtime.get_experiment(experiment_id)['world_id']
        app.state.runtime.supervisor.authorize_world(world_id,x_session_token)
        return robotics_report(app.state.runtime,experiment_id)

    SessionToken=Annotated[str,Header(min_length=32,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')]

    @app.post('/v1/sessions',response_model=SessionResponse,status_code=201)
    def create_session(request:SessionRequest,x_session_token:SessionToken):
        return app.state.runtime.supervisor.create(request,x_session_token)

    @app.get('/v1/sessions/{session_id}',response_model=SessionResponse)
    def get_session(session_id:str,x_session_token:SessionToken):
        return app.state.runtime.supervisor.get(session_id,x_session_token)

    @app.post('/v1/sessions/{session_id}/stop',response_model=SessionResponse)
    def stop_session(session_id:str,x_session_token:SessionToken):
        return app.state.runtime.supervisor.stop(session_id,x_session_token)

    @app.post('/v1/sessions/{session_id}/pause',response_model=SessionResponse)
    def pause_session(session_id:str,x_session_token:SessionToken):
        return app.state.runtime.supervisor.set_paused(session_id,x_session_token,True)

    @app.post('/v1/sessions/{session_id}/resume',response_model=SessionResponse)
    def resume_session(session_id:str,x_session_token:SessionToken):
        return app.state.runtime.supervisor.set_paused(session_id,x_session_token,False)

    @app.post('/v1/experiments/{experiment_id}/cancel',response_model=ExperimentResponse)
    def cancel_experiment(experiment_id:str):
        return app.state.runtime.cancel(experiment_id)

    @app.get('/v1/experiments/{experiment_id}/trials',response_model=TrialsResponse)
    def physics_trials(experiment_id:str,after:int=Query(-1,ge=-1),limit:int=Query(50,ge=1,le=100)):
        app.state.runtime.get_experiment(experiment_id)
        return app.state.runtime.store.trials(experiment_id,after,limit)

    @app.get('/v1/experiments/{experiment_id}/live',response_model=LiveState|None)
    def live_state(experiment_id:str):
        app.state.runtime.get_experiment(experiment_id)
        return app.state.runtime.live(experiment_id)

    async def authorize_socket(websocket,eid):
        origin=websocket.headers.get('origin')
        if origin and origin not in origins:
            await websocket.close(code=1008);return False
        protocols=[p.strip() for p in websocket.headers.get('sec-websocket-protocol','').split(',')]
        token=next((p[len('vivacity.token.'):] for p in protocols if p.startswith('vivacity.token.')),None)
        try:
            e=app.state.runtime.get_experiment(eid)
            app.state.runtime.supervisor.authorize_world(e['world_id'],token)
        except (KeyError,PermissionError):
            await websocket.close(code=1008);return False
        await websocket.accept(subprotocol='vivacity.live' if 'vivacity.live' in protocols else None)
        return True

    @app.websocket('/v1/experiments/{experiment_id}/live')
    async def live_frames(websocket:WebSocket,experiment_id:str):
        if not await authorize_socket(websocket,experiment_id):return
        sequence=-1
        try:
            while True:
                # Latest-only backpressure: slow clients receive current measured
                # state, never an accumulating queue or a recorded replay.
                frame=app.state.runtime.live(experiment_id)
                if frame and frame['sequence']>sequence:
                    await websocket.send_json(LiveState.model_validate(frame).model_dump());sequence=frame['sequence']
                e=await asyncio.to_thread(app.state.runtime.get_experiment,experiment_id)
                if e['status'] not in ('queued','running'):
                    frame=app.state.runtime.live(experiment_id)
                    if frame and frame['sequence']>sequence:await websocket.send_json(frame)
                    await websocket.close(code=1000);return
                await asyncio.sleep(.05)
        except WebSocketDisconnect:return

    @app.post('/v1/imports',response_model=ImportResponse,status_code=201)
    async def import_world(request:Request,filename:str=Query(min_length=1,max_length=180)):
        chunks=[];length=0
        async for chunk in request.stream():
            length+=len(chunk)
            if length>MAX_UPLOAD:raise ValueError('upload exceeds 16 MiB')
            chunks.append(chunk)
        return await asyncio.to_thread(app.state.imports.create,filename,b''.join(chunks))

    @app.get('/v1/imports/{import_id}',response_model=ImportResponse)
    def imported_world(import_id:str):return app.state.imports.get(import_id)

    @app.get('/v1/imports/{import_id}/preview',response_model=ImportPreview)
    def import_preview(import_id:str):return app.state.imports.get(import_id,preview=True)

    @app.post('/v1/imports/{import_id}/verify',response_model=ImportResponse,status_code=202)
    def verify_import(import_id:str):
        return app.state.imports.verify(import_id,app.state.runtime.executor)

    @app.post('/v1/imports/{import_id}/configure-task',response_model=ImportResponse)
    def configure_import_task(import_id:str):
        return app.state.imports.configure_orbital(import_id, app.state.runtime)

    @app.post('/v1/worlds', response_model=WorldResponse, status_code=201)
    def create_world(request: CreateWorld):
        return app.state.runtime.create_world(request)

    @app.get('/v1/worlds/{world_id}', response_model=WorldResponse)
    def get_world(world_id: str):
        return app.state.runtime.get_world(world_id)

    @app.get('/v1/worlds/{world_id}/state', response_model=StateResponse)
    def state(world_id: str):
        return app.state.runtime.observe(world_id)

    @app.post('/v1/worlds/{world_id}/experiments', response_model=ExperimentResponse, status_code=202)
    def experiment(world_id: str, request: ExperimentRequest, idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9._:-]+$')] = None):
        return app.state.runtime.submit(world_id, request, idempotency_key)

    @app.get('/v1/experiments/{experiment_id}', response_model=ExperimentResponse)
    def get_experiment(experiment_id: str):
        return app.state.runtime.get_experiment(experiment_id)

    @app.get('/v1/experiments/{experiment_id}/branches', response_model=list[BranchResponse])
    def branches(experiment_id: str):
        app.state.runtime.get_experiment(experiment_id)
        return app.state.runtime.store.branches(experiment_id)

    @app.get('/v1/experiments/{experiment_id}/events', response_model=list[EventResponse])
    def recorded_events(experiment_id: str, after: int = Query(0, ge=0)):
        app.state.runtime.get_experiment(experiment_id)
        return app.state.runtime.store.events(experiment_id, after)

    @app.get('/v1/experiments/{experiment_id}/branches/{branch_id}/export', response_model=BranchExport)
    def export_branch(experiment_id: str, branch_id: str):
        from fastapi.responses import JSONResponse
        result=BranchExport.model_validate(app.state.runtime.export_branch(experiment_id,branch_id))
        return JSONResponse(result.model_dump(),headers={'Content-Disposition':f'attachment; filename="vivacity-{result.branch_id}.json"'})

    @app.post('/v1/worlds/{world_id}/commit', response_model=WorldResponse)
    def commit(world_id: str, request: CommitRequest):
        return app.state.runtime.commit(world_id, request.experiment_id, request.branch_id)

    @app.post('/v1/worlds/{world_id}/reset', response_model=WorldResponse)
    def reset(world_id: str):
        return app.state.runtime.reset(world_id)

    @app.patch('/v1/worlds/{world_id}/environment', response_model=WorldResponse)
    def environment(world_id: str, request: EnvironmentPatch):
        return app.state.runtime.environment(world_id, request.config, request.expected_revision)

    @app.get('/v1/worlds/{world_id}/editor', response_model=WorldEditorResponse)
    def world_editor(world_id: str):
        return app.state.runtime.editor(world_id)

    @app.patch('/v1/worlds/{world_id}/editor/properties', response_model=WorldResponse)
    def edit_world_property(world_id: str, request: EditorChange):
        return app.state.runtime.edit_property(world_id, request)

    @app.post('/v1/worlds/{world_id}/editor/geometries', response_model=WorldResponse)
    def edit_world_geometry(world_id: str, request: EditorGeometryAction):
        return app.state.runtime.edit_geometry(world_id, request)

    @app.patch('/v1/worlds/{world_id}/editor/geometry-position', response_model=WorldResponse)
    def move_world_geometry(world_id: str, request: EditorMove):
        return app.state.runtime.move_geometry(world_id, request)

    @app.get('/v1/worlds/{world_id}/versions', response_model=list[WorldVersion])
    def world_versions(world_id: str):
        return app.state.runtime.world_versions(world_id)

    @app.post('/v1/worlds/{world_id}/versions/{revision}/restore', response_model=WorldResponse)
    def restore_world_version(world_id: str, revision: int, request: RestoreWorldVersion):
        return app.state.runtime.restore_world_version(world_id, revision, request.expected_revision)

    @app.get('/v1/experiments/{experiment_id}/replay', response_model=ReplayResponse)
    def replay(experiment_id: str):
        return app.state.runtime.replay(experiment_id)

    @app.websocket('/v1/experiments/{experiment_id}/events')
    async def events(websocket: WebSocket, experiment_id: str, after: int = Query(0, ge=0)):
        if not await authorize_socket(websocket,experiment_id):return
        try:
            while True:
                # Read terminal status first, then drain its atomically persisted event.
                status = await asyncio.to_thread(app.state.runtime.get_experiment, experiment_id)
                batch = await asyncio.to_thread(app.state.runtime.store.events, experiment_id, after)
                for event in batch:
                    await websocket.send_json(EventResponse.model_validate(event).model_dump())
                    after = event['seq']
                    if event['kind'] in ('completed', 'failed', 'cancelled'):
                        await websocket.close(code=1000); return
                if not batch and status['status'] in ('completed', 'failed', 'cancelled'):
                    await websocket.close(code=1000); return
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            return

    from fastapi.openapi.utils import get_openapi

    def openapi():
        if app.openapi_schema is None:
            spec = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
            spec['x-websockets'] = {'/v1/experiments/{experiment_id}/events': {'description': 'Persisted progress; reconnect with after=<seq>; closes on terminal event. Session worlds require capability via vivacity.token.<token> WebSocket subprotocol.', 'message_schema': EventResponse.model_json_schema()},
                                    '/v1/experiments/{experiment_id}/live': {'description':'Latest measured authoritative simulation state, maximum 20 Hz, no replay. Capability subprotocol required for session-owned worlds. Slow clients skip intermediate frames.','message_schema':LiveState.model_json_schema()}}
            app.openapi_schema = spec
        return app.openapi_schema

    app.openapi = openapi
    return app


app = create_app()
