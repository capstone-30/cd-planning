"""Rank approved posed views using only initial SfM points, never rendered errors."""
import math
from pathlib import Path

import numpy as np

from poc import read_images


# Geometric operating limits, frozen before the v2 comparison; not quality-calibrated.
PARAMETERS = dict(min_angle_degrees=5, max_angle_degrees=45,
                  min_distance_ratio=.5, max_distance_ratio=2,
                  occlusion_cell_pixels=16, occlusion_depth_ratio=1.05, min_points=5)


def posed_candidates(model, approved_names):
    """Only undistorted pinhole models; approval is supplied, never inferred from SfM."""
    model = Path(model)
    _, images = read_images(model)
    intrinsics = {}
    for line in (model/'cameras.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        cid, kind, width, height, *values = line.split()
        values = list(map(float, values))
        if kind == 'PINHOLE' and len(values) == 4:
            fx, fy, cx, cy = values
        elif kind == 'SIMPLE_PINHOLE' and len(values) == 3:
            fx, cx, cy = values
            fy = fx
        else:
            raise ValueError('Candidate poses require undistorted pinhole cameras')
        intrinsics[int(cid)] = dict(width=int(width), height=int(height), fx=fx, fy=fy, cx=cx, cy=cy)
    lookup = {v['name']: v for v in images.values()}
    if len(set(approved_names)) != len(approved_names) or any(n not in lookup for n in approved_names):
        raise ValueError('Unknown or repeated candidate image')
    return [dict(id=n, approved=True, rotation=lookup[n]['rotation'], translation=lookup[n]['translation'],
                 **intrinsics[lookup[n]['camera_id']]) for n in approved_names]


def select_views(cameras, points, candidates, budget):
    """Greedy marginal parallax gain; fewer than budget is a valid result, never padded."""
    if not isinstance(budget, int) or budget < 1 or not points or not cameras:
        raise ValueError('Positive budget and an initial SfM model are required')
    xyz = np.asarray([p[0] for p in points], dtype=float)
    errors = np.asarray([p[1] for p in points], dtype=float)
    if xyz.shape != (len(points), 3) or not np.isfinite(xyz).all() or not np.isfinite(errors).all() or np.any(errors < 0):
        raise ValueError('Invalid initial SfM points')
    counts = np.asarray([len(set(p[2])) for p in points], dtype=float)
    if np.any(counts == 0) or any(i not in cameras for p in points for i in p[2]):
        raise ValueError('Invalid initial observation tracks')
    tracks = [sorted(set(p[2])) for p in points]
    point_index = np.repeat(np.arange(len(points)), counts.astype(int))
    offsets = np.r_[0, np.cumsum(counts.astype(int))[:-1]]
    observed = np.asarray([cameras[i] for ids in tracks for i in ids], dtype=float) - xyz[point_index]
    distances = np.linalg.norm(observed, axis=1)
    if not np.isfinite(observed).all() or np.any(distances < 1e-9):
        raise ValueError('Invalid initial camera centers')
    observed /= distances[:, None]
    mean_direction = np.add.reduceat(observed, offsets) / counts[:, None]
    mean_distance = np.add.reduceat(distances, offsets) / counts
    confidence = 1/(1+errors)
    near_cos = math.cos(math.radians(PARAMETERS['min_angle_degrees']))
    far_cos = math.cos(math.radians(PARAMETERS['max_angle_degrees']))
    cache, rejected, names = [], [], set()
    for candidate in candidates:
        name = candidate['id']
        if not isinstance(name, str) or not name or name in names:
            raise ValueError('Candidate IDs must be unique nonempty strings')
        names.add(name)
        if candidate.get('approved') is not True:
            rejected.append(dict(id=name, reason='not_approved'))
            continue
        rotation, translation = np.asarray(candidate['rotation'], dtype=float), np.asarray(candidate['translation'], dtype=float)
        width, height = candidate['width'], candidate['height']
        fx, fy, cx, cy = (float(candidate[k]) for k in ('fx', 'fy', 'cx', 'cy'))
        if (rotation.shape != (3,3) or translation.shape != (3,) or
                not np.isfinite(rotation).all() or not np.isfinite(translation).all() or
                not np.allclose(rotation.T@rotation, np.eye(3), atol=1e-5) or
                not np.isclose(np.linalg.det(rotation), 1, atol=1e-5) or
                not all(math.isfinite(v) for v in (width, height, fx, fy, cx, cy)) or
                not isinstance(width, int) or not isinstance(height, int) or
                min(width, height, fx, fy) <= 0 or max(width, height) > 8192):
            raise ValueError('Invalid candidate pose or intrinsics')
        center = -rotation.T @ translation
        delta = center-xyz
        distance = np.linalg.norm(delta, axis=1)
        directions = delta / np.maximum(distance[:, None], 1e-9)
        closest = np.maximum.reduceat(np.sum(observed*directions[point_index], axis=1), offsets)
        camera_points = np.einsum('ij,kj->ik', xyz, rotation) + translation
        if not np.isfinite(camera_points).all():
            raise ValueError('Candidate projection is not finite')
        depth = camera_points[:, 2]
        u = fx*camera_points[:,0]/np.maximum(depth, 1e-9) + cx
        v = fy*camera_points[:,1]/np.maximum(depth, 1e-9) + cy
        visible = (depth > 1e-9) & (u >= 0) & (u < width) & (v >= 0) & (v < height)
        # shortcut: sparse z-buffer is only an occlusion proxy; use measured depth before route guidance.
        ids = np.flatnonzero(visible)
        cell = PARAMETERS['occlusion_cell_pixels']
        columns = math.ceil(width/cell)
        bins = (u[ids]//cell).astype(int) + (v[ids]//cell).astype(int)*columns
        nearest = np.full(columns*math.ceil(height/cell), np.inf)
        np.minimum.at(nearest, bins, depth[ids])
        visible[ids] &= depth[ids] <= nearest[bins]*PARAMETERS['occlusion_depth_ratio']
        valid = (visible & (np.sum(directions*mean_direction, axis=1) > 0) &
                 (distance >= mean_distance*PARAMETERS['min_distance_ratio']) &
                 (distance <= mean_distance*PARAMETERS['max_distance_ratio']) & (closest >= far_cos))
        if np.sum(valid & (closest < near_cos)) < PARAMETERS['min_points']:
            rejected.append(dict(id=name, reason='insufficient_visible_novel_points'))
            continue
        cache.append(dict(id=name, directions=directions, closest=closest, valid=valid, center=center))
    selected = []
    while cache and len(selected) < budget:
        options = []
        for candidate in cache:
            valid = candidate['valid'] & (candidate['closest'] < near_cos)
            gain = np.where(valid, confidence*np.sqrt(np.maximum(0, 1-candidate['closest']**2))/(counts+1), 0)
            score = float(gain.sum()) if np.sum(valid) >= PARAMETERS['min_points'] else 0
            options.append((score, candidate, gain))
        score, best, gain = max(options, key=lambda item: (item[0], item[1]['id']))
        if score <= 1e-9:
            break
        selected.append(dict(id=best['id'], marginal_gain=score, evidence_points=int(np.sum(gain > 0)),
            camera_center=best['center'].tolist(), target_center=np.average(xyz, axis=0, weights=gain).tolist()))
        counts += best['valid']
        cache = [candidate for candidate in cache if candidate is not best]
        for candidate in cache:
            overlap = best['valid']
            similarity = np.sum(candidate['directions']*best['directions'], axis=1)
            candidate['closest'] = np.where(overlap, np.maximum(candidate['closest'], similarity), candidate['closest'])
    return dict(method='coverage_gain_v2', status='ready' if len(selected) == budget else 'insufficient_candidates',
                requested=budget, selected=selected, rejected=rejected, parameters=PARAMETERS.copy(),
                limitations=['Only initial sparse points are evaluated; unobserved space is not detected.',
                             'Approval must come from outside this selector; no reachable route is inferred.',
                             'Sparse occlusion and parallax gains are uncalibrated quality proxies.'])
