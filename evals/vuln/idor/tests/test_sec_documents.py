import unittest

from documents import Store, get_document


class T(unittest.TestCase):
    def test_other_users_document(self):
        store = Store()
        store.add(1, "alice", "alice's notes")
        try:
            doc = get_document(store, "mallory", 1)
        except Exception:
            doc = None
        self.assertTrue(doc is None or doc.get("body") != "alice's notes")


if __name__ == "__main__":
    unittest.main()
