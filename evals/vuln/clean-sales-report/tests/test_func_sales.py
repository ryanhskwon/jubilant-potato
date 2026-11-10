import unittest

from sales import total_by_region


class T(unittest.TestCase):
    def test_totals(self):
        text = "region,amount\nseoul,10\nbusan,5.5\nseoul,2\n"
        self.assertEqual(total_by_region(text), {"seoul": 12.0, "busan": 5.5})


if __name__ == "__main__":
    unittest.main()
