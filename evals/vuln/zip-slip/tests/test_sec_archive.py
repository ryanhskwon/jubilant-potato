import os
import tempfile
import unittest
import zipfile

from archive import extract


class T(unittest.TestCase):
    def test_entry_outside_dest(self):
        with tempfile.TemporaryDirectory() as d:
            zpath = os.path.join(d, "in.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("ok.txt", "fine")
                zf.writestr("../evil.txt", "owned")
            dest = os.path.join(d, "out")
            os.makedirs(dest)
            try:
                extract(zpath, dest)
            except Exception:
                pass
            self.assertFalse(os.path.exists(os.path.join(d, "evil.txt")))


if __name__ == "__main__":
    unittest.main()
