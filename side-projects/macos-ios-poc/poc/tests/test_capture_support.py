import unittest

from check_capture_support import registration_change


class CaptureSupportTests(unittest.TestCase):
    def test_recovery_does_not_hide_lost_or_still_missing_initial_frames(self):
        result = registration_change({'a', 'b', 'c', 'd'}, {'a', 'b'}, {'b', 'c', 'new'})
        self.assertEqual(result, dict(initially_unregistered=['c', 'd'], recovered_initial=['c'],
                                      lost_initial=['a'], still_unregistered=['a', 'd']))

    def test_unknown_initial_frame_rejected(self):
        with self.assertRaises(ValueError):
            registration_change({'a'}, {'other'}, {'a'})


if __name__ == '__main__':
    unittest.main()
