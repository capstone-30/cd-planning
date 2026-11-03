import asyncio
import hmac
import os
import shutil
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.formparsers import MultiPartException

from .pipeline import DEFAULTS, execute, probe
from .runner import Runner
from .store import Failure, Store, free_space, ident, load, release, save

MAX_VIDEO_BYTES = 250 * 1024**2


class RunInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['initial', 'combined']
    capture_ids: list[str]


class BodyTooLarge(MultiPartException):
    pass


class Guard:
    """Authenticate and bound the entire body before Starlette spools multipart files."""
    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        authorization = headers.get(b'authorization', b'')
        if not hmac.compare_digest(authorization, ('Bearer '+self.token).encode()):
            return await JSONResponse({'error': {'code': 'UNAUTHORIZED', 'message': '개발 토큰을 확인하세요.'}}, 401)(scope, receive, send)
        total = 0
        exceeded = False
        replaced = False
        async def bounded():
            nonlocal total, exceeded
            message = await receive()
            total += len(message.get('body', b''))
            if total > MAX_VIDEO_BYTES + 1024**2:
                exceeded = True
                raise BodyTooLarge('영상 크기 제한 초과')
            return message
        async def bounded_send(message):
            nonlocal replaced
            if exceeded:
                if not replaced:
                    replaced = True
                    await JSONResponse({'error': {'code': 'FILE_TOO_LARGE', 'message': '영상은 250MB 이하여야 합니다.'}}, 413)(scope, receive, send)
                return
            await send(message)
        try:
            await self.app(scope, bounded, bounded_send)
        except BodyTooLarge:
            await JSONResponse({'error': {'code': 'FILE_TOO_LARGE', 'message': '영상은 250MB 이하여야 합니다.'}}, 413)(scope, receive, send)


