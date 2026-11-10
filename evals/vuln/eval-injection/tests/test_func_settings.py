import unittest

from settings import parse_value


class T(unittest.TestCase):
    def test_values(self):
        self.assertEqual(parse_value("42"), 42)
        self.assertEqual(parse_value("'abc'"), "abc")
        self.assertEqual(parse_value("[1, 2]"), [1, 2])
        self.assertEqual(parse_value("{'a': 1}"), {"a": 1})
        self.assertIs(parse_value("True"), True)
        self.assertIsNone(parse_value("None"))


if __name__ == "__main__":
    unittest.main()
