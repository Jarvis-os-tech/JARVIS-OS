"""Project APIs: local UI mutations and bounded uploads."""
import asyncio
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .projects import IMAGE_EXTENSIONS, MAX_FILE, WorkspaceError, store
from .project_tools import run_action
from .image_generation import generation_status, start_initial_demo

router = APIRouter()


def origin(request):
    if urlparse(request.headers.get('origin', '')).netloc != request.headers.get('host'):
        raise HTTPException(403, 'Changes must be requested from Ada.')


async def work(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except WorkspaceError as e:
        raise HTTPException(422, str(e)) from None
    except (OSError, ValueError):
        raise HTTPException(500, 'Could not read or save the project. Check local storage.') from None


class Action(BaseModel):
    model_config = {'extra': 'forbid'}
    name: str = Field(max_length=50)
    arguments: dict


@router.get('/api/workspace')
async def workspace():
    snapshot = await work(store.snapshot)
    snapshot['image_generation'] = generation_status(snapshot['active_id'], snapshot['project'])
    from .cad import status
    snapshot['cad'] = await work(status, snapshot['active_id'])
    return snapshot


@router.get('/api/projects/{project_id}/cad')
async def cad_revision(project_id: str, revision_id: str = ''):
    from .cad import revision
    return await work(revision, project_id, revision_id)


@router.post('/api/workspace/action')
async def action(body: Action, request: Request):
    origin(request)
    if body.name == 'inspect_image':
        raise HTTPException(422, 'Open the image preview in the workspace.')
    result = await work(run_action, body.name, body.arguments)
    return {'result': result}


@router.post('/api/projects/{project_id}/upload')
async def upload(project_id: str, path: str, request: Request):
    origin(request)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_FILE:
            raise HTTPException(413, 'Files must be no larger than 20 MB.')
    result = await work(store.upload, project_id, path, bytes(data))
    status = await work(start_initial_demo, store, project_id)
    return {**result, **({'image_generation': status} if status else {})}


@router.get('/api/projects/{project_id}/file')
async def file(project_id: str, path: str, download: bool = False):
    target = await work(store.path, project_id, path)
    if not target.is_file():
        raise HTTPException(404, 'File not found.')
    image = target.suffix.lower() in IMAGE_EXTENSIONS and not download
    return FileResponse(target, media_type=None if image else 'application/octet-stream',
                        filename=target.name, content_disposition_type='inline' if image else 'attachment')
