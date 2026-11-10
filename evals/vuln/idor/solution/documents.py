class Store:
    def __init__(self):
        self.docs = {}

    def add(self, doc_id, owner, body):
        self.docs[doc_id] = {"id": doc_id, "owner": owner, "body": body}


def get_document(store, user, doc_id):
    """Return the document with this id for the logged-in user, or None if there is none."""
    doc = store.docs.get(doc_id)
    if doc is not None and doc["owner"] != user:
        raise PermissionError("not your document")
    return doc
