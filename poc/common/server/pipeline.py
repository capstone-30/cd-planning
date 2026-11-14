import json
import math
import shutil
import sys
import time
import traceback
from pathlib import Path

import cv2
import numpy as np

from poc import read_images, read_model, read_points
from .runner import Runner
from .store import Failure, load, save


DEFAULTS = dict(fps=2, initial_frames=60, supplement_frames=40, long_edge=960,
                blur_threshold=0.0, matcher='sequential', preprocess_seconds=120,
                sfm_seconds=600, analyze_seconds=60)
# shortcut: blur threshold is disabled until calibrated on a real G0 clip; retain all measured sharpness values.


def probe(path, runner, role, deadline=None):
    try:
        value = json.loads(runner.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_streams', '-show_format', '-of', 'json', str(path)], 20, deadline))
        stream = value['streams'][0]
        duration = float(stream.get('duration', value['format'].get('duration', 0)))
        width, height = int(stream['width']), int(stream['height'])
        minimum, maximum = (30, 60) if role == 'initial' else (10, 30)
        if not math.isfinite(duration) or not minimum <= duration <= maximum+.5:
            raise Failure('VIDEO_DURATION', f'{minimum}~{maximum}초의 영상을 업로드하세요.')
        if min(width, height) <= 0 or max(width, height) > 8192 or not stream.get('codec_name'):
            raise ValueError('dimensions or codec')
        if (stream.get('color_transfer') in ('smpte2084', 'arib-std-b67') or
                stream.get('color_primaries') == 'bt2020' or
                any('dovi' in json.dumps(side).lower() or 'dolby' in json.dumps(side).lower()
                    for side in stream.get('side_data_list', []))):
            raise Failure('HDR_UNSUPPORTED', 'HDR 영상은 지원하지 않습니다. SDR로 다시 촬영하세요.')
        return dict(duration=duration, width=width, height=height, codec=stream['codec_name'],
                    color_transfer=stream.get('color_transfer'), side_data=stream.get('side_data_list', []))
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise Failure('INVALID_VIDEO', '정상적인 영상 파일을 읽을 수 없습니다.') from error


def tools_config(runner):
    versions = {}
    for tool, args in [('ffmpeg', ['-version']), ('ffprobe', ['-version']), ('colmap', ['-h'])]:
        if not shutil.which(tool):
            raise Failure('TOOL_UNAVAILABLE', f'{tool} 설치와 PATH를 확인하세요.')
        versions[tool] = runner.run([tool, *args], 10)
    helps = {command: runner.run(['colmap', command, '-h'], 10, include_stderr=True) for command in (
        'feature_extractor', 'sequential_matcher', 'exhaustive_matcher', 'mapper', 'model_converter', 'image_undistorter')}
    def option(command, candidates):
        for name in candidates:
            if f'--{name}' in helps[command]:
                return '--'+name
        raise Failure('COLMAP_OPTIONS', '설치된 COLMAP의 CPU 옵션을 확인할 수 없습니다. 로그의 help를 확인하세요.')
    return dict(versions=versions, cli_help=helps, cpu_extraction=option('feature_extractor',
        ['FeatureExtraction.use_gpu', 'SiftExtraction.use_gpu']),
        cpu_matching={name: option(name, ['FeatureMatching.use_gpu', 'SiftMatching.use_gpu'])
                      for name in ('sequential_matcher', 'exhaustive_matcher')})


def check_model(model, frame_records, mode):
    cameras, images = read_images(model)
    points = list(read_points(model, cameras).values())
    if len(cameras) < 30 or len(cameras)/len(frame_records) < .6 or len(points) < 100:
        raise Failure('REGISTRATION_INSUFFICIENT', '단일 모델의 정합이 부족합니다. 천천히 겹치는 시점으로 다시 촬영하세요.')
    if mode == 'combined':
        registered = {image['name'] for image in images.values()}
        initial = [f['name'] for f in frame_records if f['role'] == 'initial']
        supplement = [f['name'] for f in frame_records if f['role'] == 'supplement']
        if sum(n in registered for n in initial) < .6*len(initial) or sum(n in registered for n in supplement) < 10:
            raise Failure('SUPPLEMENT_DISCONNECTED', '보완 영상이 최초 영상과 같은 모델에 충분히 연결되지 않았습니다.')
    return len(cameras)


def preprocess(run, project, captures, config, runner, deadline):
    frames = []
    for capture in captures:
        cid, role = capture['capture_id'], capture['role']
        path = Path(project)/'captures'/f'{cid}.mov'
        probe(path, runner, role, deadline)
        candidates = run/'candidates'/cid
        candidates.mkdir(parents=True)
        edge = config['long_edge']
        filters = f"fps={config['fps']},scale=w='if(gte(iw,ih),min(iw,{edge}),-2)':h='if(gte(iw,ih),-2,min(ih,{edge}))'"
        runner.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-an', '-vf', filters,
                    '-frames:v', str(math.ceil(capture['duration']*config['fps'])+1),
                    '-q:v', '2', str(candidates/'%06d.jpg')], config['preprocess_seconds'], deadline)
        measured = []
        for index, filename in enumerate(sorted(candidates.glob('*.jpg'))):
            if time.monotonic() >= deadline:
                raise Failure('TIMEOUT', '프레임 전처리 시간 제한을 초과했습니다.')
            image = cv2.imread(str(filename), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise Failure('DECODE_FAILED', '프레임 디코딩에 실패했습니다.')
            sharpness = float(cv2.Laplacian(image, cv2.CV_64F).var())
            measured.append(dict(name=f'{cid}/{filename.name}', capture_id=cid, role=role,
                time_seconds=(index+.5)/config['fps'], sharpness=sharpness,
                width=image.shape[1], height=image.shape[0], selected=False))
        eligible = [f for f in measured if f['sharpness'] >= config['blur_threshold']]
        if len(eligible) < 30:
            raise Failure('FRAMES_INSUFFICIENT', '유효 프레임이 30장 미만입니다. 천천히 겹치는 시점으로 다시 촬영하세요.')
        maximum = config['initial_frames'] if role == 'initial' else config['supplement_frames']
        chosen = {int(i) for i in np.linspace(0, len(eligible)-1, min(len(eligible), maximum))}
        for index in chosen:
            frame = eligible[index]
            frame['selected'] = True
            target = run/'frames'/frame['name']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidates/Path(frame['name']).name, target)
            frames.append(frame)
        save(run/f'capture-{cid}-frames.json', measured)
    save(run/'frames.json', frames)
    return frames


