import io
import os
import tempfile
import unittest

from tracker.cli import main
from tracker.report import summary
from tracker.service import ServiceError, Tracker
from tracker.store import Store


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "tickets.json")

    def tearDown(self):
        self.dir.cleanup()

    def tracker(self):
        return Tracker(Store(self.path))

    def cli(self, *argv):
        out = io.StringIO()
        code = main(list(argv), path=self.path, out=out)
        return code, out.getvalue()


class Existing(Base):
    def test_create_numbers_from_one(self):
        t = self.tracker()
        self.assertEqual(t.create("  first ").id, 1)
        second = t.create("second", "high")
        self.assertEqual((second.id, second.title, second.status, second.priority), (2, "second", "open", "high"))
        self.assertEqual(t.get(1).title, "first")

    def test_create_rejects_bad_input(self):
        t = self.tracker()
        self.assertRaises(ServiceError, t.create, "   ")
        self.assertRaises(ServiceError, t.create, "x", "urgent")

    def test_move_follows_transitions(self):
        t = self.tracker()
        t.create("a")
        self.assertEqual(t.move(1, "in_progress").status, "in_progress")
        t.move(1, "closed")
        self.assertRaises(ServiceError, t.move, 1, "in_progress")
        self.assertEqual(t.move(1, "open").status, "open")

    def test_delete(self):
        t = self.tracker()
        t.create("a")
        t.delete(1)
        self.assertRaises(ServiceError, t.get, 1)
        self.assertRaises(ServiceError, t.delete, 1)

    def test_list_by_status(self):
        t = self.tracker()
        t.create("a")
        t.create("b")
        t.move(2, "closed")
        self.assertEqual([x.id for x in t.list()], [1, 2])
        self.assertEqual([x.id for x in t.list("closed")], [2])

    def test_changes_are_saved(self):
        t = self.tracker()
        t.create("a")
        t.move(1, "closed")
        again = self.tracker().get(1)
        self.assertEqual((again.title, again.status), ("a", "closed"))

    def test_report_counts(self):
        t = self.tracker()
        t.create("a", "high")
        t.create("b")
        t.move(2, "closed")
        lines = summary(t.list()).splitlines()
        self.assertEqual(lines[:8], ["2 tickets", "  open        1", "  in_progress 0", "  closed      1",
                                     "open by priority", "  low         0", "  normal      0", "  high        1"])

    def test_cli_add_list_move(self):
        self.assertEqual(self.cli("add", "Fix login", "--priority", "high"), (0, "created #1 [open] Fix login (high)\n"))
        self.cli("add", "Docs")
        self.assertEqual(self.cli("move", "2", "closed"), (0, "moved #2 [closed] Docs (normal)\n"))
        self.assertEqual(self.cli("list", "--status", "open"), (0, "#1 [open] Fix login (high)\n"))

    def test_cli_error(self):
        self.cli("add", "a")
        code, out = self.cli("move", "1", "done")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("error: "))


class Requested(Base):
    def test_delete_does_not_overwrite(self):
        t = self.tracker()
        t.create("a")
        t.create("b")
        t.delete(1)
        self.assertEqual(t.create("c").id, 3)
        self.assertEqual(t.get(2).title, "b")

    def test_assignee_in_ticket_line(self):
        t = self.tracker()
        t.create("a")
        self.assertEqual(t.assign(1, "kim").assignee, "kim")
        self.assertEqual(self.cli("list"), (0, "#1 [open] a (normal) @kim\n"))


if __name__ == "__main__":
    unittest.main()
