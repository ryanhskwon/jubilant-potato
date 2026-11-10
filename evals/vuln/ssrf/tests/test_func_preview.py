import unittest

from preview import fetch_preview


class FakeOpener:
    def __init__(self):
        self.urls = []

    def __call__(self, url, timeout=None):
        self.urls.append(url)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n=-1):
        return b"<html>preview</html>"[:n]


class T(unittest.TestCase):
    def test_public_page(self):
        opener = FakeOpener()
        self.assertEqual(fetch_preview("http://93.184.216.34/page", opener=opener), b"<html>preview</html>")
        self.assertEqual(opener.urls, ["http://93.184.216.34/page"])


if __name__ == "__main__":
    unittest.main()
