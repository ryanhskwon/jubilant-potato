import unittest

from passwords import hash_password, verify_password


class T(unittest.TestCase):
    def test_verify(self):
        stored = hash_password("correct horse")
        self.assertTrue(verify_password("correct horse", stored))
        self.assertFalse(verify_password("wrong", stored))


if __name__ == "__main__":
    unittest.main()
