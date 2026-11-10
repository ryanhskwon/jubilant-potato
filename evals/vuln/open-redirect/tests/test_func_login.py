import unittest

from login import redirect_after_login


class T(unittest.TestCase):
    def test_local_pages(self):
        self.assertEqual(redirect_after_login("/dashboard"), "/dashboard")
        self.assertEqual(redirect_after_login("/search?q=a"), "/search?q=a")
        self.assertEqual(redirect_after_login(""), "/")
        self.assertEqual(redirect_after_login(None), "/")


if __name__ == "__main__":
    unittest.main()
