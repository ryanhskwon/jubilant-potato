import unittest
from intervals import merge_intervals


class T(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(merge_intervals([(1, 3), (2, 6), (8, 10)]), [(1, 6), (8, 10)])

    def test_unsorted_and_touching(self):
        self.assertEqual(merge_intervals([(5, 7), (1, 2), (2, 4)]), [(1, 4), (5, 7)])

    def test_contained(self):
        self.assertEqual(merge_intervals([(1, 10), (2, 3)]), [(1, 10)])

    def test_empty(self):
        self.assertEqual(merge_intervals([]), [])


if __name__ == "__main__":
    unittest.main()
