import unittest
import tempfile
from pathlib import Path

import numpy as np

from guidance import posed_candidates, select_views


def candidate(name, center=(1,0,0), rotation=None, approved=True):
    rotation = np.eye(3) if rotation is None else np.asarray(rotation)
    return dict(id=name, approved=approved, rotation=rotation.tolist(),
                translation=(-rotation@np.asarray(center)).tolist(),
                width=200, height=200, fx=100, fy=100, cx=100, cy=100)


class ViewSelectionTests(unittest.TestCase):
    def setUp(self):
        self.cameras = {1:(0,0,0), 2:(.02,0,0)}
        self.points = [((x,y,5),.5,[1,2]) for x in (-.03,0,.03) for y in (-.03,0,.03)]

    def test_rejects_backside_away_duplicate_and_unapproved(self):
        offscreen = candidate('offscreen')
        offscreen['fx'] = 2000
        result = select_views(self.cameras, self.points, [
            candidate('good'), candidate('same', (0,0,0)), candidate('unapproved', approved=False),
            candidate('away', rotation=np.diag([-1,1,-1])),
            candidate('backside', (0,0,10), np.diag([1,-1,-1])), offscreen], 2)
        self.assertEqual([v['id'] for v in result['selected']], ['good'])
        self.assertEqual(result['status'], 'insufficient_candidates')

    def test_greedy_does_not_fill_budget_with_duplicate_views(self):
        result = select_views(self.cameras, self.points, [candidate('one'), candidate('near-copy', (1.001,0,0))], 2)
        self.assertEqual(len(result['selected']), 1)
        self.assertEqual(result['status'], 'insufficient_candidates')
        self.assertGreater(result['selected'][0]['marginal_gain'], 0)

    def test_sparse_depth_proxy_excludes_points_behind_foreground(self):
        points = self.points + [((x,y,10),.5,[1,2]) for x in (-.03,0,.03) for y in (-.03,0,.03)]
        result = select_views(self.cameras, points, [candidate('one')], 1)
        self.assertEqual(result['selected'][0]['evidence_points'], 9)

    def test_pose_validation_and_sfm_scale_invariance(self):
        with self.assertRaises(ValueError):
            select_views(self.cameras, self.points, [candidate('invalid', rotation=np.zeros((3,3)))], 1)
        result = select_views(self.cameras, self.points, [candidate('one')], 1)
        scaled = select_views({k:tuple(np.array(v)*3) for k,v in self.cameras.items()},
            [(tuple(np.array(x)*3),e,ids) for x,e,ids in self.points], [candidate('one', (3,0,0))], 1)
        self.assertAlmostEqual(result['selected'][0]['marginal_gain'], scaled['selected'][0]['marginal_gain'])
        q = np.array([[0,-1,0],[1,0,0],[0,0,1]])
        rotated = select_views({k:q@v for k,v in self.cameras.items()},
            [(q@x,e,ids) for x,e,ids in self.points], [candidate('one', q@np.array([1,0,0]), q.T)], 1)
        self.assertAlmostEqual(result['selected'][0]['marginal_gain'], rotated['selected'][0]['marginal_gain'])

    def test_candidate_import_rejects_distortion_and_unknown_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'images.txt').write_text('1 1 0 0 0 0 0 0 1 frame.jpg\n\n')
            (root/'cameras.txt').write_text('1 SIMPLE_RADIAL 200 200 100 100 100 0.1\n')
            with self.assertRaises(ValueError):
                posed_candidates(root, ['frame.jpg'])
            (root/'cameras.txt').write_text('1 PINHOLE 200 200 100 100 100 100\n')
            with self.assertRaises(ValueError):
                posed_candidates(root, ['missing.jpg'])
            self.assertEqual(posed_candidates(root, ['frame.jpg'])[0]['fx'], 100)


if __name__ == '__main__':
    unittest.main()
