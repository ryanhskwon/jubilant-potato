import unittest

from render import render_comment


class T(unittest.TestCase):
    def test_markup_is_escaped(self):
        self.assertNotIn("<script", render_comment("bob", "<script>alert(1)</script>").lower())
        self.assertNotIn("<img", render_comment("<img src=x onerror=alert(1)>", "hi").lower())


if __name__ == "__main__":
    unittest.main()
