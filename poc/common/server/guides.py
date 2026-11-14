import csv
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from poc import analyze, read_images, read_points, region_bounds, region_index
from .store import Failure, save


LIMITATIONS = [
    '규칙 기반 참고 점수이며 렌더링 오차·개선 확률이 아닙니다.',
    '점군에 없는 완전 미관측 공간은 검출하지 못합니다.',
    '후보 위치·자세가 없어 방향 화살표를 생성하지 않습니다. 이동 거리·안전한 경로를 추정하지 않습니다.',
    '5개 미만 점의 영역은 근거 점 부족으로 후보에서 제외합니다.',
    '실행마다 영역 구획이 달라지므로 같은 영역 ID로 전후 점수를 비교하지 않습니다.',
]


def region_key(xyz, lo, span):
    return ':'.join(map(str, region_index(xyz, lo, span)))


def make_report(run, input_frames, run_id):
    run = Path(run)
    model = run / 'colmap/text'
    cameras, images = read_images(model)
    points_by_id = read_points(model, cameras)
    points = list(points_by_id.values())
    rows = analyze(cameras, points, bins=3)
    lo, span = region_bounds(points)
    groups = {}
    for pid, (xyz, _, _) in points_by_id.items():
        groups.setdefault(region_key(xyz, lo, span), set()).add(pid)
    output = run/'analysis'
    output.mkdir(parents=True, exist_ok=True)
    assets = {}
    recommended = 0
    for row in rows:
        row.update(representative_asset_id=None, direction_asset_id=None, bounding_box=None,
                   instruction='표시 영역이 보이는 위치에서 화면에 유지하며 천천히 옆 시점으로 촬영하세요. 이동 가능 여부는 직접 확인하세요.',
                   recommended=False, evidence='근거 점 부족' if row['points'] < 5 else '미검증 규칙 기준')
        if row['points'] < 5 or recommended >= 3:
            continue
        ids = groups[row['region']]
        best = max(images.values(), key=lambda image: sum(pid in ids for _, _, pid in image['observations']))
        name = Path(best['name'])
        if name.is_absolute() or '..' in name.parts:
            raise Failure('INVALID_MODEL', 'COLMAP 이미지 경로가 올바르지 않습니다.')
        frame = cv2.imread(str(run/'frames'/name))
        if frame is None:
            raise Failure('INVALID_MODEL', '대표 프레임을 읽을 수 없습니다.')
        height, width = frame.shape[:2]
        xy = [(x, y) for x, y, pid in best['observations'] if pid in ids and 0 <= x < width and 0 <= y < height]
        if not xy:
            continue
        x, y = np.array(xy).min(axis=0)
        right, bottom = np.array(xy).max(axis=0)
        pad = max(10, (right-x)*.1, (bottom-y)*.1)
        x, y, right, bottom = max(0, x-pad), max(0, y-pad), min(width-1, right+pad), min(height-1, bottom+pad)
        row['bounding_box'] = [float(x/width), float(y/height), float((right-x)/width), float((bottom-y)/height)]
        row['representative_image'] = best['name']
        cv2.rectangle(frame, (int(x), int(y)), (int(right), int(bottom)), (0, 150, 255), 3)
        asset = str(uuid4())
        filename = f'{asset}.png'
        if not cv2.imwrite(str(output/filename), frame):
            raise Failure('GUIDE_WRITE_FAILED', '안내 이미지 저장에 실패했습니다.')
        assets[asset] = filename
        row['representative_asset_id'] = asset
        row.update(recommended=True, rank=recommended+1)
        recommended += 1
    result = dict(schema_version=2, run_id=run_id, source='real', method='region_guidance_v2',
                  viewpoint_status='candidate_pose_required',
                  registered_frames=len(cameras), input_frames=input_frames, regions=rows,
                  limitations=LIMITATIONS, message='추가 촬영 영역 후보' if recommended else '안내 근거 부족')
    save(output/'report.json', result)
    save(output/'assets.json', assets)
    with (output/'features.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: row.get(k) for k in writer.fieldnames} for row in rows)
    return result
