import unittest

from validate import is_valid_email


class T(unittest.TestCase):
    def test_emails(self):
        self.assertTrue(is_valid_email("john.doe@example.com"))
        self.assertTrue(is_valid_email("a+b@mail.co.kr"))
        self.assertFalse(is_valid_email("no-at-sign"))
        self.assertFalse(is_valid_email("x@y"))


if __name__ == "__main__":
    unittest.main()
