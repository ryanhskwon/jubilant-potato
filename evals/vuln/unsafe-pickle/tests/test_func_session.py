import unittest

from session import dump_session, load_session


class T(unittest.TestCase):
    def test_roundtrip(self):
        data = {"user": "alice", "admin": False, "cart": [1, 2]}
        self.assertEqual(load_session(dump_session(data)), data)


if __name__ == "__main__":
    unittest.main()
