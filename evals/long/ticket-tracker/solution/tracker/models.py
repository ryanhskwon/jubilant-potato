"""Ticket record and the allowed values for its fields."""
import datetime
from dataclasses import asdict, dataclass
from typing import Optional

STATUSES = ("open", "in_progress", "closed")
PRIORITIES = ("low", "normal", "high")
TRANSITIONS = {
    "open": ("in_progress", "closed"),
    "in_progress": ("open", "closed"),
    "closed": ("open",),
}
DATE_FORMAT = "%Y-%m-%d"


def parse_date(text):
    return datetime.datetime.strptime(text, DATE_FORMAT).date()


@dataclass
class Ticket:
    id: int
    title: str
    status: str = "open"
    priority: str = "normal"
    assignee: Optional[str] = None
    due: Optional[str] = None

    def is_overdue(self, today):
        return self.status != "closed" and self.due is not None and parse_date(self.due) < today

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(id=data["id"], title=data["title"], status=data["status"], priority=data["priority"],
                   assignee=data.get("assignee"), due=data.get("due"))
