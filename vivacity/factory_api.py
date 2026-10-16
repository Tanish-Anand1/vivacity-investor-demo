from typing import Literal
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel,ConfigDict,Field
from .factory import FactorySettings
from .workspace_api import Token
from .factory_benchmark import BenchmarkRequest
from .factory_schemas import FactoryCellResponse,FactoryRunResponse,FactorySamplesResponse,FactoryBenchmarkResponse,FactoryDiscoveryResponse

router=APIRouter(prefix='/v1/factory',tags=['Factory production'])

class RunRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode:Literal['conveyor','production']='conveyor'
    creator_label:str|None=Field(None,min_length=1,max_length=80)

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['pause','resume','stop','emergency_stop']

@router.post('/cells',responses={201:{'model':FactoryCellResponse}},status_code=201)
def create_cell(body:FactorySettings,request:Request,x_workspace_token:Token):
    return request.app.state.factory.create(body.model_dump(),x_workspace_token)

@router.get('/cells/{identifier}',responses={200:{'model':FactoryCellResponse}})
def cell(identifier:str,request:Request,x_workspace_token:Token):
    return request.app.state.factory.cell(identifier,x_workspace_token)

@router.get('/cells/{identifier}/observation')
def observation(identifier:str,request:Request,x_workspace_token:Token,source:Literal['initial','latest']='latest'):
    return request.app.state.factory.observation(identifier,x_workspace_token,source)

@router.post('/cells/{identifier}/runs',responses={202:{'model':FactoryRunResponse}},status_code=202)
def start(identifier:str,body:RunRequest,request:Request,x_workspace_token:Token):
    return request.app.state.factory.start(identifier,x_workspace_token,body.mode,body.creator_label)

@router.get('/runs/{identifier}',responses={200:{'model':FactoryRunResponse}})
def run(identifier:str,request:Request,x_workspace_token:Token):
    return request.app.state.factory.get(identifier,x_workspace_token)

@router.get('/runs')
def history(request:Request,x_workspace_token:Token):
    return request.app.state.factory.history(x_workspace_token)

@router.get('/runs/{identifier}/record')
def record(identifier:str,request:Request,x_workspace_token:Token):
    from fastapi.responses import StreamingResponse
    return StreamingResponse(request.app.state.factory.record_json(identifier,x_workspace_token),media_type='application/json')

@router.get('/runs/{identifier}/samples',responses={200:{'model':FactorySamplesResponse}})
def samples(identifier:str,request:Request,x_workspace_token:Token,after:int=Query(-1,ge=-1),limit:int=Query(400,ge=1,le=1000)):
    return request.app.state.factory.samples(identifier,x_workspace_token,after,limit)

@router.get('/runs/{identifier}/discovery',response_model=FactoryDiscoveryResponse)
def discovery(identifier:str,request:Request,x_workspace_token:Token):
    """Latest persisted fits. Physics frames remain the immutable source data."""
    return request.app.state.factory.discovery(identifier,x_workspace_token)

@router.post('/runs/{identifier}/control',responses={200:{'model':FactoryRunResponse}})
def control(identifier:str,body:Command,request:Request,x_workspace_token:Token):
    return request.app.state.factory.command(identifier,x_workspace_token,body.action)

@router.post('/cells/{identifier}/benchmarks',responses={202:{'model':FactoryBenchmarkResponse}},status_code=202)
def start_benchmark(identifier:str,body:BenchmarkRequest,request:Request,x_workspace_token:Token):
    return request.app.state.factory.start_benchmark(identifier,x_workspace_token,body.model_dump())

@router.get('/benchmarks')
def benchmarks(request:Request,x_workspace_token:Token):
    return request.app.state.factory.benchmarks(x_workspace_token)

@router.get('/benchmarks/{identifier}',responses={200:{'model':FactoryBenchmarkResponse}})
def benchmark(identifier:str,request:Request,x_workspace_token:Token):
    return request.app.state.factory.benchmark(identifier,x_workspace_token)

