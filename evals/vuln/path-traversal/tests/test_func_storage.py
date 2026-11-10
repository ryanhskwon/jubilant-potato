import os
import tempfile
import unittest

from storage import read_upload


class T(unittest.TestCase):
    def test_read(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sub"))
            with open(os.path.join(d, "a.txt"), "w") as f:
                f.write("hello")
            with open(os.path.join(d, "sub", "b.txt"), "w") as f:
                f.write("world")
            self.assertEqual(read_upload(d, "a.txt"), "hello")
            self.assertEqual(read_upload(d, "sub/b.txt"), "world")


if __name__ == "__main__":
    unittest.main()
