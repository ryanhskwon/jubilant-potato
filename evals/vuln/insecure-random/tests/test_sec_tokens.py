import random
import unittest
from unittest import mock

from tokens import new_reset_token


def refuse(*args, **kwargs):
    raise AssertionError("token drawn from the random module")


class T(unittest.TestCase):
    def test_not_reproducible_from_seed(self):
        random.seed(1234)
        a = new_reset_token()
        random.seed(1234)
        b = new_reset_token()
        self.assertNotEqual(a, b)

    def test_not_from_random_module(self):
        with mock.patch.object(random.Random, "random", refuse), \
                mock.patch.object(random.Random, "getrandbits", refuse):
            new_reset_token()


if __name__ == "__main__":
    unittest.main()
