"""Audit saved SfM/report evidence; does not measure guided recapture efficacy."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from poc import read_images, read_model


def registration_change(initial_input, initial_registered, combined_registered):
    if not initial_registered <= initial_input:
        raise ValueError('Initial model contains unknown frames')
    return dict(
        initially_unregistered=sorted(initial_input - initial_registered),
        recovered_initial=sorted((initial_input - initial_registered) & combined_registered),
        lost_initial=sorted(initial_registered - combined_registered),
        still_unregistered=sorted(initial_input - combined_registered),
    )


def audit(core):
    hashes = {}

    def record(path):
        hashes[str(path.relative_to(core))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path

    def load(path):
        return json.loads(record(path).read_text(encoding='utf-8'))

    summary = load(core/'summary.json')
    results, inputs, registered = {}, {}, {}
    for mode in ('initial', 'combined'):
        run = core/'api-data'/summary['project_id']/'runs'/summary['runs'][mode]['run_id']
        frames = [f for f in load(run/'frames.json') if f['selected']]
        inputs[mode] = {f['name'] for f in frames}
        assert len(inputs[mode]) == len(frames), 'Duplicate frame names'
        model = run/'colmap/text'
        record(model/'images.txt')
        record(model/'points3D.txt')
        cameras, points = read_model(model)
        _, images = read_images(model)
        registered[mode] = {v['name'] for v in images.values()}
        assert len(registered[mode]) == len(cameras), 'Duplicate registered names'
        assert registered[mode] <= inputs[mode], 'Unknown registered frames'
        report = load(run/'analysis/report.json')
        assets = load(run/'analysis/assets.json')
        assert report['registered_frames'] == len(cameras)
        assert report['input_frames'] == len(frames)
        assert summary['runs'][mode]['points'] == len(points)
        assert sum(r['points'] for r in report['regions']) == len(points)
        candidates = [r for r in report['regions'] if r['recommended']]
        assert len(candidates) <= 3
        assert sorted(r['rank'] for r in candidates) == list(range(1, len(candidates)+1))
        for row in candidates:
            assert row['points'] >= 5
            assert row['representative_image'] in registered[mode]
            box = row['bounding_box']
            assert len(box) == 4 and all(math.isfinite(v) and 0 <= v <= 1 for v in box)
            assert box[2] > 0 and box[3] > 0
            assert box[0]+box[2] <= 1.000001 and box[1]+box[3] <= 1.000001
            asset = record(run/'analysis'/assets[row['representative_asset_id']])
            assert asset.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
            assert row.get('direction_vector') is None and row.get('direction_asset_id') is None
        results[mode] = dict(input_frames=len(frames), registered_frames=len(cameras),
                             registration_ratio=len(cameras)/len(frames), sparse_points=len(points),
                             candidate_count=len(candidates), report_checks='passed')
    assert inputs['initial'] <= inputs['combined'], 'Initial input changed'
    return dict(kind='saved_evidence_audit', runs=results,
                initial_frame_change=registration_change(inputs['initial'], registered['initial'], registered['combined']),
                supplement_registered=len(registered['combined'] - inputs['initial']),
                guided_recapture_effect='not_measured',
                limitations=['Registration is not surface completeness or rendering quality.',
                             'Region IDs and point IDs are not comparable across independent SfM runs.',
                             'PNG signature and box bounds do not establish semantic correctness.'],
                source_sha256=hashes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, default=Path(__file__).parent/'data/core-check')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.core)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_sha256'}, ensure_ascii=False, indent=2))
