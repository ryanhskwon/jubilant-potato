import hashlib
import time
import unittest

from passwords import hash_password


class T(unittest.TestCase):
    def test_not_a_plain_fast_hash(self):
        stored = hash_password("correct horse")
        for name in ["md5", "sha1", "sha224", "sha256", "sha384", "sha512"]:
            self.assertNotIn(hashlib.new(name, b"correct horse").hexdigest(), stored, name)

    def test_salted(self):
        self.assertNotEqual(hash_password("same"), hash_password("same"))

    def test_slow_to_compute(self):
        t0 = time.perf_counter()
        hash_password("correct horse")
        self.assertGreater(time.perf_counter() - t0, 0.005, "a password hash needs a work factor")


if __name__ == "__main__":
    unittest.main()
