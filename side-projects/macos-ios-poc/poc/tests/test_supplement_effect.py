import math
import unittest

import numpy as np

from check_supplement_effect import metrics, split_slots


class SupplementEffectTests(unittest.TestCase):
    def test_exact_holdouts_for_both_training_budgets(self):
        evaluation = [f'e{i}' for i in range(10)]
        for count in (60, 70):
            training = [f't{i}' for i in range(count)]
            period, slots = split_slots(training, evaluation)
            self.assertEqual(slots[::period], evaluation)
            self.assertEqual([s for i, s in enumerate(slots) if i % period], training)

    def test_leakage_or_duplicate_or_uneven_split_rejected(self):
        for train, ev in [(['x'], ['x']), (['x', 'x'], ['y']), (['a'], ['b', 'c'])]:
            with self.assertRaises(ValueError):
                split_slots(train, ev)

    def test_metrics_identity_and_known_constant_error(self):
        zero = np.zeros((20, 20, 3), dtype=np.uint8)
        self.assertEqual(metrics(zero, zero)['ssim'], 1)
        self.assertTrue(math.isinf(metrics(zero, zero)['psnr_db']))
        result = metrics(zero, zero+51)
        self.assertAlmostEqual(result['psnr_db'], -10*math.log10(.04))
        self.assertAlmostEqual(result['ssim'], .0001/.0401)
        with self.assertRaises(ValueError):
            metrics(zero, zero[:10])
