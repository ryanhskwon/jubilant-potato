import unittest

from runtime import python_version


class T(unittest.TestCase):
    def test_version(self):
        self.assertTrue(python_version().startswith("Python 3"))


if __name__ == "__main__":
    unittest.main()