def create_app(root=None, token=None, config=None, processor=execute):
    token = token or os.environ.get('POC_TOKEN', '')
    if len(token) < 16 or not token.isascii():
        raise RuntimeError('POC_TOKEN에 16자 이상의 ASCII 개발 토큰을 설정하세요.')
    store = Store(root or os.environ.get('POC_DATA', Path(__file__).resolve().parents[1]/'data'))
    settings = {**DEFAULTS, **(config or {})}
    worker = None
    server_lock = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal server_lock
        # Prevent a second API process from recovering a live process's jobs.
        import fcntl
        server_lock = (store.root/'.server.lock').open('a')
        try:
            fcntl.flock(server_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            resource_lock = store.acquire()
            try:
                store.recover()
            finally:
                release(resource_lock)
            yield
        finally:
            if worker is not None:
                await asyncio.to_thread(worker.join)
            server_lock.close()

    app = FastAPI(title='촬영 안내 PoC', version='0.1.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.add_middleware(Guard, token=token)

    @app.exception_handler(Failure)
    async def failure_handler(request, error):
        status = {'NOT_FOUND': 404, 'BUSY': 409, 'NOT_READY': 409, 'INVALID_INPUT': 422,
                  'FILE_TOO_LARGE': 413, 'DISK_SPACE': 507, 'TOOL_UNAVAILABLE': 503}.get(error.code, 422)
        return JSONResponse({'error': {'code': error.code, 'message': error.message, 'log': error.log}}, status)

    @app.exception_handler(BodyTooLarge)
    async def body_handler(request, error):
        return JSONResponse({'error': {'code': 'FILE_TOO_LARGE', 'message': '영상은 250MB 이하여야 합니다.'}}, 413)

    @app.get('/health')
    def health():
        try:
            lock = store.acquire()
        except Failure:
            busy = True
        else:
            release(lock)
            busy = False
        return dict(version='0.1.0', busy=busy, tools={name: bool(shutil.which(name))
                    for name in ('ffmpeg', 'ffprobe', 'colmap', 'brush')}, settings=settings)

    @app.post('/projects', status_code=201)
    def project_create():
        free_space(store.root)
        with store.metadata():
            return {'project_id': store.create_project()}

    @app.post('/projects/{project_id}/captures', status_code=201)
    def capture_upload(project_id: str, file: UploadFile = File(...), role: Literal['initial', 'supplement'] = Form(...)):
        project = store.project(project_id)
        free_space(store.root)
        cid = str(uuid4())
        folder = project/'captures'
        folder.mkdir(exist_ok=True)
        temporary = folder/f'.{cid}.upload'
        total = 0
        try:
            with temporary.open('xb') as output:
                while chunk := file.file.read(1024**2):
                    total += len(chunk)
                    if total > MAX_VIDEO_BYTES:
                        raise Failure('FILE_TOO_LARGE', '영상은 250MB 이하여야 합니다.')
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            metadata = probe(temporary, Runner(project/'capture-validation'/cid), role)
            temporary.replace(folder/f'{cid}.mov')
            capture = dict(capture_id=cid, role=role, bytes=total, created_at=time.time(), **metadata)
            with store.metadata():
                value = load(project/'project.json')
                value['captures'].append(capture)
                save(project/'project.json', value)
            return capture
        finally:
            temporary.unlink(missing_ok=True)
            file.file.close()

    @app.post('/projects/{project_id}/runs', status_code=202)
    def run_create(project_id: str, payload: RunInput):
        nonlocal worker
        project = store.project(project_id)
        free_space(store.root)
        with store.metadata():
            value = load(project/'project.json')
            requested = payload.capture_ids
            lookup = {c['capture_id']: c for c in value['captures']}
            if len(set(requested)) != len(requested) or any(cid not in lookup for cid in requested):
                raise Failure('INVALID_INPUT', '중복되거나 다른 프로젝트의 촬영 ID입니다.')
            captures = sorted((lookup[cid] for cid in requested), key=lambda c: c['role'])
            expected = ['initial'] if payload.mode == 'initial' else ['initial', 'supplement']
            if [c['role'] for c in captures] != expected:
                raise Failure('INVALID_INPUT', '최초 A 또는 같은 프로젝트의 A+B를 선택하세요.')
            lock = store.acquire()
            try:
                run_id = str(uuid4())
                run = project/'runs'/run_id
                status = dict(run_id=run_id, mode=payload.mode, capture_ids=requested, state='queued',
                    stage=None, created_at=time.time(), started_at=None, finished_at=None, error=None,
                    reconstruction=dict(state='not_started', message='Mac에서 Brush 수동 실행이 필요합니다.'))
                save(run/'status.json', status)
                configuration = dict(settings, capture_ids=requested, camera_model='SIMPLE_RADIAL',
                                     brush={'state': 'unverified', 'target_steps': 3000})
                save(run/'run-config.json', configuration)
                value['runs'].append(run_id)
                save(project/'project.json', value)
                def work():
                    try:
                        processor(run, project, captures, configuration)
                    finally:
                        release(lock)
                worker = threading.Thread(target=work, name='poc-worker', daemon=False)
                worker.start()
            except BaseException:
                release(lock)
                raise
        return {'run_id': run_id}

    @app.get('/projects/{project_id}/runs/{run_id}')
    def run_status(project_id: str, run_id: str):
        result = load(store.run(project_id, run_id)/'status.json')
        result['elapsed_seconds'] = max(0, (result['finished_at'] or time.time()) - (result['started_at'] or result['created_at']))
        result['comparison'] = load(store.project(project_id)/'project.json').get('comparison')
        return result

    @app.get('/projects/{project_id}/runs/{run_id}/report')
    def report(project_id: str, run_id: str):
        run = store.run(project_id, run_id)
        if load(run/'status.json')['state'] != 'completed':
            raise Failure('NOT_READY', '분석이 아직 완료되지 않았습니다.')
        return load(run/'analysis/report.json')

    @app.get('/projects/{project_id}/runs/{run_id}/media/{asset_id}')
    def media(project_id: str, run_id: str, asset_id: str):
        run = store.run(project_id, run_id)
        if load(run/'status.json')['state'] != 'completed':
            raise Failure('NOT_READY', '분석이 아직 완료되지 않았습니다.')
        assets = load(run/'analysis/assets.json')
        filename = assets.get(ident(asset_id))
        if not filename or Path(filename).name != filename or not filename.endswith('.png'):
            raise Failure('NOT_FOUND', '안내 이미지를 찾을 수 없습니다.')
        return FileResponse(run/'analysis'/filename, media_type='image/png', headers={'Cache-Control': 'no-store'})

    return app
