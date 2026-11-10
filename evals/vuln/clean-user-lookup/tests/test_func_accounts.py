import unittest

from accounts import accounts_on_plan, add_account, connect


class T(unittest.TestCase):
    def test_lookup(self):
        conn = connect()
        add_account(conn, "beta", "pro")
        add_account(conn, "alpha", "pro")
        add_account(conn, "gamma", "free")
        self.assertEqual(accounts_on_plan(conn, "pro"), ["alpha", "beta"])
        self.assertEqual(accounts_on_plan(conn, "team"), [])


if __name__ == "__main__":
    unittest.main()
