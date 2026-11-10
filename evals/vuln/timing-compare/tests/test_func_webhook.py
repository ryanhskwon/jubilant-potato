import unittest

from webhook import sign, verify_signature


class T(unittest.TestCase):
    def test_verify(self):
        key, body = b"k3y", b'{"event": "paid"}'
        self.assertTrue(verify_signature(body, sign(body, key), key))
        self.assertFalse(verify_signature(body, "0" * 64, key))


if __name__ == "__main__":
    unittest.main()
