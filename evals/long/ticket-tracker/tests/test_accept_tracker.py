import datetime
import io
import json
import os
import tempfile
import unittest

from tracker.cli import main
from tracker.report import summary
from tracker.service import ServiceError, Tracker
from tracker.store import Store, StoreError

TODAY = datetime.date(2026, 11, 13)


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
        code = main(list(argv), path=self.path, out=out, today=TODAY)
        return code, out.getvalue()

    def write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f)

    def saved(self):
        with open(self.path) as f:
            return json.load(f)

    def sample(self):
        t = self.tracker()
        t.create("one", "high", "kim", "2026-11-10")
        t.create("two", assignee="lee")
        t.move(2, "in_progress")
        t.create("three", assignee="kim", due="2026-11-20")
        t.create("four", "low", "lee", "2026-11-01")
        t.move(4, "closed")
        t.create("five", "high")
        return t


class Ids(Base):
    def test_ids_not_reused_after_reload(self):
        t = self.tracker()
        for title in ("a", "b", "c"):
            t.create(title)
        t.delete(3)
        self.assertEqual(self.tracker().create("d").id, 4)

    def test_saved_file_is_version_2(self):
        self.tracker().create("a")
        data = self.saved()
        self.assertEqual((data["version"], data["next_id"]), (2, 2))
        item = data["tickets"][0]
        self.assertIsNone(item["assignee"])
        self.assertIsNone(item["due"])


class Compatibility(Base):
    def test_reads_version_1_file(self):
        self.write({"version": 1, "tickets": [
            {"id": 1, "title": "old", "status": "open", "priority": "normal"},
            {"id": 5, "title": "older", "status": "closed", "priority": "low"}]})
        t = self.tracker()
        self.assertEqual([x.title for x in t.list()], ["old", "older"])
        self.assertIsNone(t.get(1).assignee)
        self.assertIsNone(t.get(5).due)
        self.assertEqual(t.create("new").id, 6)
        self.assertEqual(self.saved()["version"], 2)

    def test_empty_version_1_file_starts_at_1(self):
        self.write({"version": 1, "tickets": []})
        self.assertEqual(self.tracker().create("a").id, 1)

    def test_rejects_newer_version(self):
        self.write({"version": 3, "next_id": 1, "tickets": []})
        self.assertRaises(StoreError, Store, self.path)
        code, out = self.cli("list")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("error: "))


class Fields(Base):
    def test_create_with_assignee_and_due_survives_reload(self):
        self.tracker().create("a", "high", "kim", "2026-11-20")
        again = self.tracker().get(1)
        self.assertEqual((again.priority, again.assignee, again.due), ("high", "kim", "2026-11-20"))

    def test_due_validation(self):
        t = self.tracker()
        self.assertRaises(ServiceError, t.create, "a", due="2026-02-30")
        self.assertEqual(t.list(), [])
        t.create("a")
        for bad in ("2026/01/05", "tomorrow", "2026-13-01"):
            self.assertRaises(ServiceError, t.set_due, 1, bad)
        self.assertEqual(t.set_due(1, "2026-02-28").due, "2026-02-28")
        self.assertIsNone(t.set_due(1, None).due)

    def test_assign_and_clear(self):
        t = self.tracker()
        t.create("a")
        t.assign(1, "kim")
        self.assertIsNone(t.assign(1, None).assignee)
        t.assign(1, "kim")
        self.assertIsNone(t.assign(1, "").assignee)
        self.assertIsNone(self.tracker().get(1).assignee)


class Listing(Base):
    def test_filters_combine(self):
        t = self.sample()
        self.assertEqual([x.id for x in t.list(assignee="kim")], [1, 3])
        self.assertEqual([x.id for x in t.list(status="closed", assignee="lee")], [4])
        self.assertEqual([x.id for x in t.list(status="open", assignee="lee")], [])

    def test_overdue(self):
        t = self.sample()
        t.create("due today", due="2026-11-13")
        self.assertEqual([x.id for x in t.list(overdue_on=TODAY)], [1])
        self.assertEqual([x.id for x in t.list(overdue_on=datetime.date(2026, 11, 21))], [1, 3, 6])
        self.assertEqual([x.id for x in t.list(assignee="lee", overdue_on=datetime.date(2026, 12, 1))], [])


class Cli(Base):
    def test_add_with_options(self):
        self.assertEqual(self.cli("add", "Fix login", "--priority", "high", "--assignee", "kim", "--due", "2026-11-20"),
                         (0, "created #1 [open] Fix login (high) @kim due 2026-11-20\n"))
        self.assertEqual(self.cli("add", "Docs", "--due", "2026-11-21"),
                         (0, "created #2 [open] Docs (normal) due 2026-11-21\n"))

    def test_assign_unassign_due(self):
        self.cli("add", "a")
        self.assertEqual(self.cli("assign", "1", "kim"), (0, "assigned #1 to kim\n"))
        self.assertEqual(self.cli("due", "1", "2026-11-01"), (0, "due #1 2026-11-01\n"))
        self.assertEqual(self.cli("list"), (0, "#1 [open] a (normal) @kim due 2026-11-01\n"))
        self.assertEqual(self.cli("unassign", "1"), (0, "unassigned #1\n"))
        self.assertEqual(self.cli("list"), (0, "#1 [open] a (normal) due 2026-11-01\n"))

    def test_list_options(self):
        self.sample()
        self.assertEqual(self.cli("list", "--overdue"), (0, "#1 [open] one (high) @kim due 2026-11-10\n"))
        self.assertEqual(self.cli("list", "--assignee", "lee", "--status", "in_progress"),
                         (0, "#2 [in_progress] two (normal) @lee\n"))

    def test_bad_due_is_an_error(self):
        self.cli("add", "a")
        for argv in (("add", "b", "--due", "2026-02-30"), ("due", "1", "soon")):
            code, out = self.cli(*argv)
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("error: "))
        self.assertEqual(self.cli("list"), (0, "#1 [open] a (normal)\n"))


class Report(Base):
    EXPECTED = ["5 tickets", "  open        3", "  in_progress 1", "  closed      1",
                "open by priority", "  low         0", "  normal      2", "  high        2",
                "open by assignee", "  kim         2", "  lee         1", "  (none)      1"]

    def test_report_with_today(self):
        t = self.sample()
        self.assertEqual(summary(t.list(), TODAY).splitlines(), self.EXPECTED + ["overdue 1"])
        self.assertEqual(self.cli("report"), (0, "\n".join(self.EXPECTED + ["overdue 1"]) + "\n"))

    def test_report_without_today_or_unassigned(self):
        t = self.sample()
        t.assign(5, "kim")
        lines = summary(t.list()).splitlines()
        self.assertEqual(lines[8:], ["open by assignee", "  kim         3", "  lee         1"])


if __name__ == "__main__":
    unittest.main()
