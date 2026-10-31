import unittest

from garmin_to_sigma.selection import ActivitySelection


class SelectionTests(unittest.TestCase):
    def selection(self, value, count=5):
        return ActivitySelection(count).indices(value)

    def test_empty_selection_means_all(self):
        self.assertEqual(ActivitySelection(4).indices(""), [0, 1, 2, 3])
        self.assertEqual(ActivitySelection(4).indices("all"), [0, 1, 2, 3])

    def test_single_and_multiple_indices(self):
        self.assertEqual(self.selection("3"), [2])
        self.assertEqual(self.selection("1, 3,5"), [0, 2, 4])

    def test_ranges_and_mixed_selection(self):
        self.assertEqual(ActivitySelection(8).indices("1-3, 5, 7-8"), [0, 1, 2, 4, 6, 7])

    def test_invalid_selection_is_rejected(self):
        with self.assertRaises(ValueError):
            self.selection("3-1")
        with self.assertRaises(ValueError):
            self.selection("0")
        with self.assertRaises(ValueError):
            self.selection("x")


if __name__ == "__main__":
    unittest.main()
