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
        return b"<html>internal</html>"[:n]


class T(unittest.TestCase):
    def test_internal_addresses_not_fetched(self):
        for url in ["http://127.0.0.1:8080/admin", "http://localhost/admin",
                    "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/", "http://[::1]/",
                    "file:///etc/passwd", "http://0.0.0.0/", "http://127.1/", "http://2130706433/",
                    "http://192.168.1.1/", "http://172.16.0.1/", "http://[::ffff:127.0.0.1]/"]:
            opener = FakeOpener()
            try:
                fetch_preview(url, opener=opener)
            except Exception:
                pass
            self.assertEqual(opener.urls, [], url)


if __name__ == "__main__":
    unittest.main()
