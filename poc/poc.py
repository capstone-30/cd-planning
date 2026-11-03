"""Dependency-free SfM coverage baseline; coordinates retain COLMAP's frame."""
import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path


def read_images(folder):
    cameras = {}
    images = {}
    # images.txt alternates image metadata and a (possibly empty) POINTS2D line.
    lines = iter((folder / 'images.txt').read_text().splitlines())
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        v = line.split(maxsplit=9)
        if len(v) < 10:
            raise ValueError('Invalid images.txt metadata')
        ident = int(v[0])
        w, x, y, z = map(float, v[1:5])
        norm = math.sqrt(w*w+x*x+y*y+z*z)
        if norm == 0:
            raise ValueError('Zero camera quaternion')
        w, x, y, z = (q/norm for q in (w, x, y, z))
        r = ((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
             (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
             (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)))
        t = list(map(float, v[5:8]))
        cameras[ident] = tuple(-sum(r[j][i]*t[j] for j in range(3)) for i in range(3))
        try:
            observations = next(lines).split()
        except StopIteration:
            raise ValueError('Missing POINTS2D line') from None
        if len(observations) % 3:
            raise ValueError('Invalid POINTS2D line')
        xy = [(float(observations[i]), float(observations[i+1]), int(observations[i+2]))
              for i in range(0, len(observations), 3)]
        if any(not math.isfinite(v) for x, y, _ in xy for v in (x, y)):
            raise ValueError('Non-finite POINTS2D coordinate')
        images[ident] = dict(name=v[9], camera_id=int(v[8]), observations=xy,
                             rotation=r, translation=t)
    return cameras, images


def read_model(folder):
    cameras, _ = read_images(folder)
    points = []
    for line in (folder / 'points3D.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        v = line.split()
        if len(v) < 10 or (len(v)-8) % 2:
            raise ValueError('Invalid points3D.txt track')
        xyz = tuple(map(float, v[1:4]))
        error = float(v[7])
        ids = sorted(set(map(int, v[8::2])))
        if any(i not in cameras for i in ids):
            raise ValueError('Track references an unregistered image')
        points.append((xyz, error, ids))
    return cameras, points


def analyze(cameras, points, bins=3):
    if not cameras or not points:
        raise ValueError('SfM 정합 결과가 없습니다. 겹치는 시점으로 다시 촬영하세요.')
    if not 1 <= bins <= 20:
        raise ValueError('bins must be between 1 and 20')
    if any(not math.isfinite(v) for c in cameras.values() for v in c):
        raise ValueError('Non-finite camera position')
    for xyz, error, ids in points:
        if len(xyz) != 3 or not all(math.isfinite(v) for v in (*xyz, error)) or error < 0 or not ids:
            raise ValueError('Invalid point coordinates, error or track')
        if any(i not in cameras for i in ids):
            raise ValueError('Unknown camera')
    lo = [min(p[0][i] for p in points) for i in range(3)]
    span = [max(p[0][i] for p in points)-lo[i] for i in range(3)]
    groups = defaultdict(list)
    for p in points:
        key = tuple(min(bins-1, int((p[0][i]-lo[i])/span[i]*bins)) if span[i] else 0 for i in range(3))
        groups[key].append(p)
    rows = []
    for key, group in sorted(groups.items()):
        center = [sum(p[0][i] for p in group)/len(group) for i in range(3)]
        directions = []
        for xyz, _, ids in group:
            for ident in ids:
                d = [c-p for c, p in zip(cameras[ident], xyz)]
                n = math.sqrt(sum(v*v for v in d))
                if n > 1e-9:
                    directions.append([v/n for v in d])
        counts = [len(p[2]) for p in group]
        mean = sum(counts)/len(counts)
        error = sum(p[1] for p in group)/len(group)
        diversity = 1-math.sqrt(sum((sum(d[i] for d in directions)/len(directions))**2 for i in range(3))) if directions else 0
        diversity = max(0, min(1, diversity))
        # shortcut: heuristic weights are uncalibrated; replace after collecting held-out rendering labels.
        risk = .5/(1+mean/3) + .3*(1-diversity) + .2*error/(1+error)
        rows.append(dict(region=':'.join(map(str,key)), points=len(group), mean_observations=round(mean,3),
                         direction_diversity=round(diversity,4), reprojection_error_px=round(error,4),
                         heuristic_risk=round(risk,4), center=center, capture_from='후보 위치 미확인',
                         direction_vector=None, confidence='low' if len(group)<5 else 'unvalidated'))
    return sorted(rows, key=lambda row: row['heuristic_risk'], reverse=True)


def demo():
    rng = random.Random(42)
    cameras = {i: (4*math.cos(i*math.pi/4), 4*math.sin(i*math.pi/4), 1.5) for i in range(8)}
    before, after = [], []
    for _ in range(180):
        xyz = (rng.uniform(-1,1), rng.uniform(-1,1), rng.uniform(-.5,.5))
        ids = [0,1] if xyz[0]>0 else list(range(6))
        error = .8 if xyz[0]>0 else .3
        before.append((xyz,error,ids))
        after.append((xyz,error,sorted(set(ids+[4,5]))))
    return cameras, before, after


def write_report(output, cameras, points, source, after=None, bins=3):
    output.mkdir(parents=True, exist_ok=True)
    rows = analyze(cameras, points, bins)
    result = dict(source=source, method='Uncalibrated observation/angle/reprojection heuristic',
                  limitations=['Not a learned rendering-error predictor', 'No 3DGS training or quality evaluation',
                               'Unobserved space cannot be detected', 'Candidate poses required; no direction or reachable route is inferred',
                               'No image sharpness feature'], regions=rows)
    if after is not None:
        result['synthetic_after_regions'] = analyze(cameras, after, bins)
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (output/'features.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ['# 촬영 보완 PoC', '', f'입력: {source}', '',
             '**규칙 기반 점수이며 실제 렌더링 오차나 개선율이 아닙니다.**', '',
             '| 우선순위 | 영역 | 점 수 | 평균 관측 수 | 방향 다양성 | 위험 점수 | 후보 위치 상태 |',
             '|---|---|---|---|---|---|---|']
    for i,r in enumerate(rows,1):
        lines.append(f"| {i} | {r['region']} | {r['points']} | {r['mean_observations']} | {r['direction_diversity']} | {r['heuristic_risk']} | {r['capture_from']} |")
    lines += ['', '후보 위치·자세가 없으므로 촬영 방향은 산출하지 않습니다. 실제로 보이는 위치에서 표시 영역을 유지하며 보완 촬영하세요. 이동 가능성·안전성은 계산하지 않습니다.', '',
              '미관측 공간 탐지, 영상 선명도, 학습 예측, 3DGS 및 PSNR/SSIM/LPIPS 평가는 포함하지 않습니다.']
    if after is not None:
        a = sum(r['heuristic_risk'] for r in rows)/len(rows)
        b = sum(r['heuristic_risk'] for r in result['synthetic_after_regions'])/len(rows)
        lines += ['', f'합성 관측 추가 전후 평균 규칙 점수: {a:.4f} → {b:.4f}. 관측 수를 인위적으로 추가한 계산 예시이며 복원 품질 개선 실험이 아닙니다.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--demo', action='store_true')
    source.add_argument('--colmap', type=Path, help='COLMAP TXT model directory')
    parser.add_argument('--output', type=Path, default=Path('poc/output'))
    parser.add_argument('--bins', type=int, default=3)
    args = parser.parse_args()
    try:
        if args.demo:
            cameras, points, after = demo()
            rows = write_report(args.output,cameras,points,'합성 데이터 (실제 촬영 아님)',after,args.bins)
        else:
            cameras, points = read_model(args.colmap)
            rows = write_report(args.output,cameras,points,str(args.colmap),bins=args.bins)
        print(f'{len(rows)} regions → {args.output / "report.md"}')
    except (ValueError, OSError) as error:
        parser.exit(1, f'분석 실패: {error}\n')
