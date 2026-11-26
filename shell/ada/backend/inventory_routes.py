"""Inventory HTTP endpoints and the shared voice/UI action dispatcher."""
import asyncio
import io
import json
import sqlite3
import tempfile
from pathlib import Path
import zipfile
from contextlib import closing

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import Field, ValidationError
from starlette.background import BackgroundTask

from .inventory import Input, get_inventory, uid
from . import inventory_camera as camera
from . import inventory_camera_live as camera_live
from .inventory_parts import report, project_change
from .inventory_vision import start_scan, refine_scan
from .project_routes import origin
from .projects import WorkspaceError, store, now

router=APIRouter()
OPERATIONS={'add_stock','adjust_stock','edit_part','edit_lot','undo','match_requirement','reserve',
            'edit_scan','confirm_scan','discard_scan'}


class Change(Input):
    operation: str
    data: dict
    request_id: str = Field(min_length=1,max_length=200)


class Scan(Input):
    mode: str = Field(default='add',pattern='^(add|recount)$')
    location: str = Field(default='',max_length=160)
    request_id: str = Field(min_length=1,max_length=200)


class Refinement(Input):
    row_id: str
    expected_revision: int
    capture_new: bool = False
    request_id: str = Field(min_length=1,max_length=200)


async def work(fn,*args,**kwargs):
    try:
        return await asyncio.to_thread(fn,*args,**kwargs)
    except (WorkspaceError,ValidationError) as error:
        message=str(error) if isinstance(error,WorkspaceError) else 'Check the inventory fields and try again.'
        raise HTTPException(422,message) from None
    except (OSError,sqlite3.Error):
        raise HTTPException(503,'Inventory storage is unavailable. Check disk space and try again.') from None


def change(operation,data,request_id):
    if operation not in OPERATIONS or not isinstance(data,dict) or len(json.dumps(data))>100000:
        raise WorkspaceError('Choose a valid inventory change.')
    if operation in {'match_requirement','reserve'}:
        return project_change(operation,data,request_id)
    if operation=='adjust_stock' and data.get('project_id'):
        store.project(data['project_id'])
    return get_inventory().mutate(operation,data,request_id)


def show_inventory(scan_id=''):
    if scan_id:get_inventory().scan(scan_id)
    with store.lock:
        store.view={'id':uid(),'project_id':store.active(),'view':'inventory','scan_id':scan_id}
    return {'view':'inventory','scan_id':scan_id}


def voice_action(name,args):
    if name=='get_inventory':
        snapshot=get_inventory().snapshot(args.get('query',''))
        return {'revision':snapshot['revision'],'items':snapshot['items'][:60],
                'total_matches':len(snapshot['items']),
                'recent_scans':[{'id':s['id'],'status':s['status'],'message':s['message']} for s in snapshot['scans'][:5]]}
    if name=='get_inventory_scan':return get_inventory().scan(args['scan_id'])
    if name=='show_inventory':return show_inventory(args.get('scan_id',''))
    if name=='scan_inventory':
        scan=start_scan(**args);show_inventory(scan['id']);return scan
    if name=='refine_inventory_scan':
        scan=refine_scan(**args);show_inventory(scan['id']);return scan
    if name=='get_project_stock':
        result=report(args['project_id'])
        result.pop('display_content',None)
        return result
    if name=='inventory_change':
        try:data=json.loads(args['data_json'])
        except (ValueError,TypeError):raise WorkspaceError('Supply a JSON object containing the inventory change.') from None
        result=change(args['operation'],data,args.get('request_id') or uid())
        return result
    raise WorkspaceError('Unknown inventory action.')


@router.get('/api/inventory')
async def inventory(query:str=''):
    if len(query)>500:raise HTTPException(422,'Search text is too long.')
    return await work(get_inventory().snapshot,query)


@router.post('/api/inventory/action')
async def action(body:Change,request:Request):
    origin(request)
    return await work(change,body.operation,body.data,body.request_id)


@router.post('/api/inventory/scans')
async def scan(body:Scan,request:Request):
    origin(request)
    return await work(start_scan,**body.model_dump())


@router.get('/api/inventory/scans/{scan_id}')
async def get_scan(scan_id:str):
    return await work(get_inventory().scan,scan_id)


@router.post('/api/inventory/scans/{scan_id}/refine')
async def refine(scan_id:str,body:Refinement,request:Request):
    origin(request)
    return await work(refine_scan,scan_id,**body.model_dump())


@router.get('/api/inventory/photos/{name}')
async def photo(name:str):
    path=await work(get_inventory().photo_path,name)
    return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'private, max-age=3600'})


@router.get('/api/inventory/camera')
async def camera_status():
    return await work(camera.status)


@router.post('/api/inventory/camera')
async def camera_settings(body:camera.CameraSettings,request:Request):
    origin(request)
    return await work(camera.save_settings,body.model_dump())


@router.post('/api/inventory/camera/preview')
async def camera_preview(request:Request):
    origin(request)
    data,source=await work(camera.capture)
    return Response(data,media_type='image/jpeg',headers={'X-Ada-Camera':source['source'],
                    'X-Ada-Camera-Fallback':str(source['fallback']).lower(),'Cache-Control':'no-store'})


@router.get('/api/inventory/camera/live')
async def camera_live_preview(request:Request, device:str='', rotation:int=0):
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Open the live preview from Ada.')
    try:
        config = camera.CameraSettings(usb_device=device, rotation=rotation)
    except ValidationError:
        raise HTTPException(422, 'Choose a valid camera and rotation.') from None
    stream = camera_live.frames(config.usb_device, config.rotation)
    try:
        first = await anext(stream)
    except (WorkspaceError, StopAsyncIteration) as error:
        await stream.aclose()
        raise HTTPException(503, str(error) or 'Camera preview stopped for a scan.') from None
    except BaseException:
        await stream.aclose()
        raise
    async def body():
        try:
            yield camera_live.multipart(first)
            async for frame in stream:
                yield camera_live.multipart(frame)
        finally:
            await stream.aclose()
    return StreamingResponse(body(), media_type='multipart/x-mixed-replace; boundary=frame',
                             headers={'Cache-Control':'no-store', 'X-Accel-Buffering':'no'},
                             background=BackgroundTask(stream.aclose))


@router.get('/api/inventory/projects/{project_id}')
async def project_stock(project_id:str):
    return await work(report,project_id)


@router.get('/api/inventory/projects/{project_id}/export')
async def export_parts(project_id:str):
    current=await work(report,project_id)
    content=f"<!-- Live stock export: {now()} -->\n\n"+current['display_content']
    return Response(content,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="Parts list - current stock.md"'})


def backup():
    inventory=get_inventory();output=io.BytesIO()
    with inventory.lock,tempfile.TemporaryDirectory(prefix='ada-inventory-backup-') as directory:
        target=Path(directory)/'inventory.sqlite3'
        source=inventory.connect()
        try:
            with closing(sqlite3.connect(target)) as destination:source.backup(destination)
        finally:source.close()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(target,'inventory.sqlite3')
            for path in inventory.photos.glob('*.jpg'):
                if not path.is_symlink():archive.write(path,'photos/'+path.name)
            settings=inventory.root/'camera.json'
            if settings.is_file() and not settings.is_symlink():archive.write(settings,'camera.json')
    return output.getvalue()


@router.get('/api/inventory/backup')
async def download_backup():
    return Response(await work(backup),media_type='application/zip',
                    headers={'Content-Disposition':'attachment; filename="ada-inventory-backup.zip"'})
