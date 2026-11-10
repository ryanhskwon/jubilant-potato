import unittest

from profiles import update_profile


class T(unittest.TestCase):
    def test_cannot_grant_admin(self):
        user = {"name": "bob", "email": "b@x.example", "is_admin": False, "role": "user"}
        try:
            update_profile(user, {"name": "x", "is_admin": True, "role": "admin"})
        except Exception:
            pass
        self.assertIs(user["is_admin"], False)
        self.assertEqual(user["role"], "user")


if __name__ == "__main__":
    unittest.main()
