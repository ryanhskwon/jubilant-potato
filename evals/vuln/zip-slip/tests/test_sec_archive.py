import os
import tempfile
import unittest
import zipfile

from archive import extract


def attack(d, name):
    zpath = os.path.join(d, "in.zip")
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("ok.txt", "fine")
        zf.writestr(name, "owned")
    dest = os.path.join(d, "out")
    os.makedirs(dest)
    try:
        extract(zpath, dest)
    except Exception:
        pass


class T(unittest.TestCase):
    def test_relative_entry_outside_dest(self):
        with tempfile.TemporaryDirectory() as d:
            attack(d, "../evil.txt")
            self.assertFalse(os.path.exists(os.path.join(d, "evil.txt")))

    def test_absolute_entry(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "abs_evil.txt")
            attack(d, target)
            self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()
