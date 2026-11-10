import unittest

from render import render_comment


class T(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(render_comment("bob", "nice post"), '<div class="comment"><b>bob</b>: nice post</div>')


if __name__ == "__main__":
    unittest.main()
