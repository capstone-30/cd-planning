"""Operator-only P1 commands. Brush arguments come from the installed version's help."""
import argparse
import shutil
import time
from pathlib import Path

import numpy as np

from poc import read_images
from .pipeline import tools_config
from .runner import Runner
from .store import Failure, Store, free_space, load, release, save


def similarity(source, target, max_relative_rmse=.1):
    source, target = np.asarray(source, dtype=float), np.asarray(target, dtype=float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3 or len(source) < 3:
        raise ValueError('최소 3개 공통 카메라 중심이 필요합니다.')
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError('카메라 중심이 유한수가 아닙니다.')
    x, y = source-source.mean(0), target-target.mean(0)
    if any(np.linalg.svd(v, compute_uv=False)[1] < np.linalg.norm(v)*1e-5 for v in (x, y)):
        raise ValueError('카메라 중심이 공선이거나 퇴화했습니다.')
    u, d, vt = np.linalg.svd(y.T @ x / len(x))
    sign = np.eye(3)
    sign[2, 2] = np.linalg.det(u @ vt)
    rotation = u @ sign @ vt
    scale = float(np.sum(d*np.diag(sign)) / np.mean(np.sum(x*x, axis=1)))
    translation = target.mean(0) - scale*rotation@source.mean(0)
    residual = np.linalg.norm(scale*(source@rotation.T)+translation-target, axis=1)
    rmse = float(np.sqrt(np.mean(residual**2)))
    relative = rmse/float(np.sqrt(np.mean(np.sum(y*y, axis=1))))
    if scale <= 0 or relative > max_relative_rmse:
        raise ValueError(f'정렬 잔차가 큽니다: relative RMSE {relative:.4f}')
    return dict(scale=scale, rotation=rotation.tolist(), translation=translation.tolist(),
                rmse=rmse, relative_rmse=relative, max_relative_rmse=max_relative_rmse,
                convention='target = scale * rotation @ source + translation; view coordinates only')


def gaussian_ply(path):
    with Path(path).open('rb') as stream:
        header = []
        for _ in range(256):
            line = stream.readline(1024).decode('ascii').strip()
            header.append(line)
            if line == 'end_header':
                break
        else:
            raise ValueError('PLY 헤더를 확인할 수 없습니다.')
        properties = {line.split()[-1] for line in header if line.startswith('property ')}
        required = {'x', 'y', 'z', 'opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3'}
        if header[0] != 'ply' or not required <= properties or not stream.read(1):
            raise ValueError('Gaussian 속성과 데이터가 있는 PLY가 필요합니다.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parents[1]/'data')
    sub = parser.add_subparsers(dest='command', required=True)
    doctor = sub.add_parser('doctor')
    doctor.add_argument('--output', type=Path, default=Path('gate-tools.json'))
    prepare = sub.add_parser('prepare')
    train = sub.add_parser('train')
    for command in (prepare, train):
        command.add_argument('project')
        command.add_argument('run')
    train.add_argument('--argv', type=Path, required=True, help='JSON array; use {dataset}, {output} placeholders')
    train.add_argument('--settings', type=Path, required=True, help='JSON object: resolution, steps, density')
    compare = sub.add_parser('compare')
    compare.add_argument('project')
    compare.add_argument('initial')
    compare.add_argument('combined')
    compare.add_argument('--screens', type=Path, required=True, help='JSON array of {initial: file, combined: file}')
    compare.add_argument('--judgment', choices=('improved', 'unchanged', 'worse', 'incomparable'), required=True)
    compare.add_argument('--reason', required=True)
    compare.add_argument('--view-mode', choices=('aligned', 'approximate'), required=True)
    args = parser.parse_args()
    store = Store(args.data)
    lock = store.acquire()
    try:
        free_space(store.root)
        if args.command == 'doctor':
            runner = Runner(args.output.resolve().parent/'gate-logs')
            config = tools_config(runner)
            if shutil.which('brush'):
                config['brush_help'] = runner.run(['brush', '--help'], 10)
                if '--version' in config['brush_help']:
                    config['brush_version'] = runner.run(['brush', '--version'], 10)
            else:
                config['brush_help'] = None
            config['real_scene_gate'] = 'not_run'
            save(args.output, config)
            print(args.output)
        elif args.command in ('prepare', 'train'):
            run = store.run(args.project, args.run)
            status = load(run/'status.json')
            if status['state'] != 'completed':
                raise ValueError('완료된 분석이 필요합니다.')
            runner = Runner(run/'logs')
            config = load(run/'run-config.json')
            dataset = run/'colmap/undistorted'
            if args.command == 'prepare':
                if dataset.exists():
                    raise ValueError('이미 준비된 폴더입니다. 불변 결과를 보존하려면 새 run으로 실행하세요.')
                runner.run(['colmap', 'image_undistorter', '--image_path', str(run/'frames'),
                    '--input_path', str(run/config['selected_model']), '--output_path', str(dataset),
                    '--output_type', 'COLMAP', '--max_image_size', str(config['long_edge'])], 600)
            else:
                if status['reconstruction']['state'] == 'ready':
                    raise ValueError('기존 3DGS를 덮어쓸 수 없습니다. 새 run을 사용하세요.')
                if not (dataset/'sparse').is_dir():
                    raise ValueError('먼저 prepare로 왜곡 보정된 입력을 생성하세요.')
                settings = load(args.settings)
                if not isinstance(settings, dict) or not {'resolution', 'steps', 'density'} <= settings.keys():
                    raise ValueError('resolution, steps, density를 실제 Brush 설정으로 기록하세요.')
                help_text = runner.run(['brush', '--help'], 10)
                version = runner.run(['brush', '--version'], 10) if '--version' in help_text else settings.get('version')
                if not version:
                    raise ValueError('Brush가 --version을 지원하지 않으면 settings의 version에 설치 버전을 기록하세요.')
                template = load(args.argv)
                if not isinstance(template, list) or not template or any(not isinstance(x, str) for x in template):
                    raise ValueError('argv는 문자열 배열이어야 합니다.')
                if Path(template[0]).name != 'brush' or not any('{dataset}' in x for x in template) or not any('{output}' in x for x in template):
                    raise ValueError('brush 명령과 {dataset}, {output} 인수가 필요합니다.')
                for arg in template[1:]:
                    if arg.startswith('--') and arg.split('=')[0] not in help_text:
                        raise ValueError(f'설치된 Brush help에 없는 옵션: {arg}')
                output = run/'splats/result.ply'
                output.parent.mkdir(exist_ok=True)
                argv = [x.replace('{dataset}', str(dataset)).replace('{output}', str(output)) for x in template]
                config['brush'] = dict(settings=settings, help=help_text, argv=argv, version=version)
                save(run/'run-config.json', config)
                status['reconstruction'] = dict(state='running', message='Mac에서 Brush 학습 중입니다.')
                save(run/'status.json', status)
                start = time.monotonic()
                try:
                    runner.run(argv, 900)
                    gaussian_ply(output)
                    status['reconstruction'] = dict(state='ready', message='Mac에서 PLY를 열어 확인하세요.',
                        ply='splats/result.ply', elapsed_seconds=time.monotonic()-start, settings=settings)
                except Exception as error:
                    status['reconstruction'] = dict(state='failed', message=str(error))
                    raise
                finally:
                    save(run/'status.json', status)
        else:
            project = store.project(args.project)
            a, b = (store.run(args.project, rid) for rid in (args.initial, args.combined))
            sa, sb = (load(path/'status.json') for path in (a, b))
            if sa['mode'] != 'initial' or sb['mode'] != 'combined' or sa['capture_ids'][0] not in sb['capture_ids']:
                raise ValueError('동일한 최초 A를 사용하는 A / A+B 작업이 필요합니다.')
            ra, rb = sa['reconstruction'], sb['reconstruction']
            if ra['state'] != 'ready' or rb['state'] != 'ready' or ra['settings'] != rb['settings']:
                raise ValueError('동일 설정으로 생성된 두 3DGS가 필요합니다.')
            ac, ai = read_images(a/'colmap/text')
            bc, bi = read_images(b/'colmap/text')
            an = {image['name']: ac[i] for i, image in ai.items()}
            bn = {image['name']: bc[i] for i, image in bi.items()}
            initial_id = sa['capture_ids'][0]
            common = sorted(n for n in an.keys() & bn.keys() if n.startswith(initial_id+'/'))
            try:
                alignment = dict(state='ready', common_images=common,
                                 **similarity([bn[n] for n in common], [an[n] for n in common]))
            except ValueError as error:
                alignment = dict(state='failed', message=str(error))
            if alignment['state'] != 'ready' and (args.view_mode == 'aligned' or args.judgment != 'incomparable'):
                save(project/'comparison'/f'alignment-failed-{int(time.time())}.json', alignment)
                raise ValueError('좌표 정렬 실패입니다. approximate 또는 incomparable로 기록하세요.')
            screens = load(args.screens)
            if not isinstance(screens, list) or (len(screens) < 3 and args.judgment != 'incomparable'):
                raise ValueError('대응 화면 최소 3쌍이 필요합니다. 비교 불가는 화면을 생략할 수 있습니다.')
            for pair in screens:
                if not isinstance(pair, dict) or any(not isinstance(pair.get(role), str) for role in ('initial', 'combined')):
                    raise ValueError('각 화면 쌍에는 initial, combined 파일 경로가 필요합니다.')
                for role in ('initial', 'combined'):
                    source = Path(pair[role])
                    if not source.is_file() or source.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                        raise ValueError('존재하는 PNG 또는 JPEG 화면을 사용하세요.')
            folder = project/'comparison'/f'{args.initial}-{args.combined}'
            folder.mkdir(parents=True, exist_ok=False)
            save(folder/'alignment.json', alignment)
            for index, pair in enumerate(screens):
                for role in ('initial', 'combined'):
                    source = Path(pair[role])
                    if source.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                        raise ValueError('PNG 또는 JPEG 화면을 사용하세요.')
                    shutil.copyfile(source, folder/f'{index+1}-{role}{source.suffix.lower()}')
            result = dict(initial_run=args.initial, combined_run=args.combined, judgment=args.judgment,
                reason=args.reason, view_mode=args.view_mode, alignment=alignment['state'],
                message='운영자 육안 관찰. 정량 품질·인과 효과 평가가 아닙니다.', recorded_at=time.time())
            save(folder/'comparison.json', result)
            (folder/'observations.md').write_text(f"# 3DGS 육안 관찰\n\n판단: {args.judgment}\n\n{args.reason}\n\n시점: {args.view_mode}\n\n{result['message']}\n", encoding='utf-8')
            with store.metadata():
                metadata = load(project/'project.json')
                metadata['comparison'] = result
                save(project/'project.json', metadata)
    except (Failure, ValueError, OSError, KeyError) as error:
        parser.exit(1, f'실험 실패: {error}\n')
    finally:
        release(lock)


if __name__ == '__main__':
    main()
