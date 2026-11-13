"""Rebuild poc/data/core-check from the public Mip-NeRF 360 `room` images.

Reproduces the 2026-11-10 core check (CORE_POC_RESULT.md) whose original scripts were not committed:
first 60 sorted images -> 30 s clip A, next 40 -> 20 s clip B (0.5 s per image, 960x640 H.264),
real API upload/analysis through FastAPI TestClient, COLMAP undistortion of both runs, and the
A+B -> A camera similarity that evaluate_guidance.py reads from summary.json.
Stills stitched into clips are not a smartphone capture or a guided recapture.
"""
import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from poc import read_images, read_model
from server.app import create_app
from server.experiment import similarity
from server.runner import Runner
from server.store import save

HERE = Path(__file__).resolve().parent


def make_clip(images, output, runner):
    staging = output.with_suffix('')
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for i, image in enumerate(images):
        shutil.copyfile(image, staging/f'{i:03d}.jpg')
    runner.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-framerate', '2', '-i', str(staging/'%03d.jpg'),
                '-vf', 'scale=960:640,format=yuv420p', '-r', '30', '-c:v', 'libx264', '-crf', '18',
                '-movflags', '+faststart', str(output)], 300)
    shutil.rmtree(staging)
    return dict(path=output.name, frames=len(images), seconds=len(images)*.5,
                sources=[Path(p).name for p in images])


def wait(client, headers, project_id, run_id, log):
    while True:
        status = client.get(f'/projects/{project_id}/runs/{run_id}', headers=headers).json()
        if status['state'] in ('completed', 'failed'):
            log.append(dict(call=f'GET /projects/{{project}}/runs/{run_id}', state=status['state'],
                            stage=status.get('stage'), error=status.get('error')))
            return status
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, required=True, help='folder holding the downloaded room/images_4 files')
    parser.add_argument('--manifest', type=Path, required=True, help='source-manifest.json with revision and SHA256')
    parser.add_argument('--core', type=Path, default=HERE/'data/core-check')
    args = parser.parse_args()
    core = args.core.resolve()
    if (core/'api-evidence.json').exists():
        parser.error(f'{core} already holds a core check; choose a new --core')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    if not all(f.get('match') for f in manifest['files']) or len(manifest['files']) != 100:
        parser.error('manifest must list 100 files whose SHA256 matched the published LFS hash')
    images = [args.images/Path(f['path']).name for f in manifest['files']]
    core.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.manifest, core/'source-manifest.json')

    runner = Runner(core/'clip-logs')
    clips = core/'clips'
    clips.mkdir(exist_ok=True)
    clip_a = make_clip(images[:60], clips/'A.mp4', runner)
    clip_b = make_clip(images[60:], clips/'B.mp4', runner)
    save(core/'clips.json', dict(A=clip_a, B=clip_b, note='0.5 s per still; not a continuous phone capture'))

    token = secrets.token_hex(24)
    headers = {'Authorization': f'Bearer {token}'}
    log = []
    evidence = dict(platform=sys.platform, python=sys.version.split()[0])
    with TestClient(create_app(core/'api-data', token=token)) as client:
        log.append(dict(call='GET /health', **client.get('/health', headers=headers).json()))
        project_id = client.post('/projects', headers=headers).json()['project_id']
        evidence['project_id'] = project_id
        captures = {}
        for role, clip in (('initial', clips/'A.mp4'), ('supplement', clips/'B.mp4')):
            with clip.open('rb') as stream:
                response = client.post(f'/projects/{project_id}/captures', headers=headers,
                                       data={'role': role}, files={'file': (clip.name, stream, 'video/mp4')})
            response.raise_for_status()
            captures[role] = response.json()
            log.append(dict(call='POST /captures', role=role, status=response.status_code, capture=captures[role]))
        evidence['runs'] = {}
        for mode, ids in (('initial', [captures['initial']['capture_id']]),
                          ('combined', [captures['initial']['capture_id'], captures['supplement']['capture_id']])):
            response = client.post(f'/projects/{project_id}/runs', headers=headers, json=dict(mode=mode, capture_ids=ids))
            response.raise_for_status()
            run_id = response.json()['run_id']
            print('run', mode, run_id, flush=True)
            status = wait(client, headers, project_id, run_id, log)
            if status['state'] != 'completed':
                save(core/'api-evidence.json', dict(evidence, calls=log))
                raise SystemExit(f'{mode} run failed: {status["error"]}')
            report = client.get(f'/projects/{project_id}/runs/{run_id}/report', headers=headers).json()
            assets = [r['representative_asset_id'] for r in report['regions'] if r.get('representative_asset_id')]
            for asset in assets:
                media = client.get(f'/projects/{project_id}/runs/{run_id}/media/{asset}', headers=headers)
                log.append(dict(call='GET /media', run=mode, status=media.status_code, bytes=len(media.content)))
            evidence['runs'][mode] = dict(run_id=run_id, capture=captures['initial' if mode == 'initial' else 'supplement'],
                                          status=status, report_message=report['message'],
                                          recommended=sum(bool(r.get('recommended')) for r in report['regions']))
    evidence['calls'] = log
    save(core/'api-evidence.json', evidence)

    runs = core/'api-data'/project_id/'runs'
    summary = dict(platform=sys.platform, project_id=project_id, runs={})
    for mode in ('initial', 'combined'):
        run_id = evidence['runs'][mode]['run_id']
        subprocess.run([sys.executable, '-m', 'server.experiment', '--data', str(core/'api-data'),
                        'prepare', project_id, run_id], cwd=HERE, check=True)
        run = runs/run_id
        cameras, points = read_model(run/'colmap/text')
        config = json.loads((run/'run-config.json').read_text(encoding='utf-8'))
        status = evidence['runs'][mode]['status']
        summary['runs'][mode] = dict(run_id=run_id, input_frames=config['input_frames'], registered=len(cameras),
                                     points=len(points), timings=status['timings'],
                                     elapsed_seconds=status['elapsed_seconds'],
                                     recommended=evidence['runs'][mode]['recommended'],
                                     tool_versions={k: v.splitlines()[0] for k, v in config['versions'].items()})
    a, b = (runs/evidence['runs'][m]['run_id']/'colmap/text' for m in ('initial', 'combined'))
    ac, ai = read_images(a)
    bc, bi = read_images(b)
    an = {image['name']: ac[i] for i, image in ai.items()}
    bn = {image['name']: bc[i] for i, image in bi.items()}
    prefix = evidence['runs']['initial']['capture']['capture_id'] + '/'
    common = sorted(n for n in an.keys() & bn.keys() if n.startswith(prefix))
    try:
        summary['alignment'] = dict(state='ready', common_images=common,
                                    **similarity([bn[n] for n in common], [an[n] for n in common]))
    except ValueError as error:
        summary['alignment'] = dict(state='failed', message=str(error), common_images=common)
    save(core/'summary.json', summary)
    print(json.dumps({m: {k: v for k, v in r.items() if k != 'tool_versions'} for m, r in summary['runs'].items()}, indent=1))
    print('alignment', summary['alignment']['state'], summary['alignment'].get('relative_rmse'))


if __name__ == '__main__':
    main()
