import string
import unittest

from tokens import new_reset_token


class T(unittest.TestCase):
    def test_token(self):
        a, b = new_reset_token(), new_reset_token()
        self.assertGreaterEqual(len(a), 20)
        self.assertTrue(set(a) <= set(string.ascii_letters + string.digits + "-_"))
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
