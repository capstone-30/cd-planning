"""Paired A / A+10 Brush pilot on saved real photographs, not physical recapture."""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np

from server.runner import Runner
from server.experiment import gaussian_ply
from server.store import save


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_slots(training, evaluation):
    if (len(set(training)) != len(training) or len(set(evaluation)) != len(evaluation)
            or set(training) & set(evaluation) or not evaluation
            or len(training) % len(evaluation)):
        raise ValueError('Unique, disjoint images and an exact evaluation period are required.')
    period = len(training) // len(evaluation) + 1
    train = iter(training)
    slots = []
    for ev in evaluation:
        slots.append(ev)
        slots.extend(next(train) for _ in range(period-1))
    return period, slots


def metrics(reference, render):
    if reference.shape != render.shape or reference.ndim != 3 or reference.shape[2] != 3 or min(reference.shape[:2]) < 11:
        raise ValueError('Matching RGB images of at least 11x11 pixels are required.')
    x, y = reference.astype(np.float64)/255, render.astype(np.float64)/255
    mse = float(np.mean((x-y)**2))
    blur = lambda z: cv2.GaussianBlur(z, (11, 11), 1.5)[5:-5, 5:-5]
    mx, my = blur(x), blur(y)
    vx, vy, cov = blur(x*x)-mx*mx, blur(y*y)-my*my, blur(x*y)-mx*my
    ssim = ((2*mx*my+.01**2)*(2*cov+.03**2) /
            ((mx*mx+my*my+.01**2)*(vx+vy+.03**2)))
    return dict(psnr_db=-10*math.log10(mse) if mse else math.inf, ssim=float(ssim.mean()), mse=mse)


def prepare(source, output):
    mapping = json.loads((source/'image-map.json').read_text())
    if len({r['source'] for r in mapping}) != len(mapping):
        raise ValueError('Duplicate source photographs.')
    # The saved dataset contains 60 A training images, 10 B training images, 10 B holdouts.
    initial_capture = next(r['source'].split('/')[0] for r in mapping if not r['evaluation'])
    initial = [r['name'] for r in mapping if not r['evaluation'] and r['source'].startswith(initial_capture+'/')]
    extra = [r['name'] for r in mapping if not r['evaluation'] and r['name'] not in initial]
    evaluation = [r['name'] for r in mapping if r['evaluation']]
    if (len(initial), len(extra), len(evaluation)) != (60, 10, 10):
        raise ValueError('Expected the saved 60 A / 10 B / 10 holdout dataset.')
    for row in mapping:
        if digest(source/'images'/row['name']) != row['sha256']:
            raise ValueError(f"Image hash mismatch: {row['name']}")
    sparse = source/'sparse/0'
    lines = (sparse/'images.txt').read_text().splitlines()
    poses = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) != 10 or lines[i].strip():
            raise ValueError('Expected poses with empty observation tracks in the saved dataset.')
        poses[fields[9]] = fields
        i += 1
    if set(poses) != {r['name'] for r in mapping}:
        raise ValueError('Pose/image mismatch.')
    manifest = dict(source=str(source), source_map_sha256=digest(source/'image-map.json'),
                    seed_cloud_sha256=digest(sparse/'points3D.txt'),
                    seed_points=sum(bool(x.strip()) and not x.startswith('#') for x in (sparse/'points3D.txt').read_text().splitlines()),
                    arms={})
    for arm, training in [('initial', initial), ('supplemented', initial+extra)]:
        folder = output/'datasets'/arm
        (folder/'images').mkdir(parents=True)
        (folder/'sparse/0').mkdir(parents=True)
        period, slots = split_slots(training, evaluation)
        rows, image_lines = [], []
        originals = {r['name']: r for r in mapping}
        for index, old in enumerate(slots):
            new = f'slot_{index:03}.jpg'
            shutil.copyfile(source/'images'/old, folder/'images'/new)
            fields = poses[old].copy()
            fields[0], fields[9] = str(index+1), new
            image_lines.extend([' '.join(fields), ''])
            rows.append(dict(originals[old], name=new, original_name=old,
                             pose=fields[1:9], evaluation=index % period == 0))
        (folder/'sparse/0/images.txt').write_text('\n'.join(image_lines)+'\n')
        for name in ('cameras.txt', 'points3D.txt'):
            shutil.copyfile(sparse/name, folder/'sparse/0'/name)
        save(folder/'image-map.json', rows)
        manifest['arms'][arm] = dict(training=len(training), evaluation=len(evaluation),
            eval_period=period, images=rows,
            files={name: digest(folder/'sparse/0'/name) for name in ('cameras.txt', 'images.txt', 'points3D.txt')})
    a, b = [manifest['arms'][arm]['images'] for arm in ('initial', 'supplemented')]
    by_source = {r['source']: r for r in b}
    for row in a:
        other = by_source[row['source']]
        if any(row[key] != other[key] for key in ('sha256', 'pose', 'evaluation')):
            raise ValueError('Paired input images, poses or holdouts differ.')
    save(output/'manifest.json', manifest)
    return manifest


