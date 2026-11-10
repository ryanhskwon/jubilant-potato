import unittest

from profiles import update_profile


class T(unittest.TestCase):
    def test_update(self):
        user = {"name": "bob", "email": "b@x.example", "is_admin": False}
        update_profile(user, {"name": "Bob K", "email": "bob@x.example"})
        self.assertEqual((user["name"], user["email"]), ("Bob K", "bob@x.example"))


if __name__ == "__main__":
    unittest.main()
