import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from .service import get_service
from .models import PrinterSettings, PrintRequest, StartRequest, ControlRequest, ReviewRequest
from . import plate
import asyncio

router = APIRouter(prefix='/api/printing')

def origin(request):
    from ..main import same_origin
    if not same_origin(request.headers.get('origin'),request.headers.get('host')):
        raise HTTPException(403,'Printing changes must be requested from Jarvis.')

async def action(call):
    try: return await call
    except KeyError: raise HTTPException(404,'Print job not found.') from None
    except ValueError as exc: raise HTTPException(409,str(exc)) from None

@router.get('/status')
async def status():
    s=get_service()
    return {'printer':s.cached, 'settings':s.settings().model_dump(), 'jobs':await s.db('list')}

@router.get('/projects/{project_id}')
async def catalogue(project_id: str, revision_id: str):
    return await action(asyncio.to_thread(plate.catalogue, project_id, revision_id))

@router.post('/inspect')
async def inspect(body: PrintRequest, request: Request):
    origin(request)
    return await action(asyncio.to_thread(plate.inspect, body.model_dump()))

@router.post('/arrange')
async def arrange(body: PrintRequest, request: Request):
    origin(request)
    return await action(asyncio.to_thread(plate.inspect, body.model_dump(), auto_arrange=True))

@router.post('/test')
async def test_connection(request: Request):
    origin(request)
    return await get_service().status()

@router.post('/settings')
async def settings(body: PrinterSettings, request: Request):
    origin(request)
    return await action(get_service().save_settings(body))

@router.post('/jobs',status_code=202)
async def create(body: PrintRequest, request: Request):
    origin(request)
    key=request.headers.get('Idempotency-Key',uuid.uuid4().hex)
    if not 1<=len(key)<=160: raise HTTPException(400,'Invalid request identifier.')
    return await action(get_service().create(body.model_dump(),'http:'+key))

@router.get('/jobs/{job_id}/preview')
async def preview(job_id: str):
    job=await action(get_service().db('get',job_id))
    if not job.get('summary'): raise HTTPException(404,'Preview is not ready.')
    path=get_service().root/job['id']/'output/preview.json'
    if path.is_symlink() or not path.is_file(): raise HTTPException(404,'Preview is not available.')
    return FileResponse(path,media_type='application/json')

@router.get('/jobs/{job_id}')
async def job(job_id: str):
    return await action(get_service().db('get', job_id))

@router.get('/jobs/{job_id}/gcode')
async def gcode(job_id: str):
    job = await action(get_service().db('get', job_id))
    if not job.get('summary'): raise HTTPException(404, 'Slice this plate first.')
    return FileResponse(get_service().root/job['id']/'output/print.gcode', filename='ada-'+job['id']+'.gcode')

@router.post('/jobs/{job_id}/upload')
async def upload(job_id: str, body: ReviewRequest, request: Request):
    origin(request)
    return await action(get_service().upload(job_id, body.fingerprint))

@router.post('/jobs/{job_id}/start')
async def start(job_id: str, body: StartRequest, request: Request):
    origin(request)
    return await action(get_service().start(job_id,body))

@router.post('/control')
async def control(body: ControlRequest, request: Request):
    origin(request)
    return await action(get_service().control(body.action,body.filename))

@router.post('/jobs/{job_id}/resolve')
async def resolve(job_id: str, request: Request):
    origin(request)
    return await action(get_service().resolve(job_id))

@router.post('/jobs/{job_id}/verify')
async def verify(job_id: str, request: Request):
    origin(request)
    return await action(get_service().verify(job_id))