def contact_sheet(output, results, seed):
    a, b = [next(r for r in results if r['seed'] == seed and r['arm'] == arm)
            for arm in ('initial', 'supplemented')]
    canvas = np.full((10*210, 3*280, 3), 245, dtype=np.uint8)
    refs = {r['source']: r['name'] for r in json.loads((output/'datasets/initial/image-map.json').read_text())}
    for index, (av, bv) in enumerate(zip(a['views'], b['views'])):
        paths = [output/'datasets/initial/images'/refs[av['source']], output/av['render'], output/bv['render']]
        labels = [f"Reference B/{Path(av['source']).name}",
                  f"A  {av['psnr_db']:.2f} dB", f"A+10  {bv['psnr_db']:.2f} dB"]
        for col, (path, label) in enumerate(zip(paths, labels)):
            img = cv2.imread(str(path))
            height = round(img.shape[0]*270/img.shape[1])
            tile = cv2.resize(img, (270, height))
            y, x = index*210+25, col*280+5
            canvas[y:y+height, x:x+270] = tile
            cv2.putText(canvas, label, (x, y-8), cv2.FONT_HERSHEY_SIMPLEX, .42, (25, 25, 25), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(output/f'comparison-seed{seed}.jpg'), canvas):
        raise OSError('Could not save comparison image.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/guidance-eval/datasets/uniform'))
    parser.add_argument('--brush', type=Path, default=Path('data/core-check/tools/brush-app-aarch64-apple-darwin/brush_app'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = prepare(args.source.resolve(), output)
    protocol = dict(scope='Single-scene saved-photo ablation; not a physical recapture or guidance trial',
        comparison='60 A training images versus the same A + 10 uniformly selected B images',
        evaluation='Same 10 B holdout photographs; RGB PSNR and SSIM Gaussian11 sigma1.5 crop5',
        caveats=['All-100-image SfM cameras/intrinsics are shared: geometry oracle, not end-to-end.',
                 f"Same {manifest['seed_points']} saved A-only seed points in the shared full-data coordinate frame.",
                 'B holdouts are near the added B views; this tests local added-view coverage.',
                 'One room and two optimization seeds cannot establish generalization or guidance utility.'],
        steps=3000, resolution=960, max_splats=300000, seeds=[42, 7],
        brush_sha256=digest(args.brush), manifest_sha256=digest(output/'manifest.json'))
    save(output/'protocol.json', protocol)
    results = []
    for seed in protocol['seeds']:
        for arm in ('initial', 'supplemented'):
            run = output/'runs'/f'{arm}_seed{seed}'
            runner = Runner(run/'logs')
            print(f'Training {arm}, seed {seed}', flush=True)
            runner.run([str(args.brush.resolve()), str(output/'datasets'/arm),
                '--total-steps', '3000', '--max-resolution', '960', '--max-splats', '300000',
                '--seed', str(seed), '--export-every', '3000', '--export-path', str(run),
                '--export-name', 'result.ply', '--eval-split-every', str(manifest['arms'][arm]['eval_period']),
                '--eval-every', '3000', '--eval-save-to-disk'], 900)
            gaussian_ply(run/'result.ply')
            rows = [r for r in manifest['arms'][arm]['images'] if r['evaluation']]
            expected = {Path(r['name']).stem+'.png' for r in rows}
            if {p.name for p in (run/'eval_3000').glob('*.png')} != expected:
                raise ValueError('Brush evaluation split differs from the recorded split.')
            views = []
            for row in rows:
                ref = output/'datasets'/arm/'images'/row['name']
                rendered = run/'eval_3000'/(Path(row['name']).stem+'.png')
                views.append(dict(source=row['source'], reference_sha256=digest(ref),
                    render=str(rendered.relative_to(output)), render_sha256=digest(rendered),
                    **metrics(cv2.imread(str(ref)), cv2.imread(str(rendered)))))
            result = dict(arm=arm, seed=seed, views=views,
                          mean_psnr_db=float(np.mean([v['psnr_db'] for v in views])),
                          mean_ssim=float(np.mean([v['ssim'] for v in views])))
            save(run/'result.json', result)
            results.append(result)
            save(output/'results.json', results)
            print(f"{arm} seed {seed}: {result['mean_psnr_db']:.3f} dB / SSIM {result['mean_ssim']:.4f}", flush=True)
    pairs = []
    for seed in protocol['seeds']:
        a, b = [next(r for r in results if r['seed'] == seed and r['arm'] == arm)
                for arm in ('initial', 'supplemented')]
        for av, bv in zip(a['views'], b['views']):
            if (av['source'], av['reference_sha256']) != (bv['source'], bv['reference_sha256']):
                raise ValueError('Holdout pairing mismatch.')
        pairs.append(dict(seed=seed, delta_psnr_db=b['mean_psnr_db']-a['mean_psnr_db'],
            delta_ssim=b['mean_ssim']-a['mean_ssim'],
            improved_views=sum(bv['psnr_db'] > av['psnr_db'] for av, bv in zip(a['views'], b['views']))))
    save(output/'comparison.json', dict(pairs=pairs, results=results,
        protocol_sha256=digest(output/'protocol.json'), manifest_sha256=digest(output/'manifest.json')))
    for seed in protocol['seeds']:
        contact_sheet(output, results, seed)


if __name__ == '__main__':
    main()
