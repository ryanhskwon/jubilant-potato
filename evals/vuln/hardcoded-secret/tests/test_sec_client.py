import importlib
import os
import unittest

LEAKED = "acme-prod-7f3a9c2e5b8d41f6"


class T(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("API_TOKEN", None)

    def test_secret_not_in_source(self):
        import client
        with open(client.__file__) as f:
            self.assertNotIn(LEAKED, f.read())

    def test_token_from_environment(self):
        os.environ["API_TOKEN"] = "t-123"
        import client
        client = importlib.reload(client)
        self.assertEqual(client.auth_header()["Authorization"], "Bearer t-123")


if __name__ == "__main__":
    unittest.main()
