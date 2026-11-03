import unittest

import numpy as np

from evaluate_guidance import direction_scores, layout, ssim


class GuidanceExperimentTests(unittest.TestCase):
    def test_fixed_evaluation_is_disjoint_and_identical_between_arms(self):
        initial = [f'a{i}' for i in range(60)]
        evaluation = [f'e{i}' for i in range(10)]
        first = layout(initial, [f'b{i}' for i in range(10)], evaluation)
        second = layout(initial, [f'c{i}' for i in range(10)], evaluation)
        self.assertEqual([v for v, e in first if e], evaluation)
        self.assertEqual([v for v, e in second if e], evaluation)
        self.assertEqual([i for i, (_, e) in enumerate(first) if e], list(range(0,80,8)))
        self.assertEqual(sum(not e for _,e in first), 70)
        with self.assertRaises(ValueError):
            layout(initial, evaluation, evaluation)

    def test_direction_ranking_and_opposite_candidate_detection(self):
        score, cosine = direction_scores([[0,0,0]], [[1,0,0]], [1], [[2,0,0], [-2,0,0], [0,2,0]])
        np.testing.assert_allclose(score, [1,-1,0])
        self.assertEqual(int(np.sum(np.any(cosine > 0, axis=1))), 1)
        with self.assertRaises(ValueError):
            direction_scores([[0,0,0]], [[1,0,0]], [1], [[0,0,0]])

    def test_ssim_identical_and_changed_images(self):
        a = np.full((24,24,3), 100, np.uint8)
        self.assertAlmostEqual(ssim(a,a), 1)
        self.assertLess(ssim(a,np.zeros_like(a)), .01)


if __name__ == '__main__':
    unittest.main()
