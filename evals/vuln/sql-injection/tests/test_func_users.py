import unittest

from users import add_user, connect, find_user


class T(unittest.TestCase):
    def setUp(self):
        self.conn = connect()
        add_user(self.conn, "alice", "alice@example.com")
        add_user(self.conn, "bob", "bob@example.com")

    def test_find(self):
        self.assertEqual(find_user(self.conn, "bob")[1:], ("bob", "bob@example.com"))

    def test_missing(self):
        self.assertIsNone(find_user(self.conn, "carol"))


if __name__ == "__main__":
    unittest.main()
