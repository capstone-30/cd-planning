"""Paired, fixed-pose offline pilot; never evidence of physical guided recapture."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil

import cv2
import numpy as np

from poc import read_images, read_model
from guidance import PARAMETERS, posed_candidates, select_views
from server.runner import Runner
from server.store import Failure, save


def direction_scores(centers, directions, weights, camera_centers):
    vectors = np.asarray(camera_centers)[:, None, :] - np.asarray(centers)[None, :, :]
    norms = np.linalg.norm(vectors, axis=2, keepdims=True)
    if np.any(norms < 1e-9):
        raise ValueError('Candidate coincides with a region center')
    cosines = np.sum(vectors / norms * np.asarray(directions)[None, :, :], axis=2)
    return cosines @ (np.asarray(weights) / np.sum(weights)), cosines


def layout(initial, extra, evaluation, period=8):
    training = list(initial) + list(extra)
    if len(set(training + list(evaluation))) != len(training) + len(evaluation):
        raise ValueError('Training/evaluation images overlap or repeat')
    if len(training) + len(evaluation) != period * len(evaluation):
        raise ValueError('Fixed eval-period layout does not fit')
    train_iter, eval_iter = iter(training), iter(evaluation)
    return [(next(eval_iter) if i % period == 0 else next(train_iter), i % period == 0)
            for i in range(len(training) + len(evaluation))]


def ssim(a, b):
    a, b = a.astype(np.float64), b.astype(np.float64)
    mu_a = cv2.GaussianBlur(a, (11, 11), 1.5)
    mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)
    va = cv2.GaussianBlur(a*a, (11, 11), 1.5) - mu_a*mu_a
    vb = cv2.GaussianBlur(b*b, (11, 11), 1.5) - mu_b*mu_b
    cov = cv2.GaussianBlur(a*b, (11, 11), 1.5) - mu_a*mu_b
    value = ((2*mu_a*mu_b + (0.01*255)**2) * (2*cov + (0.03*255)**2) /
             ((mu_a*mu_a + mu_b*mu_b + (0.01*255)**2) * (va + vb + (0.03*255)**2)))
    return float(value[5:-5, 5:-5].mean())


def prepare(root, core, policy='legacy', seeds=(42, 7)):
    if (root/'protocol.json').exists():
        raise ValueError('Protocol already frozen; use a new output directory to change it')
    evidence = json.loads((core/'api-evidence.json').read_text(encoding='utf-8'))
    project = core/'api-data'/evidence['project_id']/'runs'
    initial_run = project/evidence['runs']['initial']['run_id']
    combined_run = project/evidence['runs']['combined']['run_id']
    reference = root/'reference'
    reference.mkdir(parents=True, exist_ok=True)
    runner = Runner(root/'prepare-logs')
    if not (reference/'images.txt').exists():
        runner.run(['colmap', 'model_converter', '--input_path', str(combined_run/'colmap/undistorted/sparse'),
                    '--output_path', str(reference), '--output_type', 'TXT'], 60)
    cameras, images = read_images(reference)
    image_by_name = {v['name']: v for v in images.values()}
    camera_by_name = {v['name']: cameras[k] for k, v in images.items()}
    a_id = evidence['runs']['initial']['capture']['capture_id']
    b_id = evidence['runs']['combined']['capture']['capture_id']
    initial = sorted(n for n in image_by_name if n.startswith(a_id+'/'))
    extra_pool = sorted(n for n in image_by_name if n.startswith(b_id+'/'))
    evaluation = [n for n in extra_pool if int(Path(n).stem) % 4 == 0]
    candidates = [n for n in extra_pool if n not in evaluation]
    assert (len(initial), len(evaluation), len(candidates)) == (60, 10, 30)
    report = json.loads((initial_run/'analysis/report.json').read_text(encoding='utf-8'))
    regions = [r for r in report['regions'] if r['recommended']]
    assert len(regions) == 3
    alignment = json.loads((core/'summary.json').read_text(encoding='utf-8'))['alignment']
    assert alignment['state'] == 'ready'
    rotation, translation, scale = np.array(alignment['rotation']), np.array(alignment['translation']), alignment['scale']
    centers = [(np.array(r['center'])-translation) @ rotation / scale for r in regions]
    if all(r.get('direction_vector') is not None for r in regions):
        directions = [np.array(r['direction_vector']) @ rotation for r in regions]
        scores, cosines = direction_scores(centers, directions, [r['heuristic_risk'] for r in regions],
                                          [camera_by_name[n] for n in candidates])
    else:
        if policy == 'legacy':
            raise ValueError('Legacy comparison requires an archived v1 direction report')
        scores, cosines = np.zeros(len(candidates)), np.empty((len(candidates), 0))
    guided = sorted(sorted(candidates, key=lambda n: (-scores[candidates.index(n)], n))[:10])
    uniform = [candidates[i] for i in np.linspace(0, len(candidates)-1, 10, dtype=int)]
    if policy == 'coverage_v2':
        initial_cameras, initial_points = read_model(initial_run/'colmap/text')
        initial_cameras = {i:(np.array(c)-translation)@rotation/scale for i,c in initial_cameras.items()}
        initial_points = [((np.array(x)-translation)@rotation/scale, error, ids) for x,error,ids in initial_points]
        selection = select_views(initial_cameras, initial_points, posed_candidates(reference, candidates), 10)
        save(root/'selection.json', selection)
        if selection['status'] != 'ready':
            raise ValueError(f'v2 cannot supply equal +10 budget: {len(selection["selected"])} candidates; no fallback used')
        guide_arm = 'coverage_gain_v2'
        selections = {guide_arm: sorted(v['id'] for v in selection['selected']), 'uniform': uniform}
    else:
        guide_arm = 'nearest_direction_proxy'
        selections = {guide_arm: guided, 'uniform': uniform}
        selections.update({f'random_{seed}': sorted(random.Random(seed).sample(candidates, 10)) for seed in (0, 1, 2)})
    # All arms get the identical initial-only point cloud, never points from candidates/evaluation.
    point_lines = []
    for line in (initial_run/'colmap/text/points3D.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        v = line.split()
        xyz = (np.array(list(map(float, v[1:4])))-translation) @ rotation / scale
        # Brush only consumes XYZ/RGB here; tracks intentionally omitted from this seed cloud.
        point_lines.append(' '.join([v[0], *(format(x, '.17g') for x in xyz), *v[4:8]]))
    seed_cloud = '\n'.join(point_lines)+'\n'
    metadata = {}
    lines = iter((reference/'images.txt').read_text(encoding='utf-8').splitlines())
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        v = line.split(maxsplit=9)
        metadata[v[9]] = v[1:9]
        next(lines)
    eval_hashes = {}
    for arm, extra in selections.items():
        assert len(extra) == 10 and set(extra) <= set(candidates)
        dataset = root/'datasets'/arm
        sparse = dataset/'sparse/0'
        sparse.mkdir(parents=True)
        (dataset/'images').mkdir()
        shutil.copyfile(reference/'cameras.txt', sparse/'cameras.txt')
        (sparse/'points3D.txt').write_text(seed_cloud, encoding='utf-8')
        image_lines, mapping = [], []
        for i, (source_name, is_eval) in enumerate(layout(initial, extra, evaluation)):
            name = f'slot_{i:03d}.jpg'
            source = combined_run/'colmap/undistorted/images'/source_name
            os.link(source, dataset/'images'/name)
            image_lines += [' '.join([str(i+1), *metadata[source_name], name]), '']
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if is_eval:
                assert name not in eval_hashes or eval_hashes[name] == digest
                eval_hashes[name] = digest
            mapping.append(dict(name=name, source=source_name, evaluation=is_eval, sha256=digest))
        (sparse/'images.txt').write_text('\n'.join(image_lines)+'\n', encoding='utf-8')
        save(dataset/'image-map.json', mapping)
    runs = ([(arm, seed) for seed in seeds for arm in selections] if policy == 'coverage_v2' else
            [(arm, 42) for arm in selections] + [(guide_arm, 7), ('uniform', 7)])
    protocol = dict(scope='offline fixed-pose single-scene pilot, not physical recapture',
        hypothesis=f'{guide_arm} versus uniform at equal +10 frames', guide_arm=guide_arm,
        selector_parameters=PARAMETERS.copy() if policy == 'coverage_v2' else None,
        original_rule_feasible_candidates=int(np.sum(np.any(cosines > 0, axis=1))) if cosines.shape[1] else None,
        candidate_direction_cosines=cosines.tolist(), candidate_scores=dict(zip(candidates, map(float, scores))),
        initial_frames=initial, evaluation_frames=evaluation, candidate_frames=candidates,
        additional_frames=10, selections=selections, initial_seed_points=len(point_lines),
        seed_cloud_sha256=hashlib.sha256(seed_cloud.encode()).hexdigest(),
        eval_image_sha256=eval_hashes, pose_source=str(reference),
        caveats=['all-100-image SfM poses/intrinsics fixed for every arm; geometry oracle',
                 'only A points seed the models; candidate/eval points excluded',
                 ('candidate whitelist is historical captured poses, not validated routes; sparse visibility only'
                  if policy == 'coverage_v2' else 'all candidate directions are opposite recommendations; proxy is not following original guidance'),
                 'one room, one initial split; training seeds are not independent scenes',
                 'photometric metrics do not assess reachability or camera-motion burden'],
        settings=dict(steps=3000, max_resolution=960, max_splats=300000, eval_period=8),
        primary_metric='mean per-view RGB PSNR dB on the same 10 held-out images',
        secondary_metric='mean RGB SSIM, Gaussian 11x11 sigma1.5, crop5',
        runs=[dict(arm=a, seed=s) for a,s in runs])
    assert len(eval_hashes) == 10
    save(root/'protocol.json', protocol)
    print('Frozen protocol:', len(runs), 'runs;', protocol['original_rule_feasible_candidates'], 'original-direction candidates', flush=True)


def run(root, brush):
    protocol = json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    protocol_hash = hashlib.sha256((root/'protocol.json').read_bytes()).hexdigest()
    os.environ['RUST_LOG'] = 'info'
    results = []
    for item in protocol['runs']:
        arm, seed = item['arm'], item['seed']
        output = root/'runs'/f'{arm}_seed{seed}'
        if (output/'result.json').exists():
            result = json.loads((output/'result.json').read_text(encoding='utf-8'))
            assert result['protocol_sha256'] == protocol_hash
            results.append(result)
            continue
        output.mkdir(parents=True, exist_ok=True)
        dataset = root/'datasets'/arm
        for entry in json.loads((dataset/'image-map.json').read_text(encoding='utf-8')):
            if entry['evaluation']:
                assert hashlib.sha256((dataset/'images'/entry['name']).read_bytes()).hexdigest() == protocol['eval_image_sha256'][entry['name']]
        runner = Runner(output/'logs')
        argv = [str(brush), str(dataset), '--total-steps', '3000', '--max-resolution', '960',
                '--max-splats', '300000', '--seed', str(seed), '--export-every', '3000',
                '--export-path', str(output), '--export-name', 'result.ply',
                '--eval-split-every', '8', '--eval-every', '3000', '--eval-save-to-disk']
        print('Training', arm, 'seed', seed, flush=True)
        try:
            text = runner.run(argv, 900)
        except Failure as error:
            save(output/f'failure-{runner.counter:03d}.json', dict(code=error.code, message=error.message, log=error.log))
            raise
        assert '70 training, 10 eval views' in text, 'Unexpected dataset split; inspect log'
        assert f'Starting from colmap points {protocol["initial_seed_points"]}' in text, 'Initial-only seed cloud not loaded'
        views = []
        for name in protocol['eval_image_sha256']:
            render = cv2.imread(str(output/'eval_3000'/Path(name).with_suffix('.png')))
            target = cv2.imread(str(dataset/'images'/name))
            assert render is not None and render.shape == target.shape
            mse = float(np.mean((render.astype(float)-target.astype(float))**2))
            assert mse > 0 and math.isfinite(mse)
            views.append(dict(view=name, psnr_db=10*math.log10(255**2/mse), ssim=ssim(render, target)))
        command = max((json.loads(p.read_text(encoding='utf-8')) for p in (output/'logs').glob('*.command.json')),
                      key=lambda record: record['started_at'])
        assert command['returncode'] == 0
        result = dict(arm=arm, seed=seed, protocol_sha256=protocol_hash, views=views,
            mean_psnr_db=float(np.mean([v['psnr_db'] for v in views])),
            mean_ssim=float(np.mean([v['ssim'] for v in views])), seconds=command['elapsed_seconds'])
        save(output/'result.json', result)
        results.append(result)
        save(root/'results.json', results)
        print('Finished', arm, seed, 'PSNR', round(result['mean_psnr_db'],4), 'SSIM', round(result['mean_ssim'],4), flush=True)
    save(root/'results.json', results)


def summarize(root):
    protocol = json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    results = json.loads((root/'results.json').read_text(encoding='utf-8'))
    lookup = {(r['arm'], r['seed']): r for r in results}
    assert set(lookup) == {(r['arm'], r['seed']) for r in protocol['runs']}
    assert {r['protocol_sha256'] for r in results} == {hashlib.sha256((root/'protocol.json').read_bytes()).hexdigest()}
    paired = []
    guide_arm = protocol.get('guide_arm', 'nearest_direction_proxy')
    for seed in sorted({r['seed'] for r in protocol['runs'] if r['arm'] == guide_arm}, key=[r['seed'] for r in protocol['runs']].index):
        guide, uniform = lookup[guide_arm, seed], lookup['uniform', seed]
        deltas = []
        for a, b in zip(guide['views'], uniform['views']):
            assert a['view'] == b['view']
            deltas.append(dict(view=a['view'], psnr_delta_db=a['psnr_db']-b['psnr_db'],
                               ssim_delta=a['ssim']-b['ssim']))
        paired.append(dict(seed=seed, psnr_delta_db=guide['mean_psnr_db']-uniform['mean_psnr_db'],
            ssim_delta=guide['mean_ssim']-uniform['mean_ssim'],
            guide_psnr_higher_views=sum(d['psnr_delta_db'] > 0 for d in deltas), views=deltas))
    groups = {}
    for label, arms in [(guide_arm, [guide_arm]), ('uniform', ['uniform']),
                        ('random', ['random_0', 'random_1', 'random_2'])]:
        group = [r for r in results if r['arm'] in arms]
        if not group:
            continue
        groups[label] = dict(runs=len(group), mean_psnr_db=float(np.mean([r['mean_psnr_db'] for r in group])),
            min_psnr_db=min(r['mean_psnr_db'] for r in group), max_psnr_db=max(r['mean_psnr_db'] for r in group),
            mean_ssim=float(np.mean([r['mean_ssim'] for r in group])))
    save(root/'comparison.json', dict(original_rule_feasible_candidates=protocol['original_rule_feasible_candidates'],
        guide_arm=guide_arm, paired_guide_minus_uniform=paired, groups=groups,
        warning='single-scene offline experiment; no physical recapture or cross-scene superiority established'))
    print(json.dumps(dict(paired=paired, groups=groups), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'prepare-v2', 'run', 'summarize'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent/'data/guidance-eval')
    parser.add_argument('--core', type=Path, default=Path(__file__).resolve().parent/'data/core-check')
    parser.add_argument('--seeds', type=lambda s: tuple(int(x) for x in s.split(',')), default=(42, 7),
                        help='prepare-v2 training seeds, comma separated; default 42,7 as in the original protocol')
    parser.add_argument('--brush', type=Path, help='Brush executable; default is the archived macOS app under --core')
    args = parser.parse_args()
    root, core = args.root.resolve(), args.core.resolve()
    if args.action == 'prepare':
        prepare(root, core)
    elif args.action == 'prepare-v2':
        prepare(root, core, 'coverage_v2', args.seeds)
    elif args.action == 'run':
        run(root, args.brush or core/'tools/brush-app-aarch64-apple-darwin/brush_app')
    else:
        summarize(root)
