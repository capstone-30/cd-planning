"""Bounded subprocesses; the JSONL resource trace includes system pressure, not only RSS."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .store import Failure, save


def sample(pid):
    def output(args):
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
        except (OSError, subprocess.SubprocessError):
            return None
    rss = output(['/bin/ps', '-o', 'rss=', '-p', str(pid)])
    result = dict(time=time.time(), process_rss_kb=rss)
    if sys.platform == 'darwin':
        result['pressure'] = output(['/usr/sbin/sysctl', '-n', 'kern.memorystatus_vm_pressure_level'])
        result['swap'] = output(['/usr/sbin/sysctl', '-n', 'vm.swapusage'])
    return result


class Runner:
    def __init__(self, logs):
        self.logs = Path(logs)
        self.logs.mkdir(parents=True, exist_ok=True)
        self.counter = len(list(self.logs.glob('*.command.json')))

    def run(self, args, timeout, deadline=None, cwd=None, include_stderr=False):
        self.counter += 1
        stem = self.logs / f'{self.counter:03d}-{Path(args[0]).name}'
        start = time.monotonic()
        limit = min(start + timeout, deadline) if deadline else start + timeout
        record = dict(argv=list(map(str, args)), started_at=time.time())
        save(stem.with_suffix('.command.json'), record)
        process = None
        pressure_since = None
        try:
            with stem.with_suffix('.stdout').open('wb') as out, stem.with_suffix('.stderr').open('wb') as err, stem.with_suffix('.resources.jsonl').open('w') as metrics:
                process = subprocess.Popen(list(map(str, args)), stdout=out, stderr=err, start_new_session=True, cwd=cwd)
                while process.poll() is None:
                    now = time.monotonic()
                    if now >= limit:
                        raise Failure('TIMEOUT', '처리 시간 제한을 초과했습니다. 작은 설정으로 새 작업을 실행하세요.', str(stem.name))
                    resource = sample(process.pid)
                    metrics.write(json.dumps(resource) + '\n')
                    metrics.flush()
                    if resource.get('pressure') in ('2', '4'):
                        pressure_since = pressure_since or now
                        if now - pressure_since >= 30:
                            raise Failure('MEMORY_PRESSURE', '메모리 압박이 30초 지속되어 중단했습니다.', str(stem.name))
                    else:
                        pressure_since = None
                    try:
                        process.wait(timeout=min(2, max(.01, limit-time.monotonic())))
                    except subprocess.TimeoutExpired:
                        pass
                record['returncode'] = process.returncode
                if process.returncode:
                    raise Failure('COMMAND_FAILED', '외부 처리 명령이 실패했습니다. Mac 로그를 확인하세요.', str(stem.name))
        except OSError as error:
            raise Failure('TOOL_UNAVAILABLE', '필요한 실행 도구를 찾거나 시작할 수 없습니다.', str(stem.name)) from error
        finally:
            if process and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            record.update(elapsed_seconds=round(time.monotonic()-start, 3), finished_at=time.time())
            save(stem.with_suffix('.command.json'), record)
        output = stem.with_suffix('.stdout').read_text(errors='replace')
        if include_stderr:
            output += '\n' + stem.with_suffix('.stderr').read_text(errors='replace')
        return output
