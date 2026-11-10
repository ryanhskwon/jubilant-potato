import random
import unittest

from tokens import new_reset_token


class T(unittest.TestCase):
    def test_not_reproducible_from_seed(self):
        random.seed(1234)
        a = new_reset_token()
        random.seed(1234)
        b = new_reset_token()
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
