import os
import tempfile
import unittest
import zipfile

from archive import extract


class T(unittest.TestCase):
    def test_extract(self):
        with tempfile.TemporaryDirectory() as d:
            zpath = os.path.join(d, "in.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("a.txt", "A")
                zf.writestr("docs/b.txt", "B")
            dest = os.path.join(d, "out")
            os.makedirs(dest)
            extract(zpath, dest)
            with open(os.path.join(dest, "a.txt")) as f:
                self.assertEqual(f.read(), "A")
            with open(os.path.join(dest, "docs", "b.txt")) as f:
                self.assertEqual(f.read(), "B")


if __name__ == "__main__":
    unittest.main()
