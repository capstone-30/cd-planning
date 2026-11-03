import fcntl
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4


class Failure(Exception):
    def __init__(self, code, message, log=None):
        super().__init__(message)
        self.code, self.message, self.log = code, message, log


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def ident(value):
    try:
        if str(UUID(str(value))) != str(value):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise Failure('NOT_FOUND', '항목을 찾을 수 없습니다.') from None
    return str(value)


def free_space(root):
    if shutil.disk_usage(root).free < 10 * 1024**3:
        raise Failure('DISK_SPACE', '여유 공간 10GB가 필요합니다. 이전 실험을 직접 정리하세요.')


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def project(self, project_id):
        path = self.root / ident(project_id)
        if not (path / 'project.json').is_file():
            raise Failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.')
        return path

    def run(self, project_id, run_id):
        path = self.project(project_id) / 'runs' / ident(run_id)
        if not (path / 'status.json').is_file():
            raise Failure('NOT_FOUND', '작업을 찾을 수 없습니다.')
        return path

    def create_project(self):
        project_id = str(uuid4())
        save(self.root / project_id / 'project.json', dict(project_id=project_id,
             created_at=time.time(), captures=[], runs=[], comparison=None))
        return project_id

    def recover(self):
        for path in self.root.glob('*/runs/*/status.json'):
            status = load(path)
            changed = False
            if status['state'] in ('queued', 'running'):
                status.update(state='failed', finished_at=time.time(), error=dict(
                    code='SERVER_RESTARTED', message='서버가 재시작되었습니다. 새 작업으로 재시도하세요.', log=None))
                changed = True
            if status.get('reconstruction', {}).get('state') == 'running':
                status['reconstruction'].update(state='failed', message='서버/운영자 작업이 중단되었습니다.')
                changed = True
            if changed:
                save(path, status)

    def acquire(self):
        stream = (self.root / '.worker.lock').open('a')
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            stream.close()
            raise Failure('BUSY', '다른 분석 또는 복원이 실행 중입니다.') from None
        return stream

    @contextmanager
    def metadata(self):
        with (self.root/'.metadata.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def release(stream):
    fcntl.flock(stream, fcntl.LOCK_UN)
    stream.close()
