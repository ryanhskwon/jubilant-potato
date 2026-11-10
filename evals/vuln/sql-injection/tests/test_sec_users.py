import unittest

from users import add_user, connect, find_user


class T(unittest.TestCase):
    def setUp(self):
        self.conn = connect()
        add_user(self.conn, "alice", "alice@example.com")

    def test_injection_finds_nobody(self):
        try:
            row = find_user(self.conn, "nobody' OR '1'='1")
        except Exception:
            row = None
        self.assertIsNone(row)

    def test_quote_in_name(self):
        add_user(self.conn, "o'brien", "ob@example.com")
        self.assertEqual(find_user(self.conn, "o'brien")[1], "o'brien")


if __name__ == "__main__":
    unittest.main()