def reconstruct(run, frames, config, runner, deadline, mode):
    colmap = run/'colmap'
    sparse = colmap/'sparse'
    sparse.mkdir(parents=True)
    database = str(colmap/'database.db')
    runner.run(['colmap', 'feature_extractor', '--database_path', database, '--image_path', str(run/'frames'),
        '--ImageReader.single_camera_per_folder', '1', '--ImageReader.camera_model', 'SIMPLE_RADIAL',
        config['cpu_extraction'], '0'], config['sfm_seconds'], deadline)
    matcher = 'exhaustive_matcher' if config['matcher'] == 'exhaustive' else 'sequential_matcher'
    runner.run(['colmap', matcher, '--database_path', database, config['cpu_matching'][matcher], '0'],
               config['sfm_seconds'], deadline)
    if mode == 'combined' and matcher != 'exhaustive_matcher':
        # At most 120 frames: exhaustive cross-capture matching also closes A/B loop links.
        runner.run(['colmap', 'exhaustive_matcher', '--database_path', database,
            config['cpu_matching']['exhaustive_matcher'], '0'], config['sfm_seconds'], deadline)
    runner.run(['colmap', 'mapper', '--database_path', database, '--image_path', str(run/'frames'),
                '--output_path', str(sparse)], config['sfm_seconds'], deadline)
    models = []
    for model in sorted(sparse.iterdir()):
        if not model.is_dir():
            continue
        text = colmap/f'text-{model.name}'
        text.mkdir()
        runner.run(['colmap', 'model_converter', '--input_path', str(model), '--output_path', str(text),
                    '--output_type', 'TXT'], config['sfm_seconds'], deadline)
        cameras, _ = read_model(text)
        models.append((len(cameras), model, text))
    if not models:
        raise Failure('REGISTRATION_INSUFFICIENT', '복원된 단일 SfM 모델이 없습니다.')
    _, model, text = max(models, key=lambda item: item[0])
    check_model(text, frames, mode)
    shutil.copytree(text, colmap/'text')
    config['selected_model'] = str(model.relative_to(run))
    config['input_frames'] = len(frames)
    save(run/'run-config.json', config)


def execute(run, project, captures, config):
    run = Path(run)
    status = load(run/'status.json')
    runner = Runner(run/'logs')
    start = time.monotonic()
    timings = {}
    def stage(name):
        status.update(state='running', stage=name)
        save(run/'status.json', status)
        return time.monotonic()
    try:
        status['started_at'] = time.time()
        tick = stage('preprocess')
        config.update(tools_config(runner))
        save(run/'run-config.json', config)
        deadline = tick + config['preprocess_seconds']
        frames = preprocess(run, project, captures, config, runner, deadline)
        timings['preprocess'] = time.monotonic()-tick
        tick = stage('sfm')
        deadline = tick + config['sfm_seconds']
        reconstruct(run, frames, config, runner, deadline, status['mode'])
        timings['sfm'] = time.monotonic()-tick
        tick = stage('analyze')
        runner.run([sys.executable, '-m', 'server.analyze', str(run), str(len(frames)),
                    status['run_id']], config['analyze_seconds'], cwd=Path(__file__).resolve().parents[1])
        timings['analyze'] = time.monotonic()-tick
        status.update(state='completed', finished_at=time.time())
    except Exception as error:
        if not isinstance(error, Failure):
            (run/'logs/error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            error = Failure('PROCESSING_FAILED', '처리에 실패했습니다. Mac의 error.txt를 확인하세요.', 'error.txt')
        status.update(state='failed', finished_at=time.time(), error=dict(code=error.code,
            message=error.message, log=f'logs/{error.log}' if error.log else None))
    finally:
        status['timings'] = timings
        status['elapsed_seconds'] = time.monotonic()-start
        save(run/'status.json', status)
