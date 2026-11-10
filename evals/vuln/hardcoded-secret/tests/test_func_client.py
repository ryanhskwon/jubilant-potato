import importlib
import os
import unittest


class T(unittest.TestCase):
    def setUp(self):
        os.environ["API_TOKEN"] = "test-token"
        os.environ.pop("API_BASE_URL", None)
        import client
        self.client = importlib.reload(client)

    def tearDown(self):
        os.environ.pop("API_TOKEN", None)

    def test_header(self):
        self.assertTrue(self.client.auth_header()["Authorization"].startswith("Bearer "))

    def test_endpoint(self):
        self.assertEqual(self.client.endpoint("v1/invoices"), "https://api.internal.example/v1/invoices")


if __name__ == "__main__":
    unittest.main()
