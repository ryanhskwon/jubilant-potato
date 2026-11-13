"""Ticket record and the allowed values for its fields."""
from dataclasses import asdict, dataclass

STATUSES = ("open", "in_progress", "closed")
PRIORITIES = ("low", "normal", "high")
TRANSITIONS = {
    "open": ("in_progress", "closed"),
    "in_progress": ("open", "closed"),
    "closed": ("open",),
}


@dataclass
class Ticket:
    id: int
    title: str
    status: str = "open"
    priority: str = "normal"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(id=data["id"], title=data["title"], status=data["status"], priority=data["priority"])