@router.post('/benchmarks/{identifier}/control')
def benchmark_control(identifier:str,body:Command,request:Request,x_workspace_token:Token):
    return request.app.state.factory.command(identifier,x_workspace_token,body.action,kind='factory_benchmark')

from .factory_exchange import Exchange

@router.get('/cells/{identifier}/export',response_model=Exchange)
def export_configuration(identifier:str,request:Request,x_workspace_token:Token):
    return request.app.state.factory.export_configuration(identifier,x_workspace_token)

@router.get('/benchmarks/{identifier}/export',response_model=Exchange)
def export_benchmark(identifier:str,request:Request,x_workspace_token:Token):
    return request.app.state.factory.export_configuration(identifier,x_workspace_token,'benchmark')

@router.get('/runs/{identifier}/export')
def export_record(identifier:str,request:Request,x_workspace_token:Token):
    from fastapi.responses import StreamingResponse
    return StreamingResponse(request.app.state.factory.export_record(identifier,x_workspace_token,raw=True),media_type='application/json')

@router.post('/imports',status_code=201,openapi_extra={'requestBody':{'required':True,'content':{'application/json':{'schema':Exchange.model_json_schema(ref_template='#/components/schemas/{model}')}}}})
async def import_configuration(request:Request,x_workspace_token:Token):
    # Bound bytes before JSON decoding and Pydantic validation (including chunked uploads).
    import asyncio
    chunks=[];length=0
    async for chunk in request.stream():
        length+=len(chunk)
        if length>262144:raise ValueError('Configuration interchange is limited to 256 KiB. Use a configuration or benchmark file, not a raw result archive.')
        chunks.append(chunk)
    from pydantic import ValidationError
    try:body=Exchange.model_validate_json(b''.join(chunks))
    except ValidationError as exc:
        reasons=['.'.join(map(str,e['loc']))+': '+e['msg'] for e in exc.errors(include_input=False)[:5]]
        raise ValueError('Incompatible interchange file. '+'; '.join(reasons)) from None
    return await asyncio.to_thread(request.app.state.factory.import_configuration,body.model_dump(mode='json'),x_workspace_token)

@router.get('/reports/{kind}/{identifier}')
def report(kind:Literal['run','benchmark'],identifier:str,request:Request,x_workspace_token:Token,format:Literal['pdf','zip']='pdf',project_id:str|None=None):
    from fastapi.responses import Response,FileResponse
    from starlette.background import BackgroundTask
    result=request.app.state.factory.report(identifier,x_workspace_token,kind,archive=format=='zip',project_id=project_id)
    filename='vivacity-'+identifier+'.'+format
    if format=='zip':return FileResponse(result,media_type='application/zip',filename=filename,background=BackgroundTask(result.unlink,missing_ok=True))
    return Response(result,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="'+filename+'"'})

from .factory_projects import FactoryProjects,ProjectRequest,VersionRequest,AttachmentRequest

@router.get('/projects')
def projects(request:Request,x_workspace_token:Token):
    return FactoryProjects(request.app.state.factory).list(x_workspace_token)

@router.post('/projects',status_code=201)
def create_project(body:ProjectRequest,request:Request,x_workspace_token:Token):
    return FactoryProjects(request.app.state.factory).create(body.model_dump(),x_workspace_token)

@router.get('/projects/{identifier}')
def project(identifier:str,request:Request,x_workspace_token:Token):
    return FactoryProjects(request.app.state.factory).get(identifier,x_workspace_token)

@router.post('/projects/{identifier}/versions',status_code=201)
def project_version(identifier:str,body:VersionRequest,request:Request,x_workspace_token:Token):
    return FactoryProjects(request.app.state.factory).version(identifier,body.model_dump(),x_workspace_token)

@router.post('/projects/{identifier}/attachments',status_code=201)
def project_attach(identifier:str,body:AttachmentRequest,request:Request,x_workspace_token:Token):
    return FactoryProjects(request.app.state.factory).attach(identifier,body.model_dump(),x_workspace_token)
