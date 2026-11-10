import unittest

from documents import Store, get_document


class T(unittest.TestCase):
    def test_own_document(self):
        store = Store()
        store.add(1, "alice", "alice's notes")
        self.assertEqual(get_document(store, "alice", 1)["body"], "alice's notes")
        self.assertIsNone(get_document(store, "alice", 2))


if __name__ == "__main__":
    unittest.main()
