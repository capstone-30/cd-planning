import tempfile
import unittest
from pathlib import Path
from poc import analyze, demo, read_model, read_points, region_bounds, region_index, write_report


class CoverageTests(unittest.TestCase):
    def test_added_views_reduce_heuristic(self):
        cameras, before, after = demo()
        a = {r['region']: r for r in analyze(cameras,before)}
        b = {r['region']: r for r in analyze(cameras,after)}
        self.assertEqual(a.keys(), b.keys())
        for key in a:
            self.assertLessEqual(b[key]['heuristic_risk'], a[key]['heuristic_risk'])
        self.assertTrue(any(b[k]['heuristic_risk'] < a[k]['heuristic_risk'] for k in a))

    def test_camera_pose_and_empty_observation_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'images.txt').write_text('# images\n1 1 0 0 0 -2 0 0 1 frame one.jpg\n\n2 0.7071067811865476 0 0 0.7071067811865476 0 -2 0 1 b.jpg\n0 0 1\n')
            (root/'points3D.txt').write_text('1 0 0 0 255 255 255 0.5 1 0 2 0\n')
            cameras, points = read_model(root)
            self.assertEqual(cameras[1], (2,0,0))
            self.assertAlmostEqual(cameras[2][0], 2)
            self.assertAlmostEqual(cameras[2][1], 0)
            rows = write_report(root/'result', cameras, points, 'fixture')
            self.assertEqual(rows[0]['capture_from'], '후보 위치 미확인')
            self.assertIsNone(rows[0]['direction_vector'])
            self.assertEqual(rows[0]['mean_observations'], 2)
            self.assertTrue((root/'result/report.json').exists())

    def test_failed_registration_and_invalid_values(self):
        with self.assertRaises(ValueError):
            analyze({}, [])
        with self.assertRaises(ValueError):
            analyze({0:(0,0,1)}, [((float('nan'),0,0),0,[0])])
        with self.assertRaises(ValueError):
            analyze({0:(0,0,1)}, [((0,0,0),0,[1])])

    def test_region_boundaries_and_flat_axes(self):
        points = [((x, 2, 0), .5, [1]) for x in (-3, -1, 1, 3)]
        lo, span = region_bounds(points)
        self.assertEqual([region_index(p[0], lo, span) for p in points],
                         [(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 0, 0)])
        self.assertEqual(region_index(points[-1][0], lo, span, bins=20), (19, 0, 0))

    def test_point_ids_preserve_file_order_and_reject_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lines = '9 0 0 0 255 255 255 0.5 1 0\n2 1 0 0 255 255 255 0.3 1 0\n'
            path = root/'points3D.txt'
            path.write_text(lines)
            self.assertEqual(list(read_points(root, {1: (0, 0, 1)})), [9, 2])
            path.write_text(lines + lines.splitlines()[0] + '\n')
            with self.assertRaisesRegex(ValueError, 'Duplicate point ID'):
                read_points(root, {1: (0, 0, 1)})


if __name__ == '__main__':
    unittest.main()
