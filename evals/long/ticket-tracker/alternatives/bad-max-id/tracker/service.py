"""Ticket operations. Every change is saved right away."""
from .models import PRIORITIES, TRANSITIONS, Ticket, parse_date
from .store import StoreError


class ServiceError(Exception):
    pass


def check_due(due):
    if due is None:
        return None
    try:
        parse_date(due)
    except (TypeError, ValueError):
        raise ServiceError("due must be a date like 2026-01-31, got {!r}".format(due))
    return due


class Tracker:
    def __init__(self, store):
        self.store = store

    def create(self, title, priority="normal", assignee=None, due=None):
        title = title.strip()
        if not title:
            raise ServiceError("title is empty")
        if priority not in PRIORITIES:
            raise ServiceError("unknown priority: {}".format(priority))
        due = check_due(due)
        ticket = Ticket(id=self.store.next_id(), title=title, priority=priority, assignee=assignee or None, due=due)
        self.store.add(ticket)
        self.store.save()
        return ticket

    def move(self, ticket_id, status):
        ticket = self.get(ticket_id)
        if status not in TRANSITIONS[ticket.status]:
            raise ServiceError("cannot move #{} from {} to {}".format(ticket.id, ticket.status, status))
        ticket.status = status
        self.store.save()
        return ticket

    def assign(self, ticket_id, assignee):
        ticket = self.get(ticket_id)
        ticket.assignee = assignee or None
        self.store.save()
        return ticket

    def set_due(self, ticket_id, due):
        ticket = self.get(ticket_id)
        ticket.due = check_due(due)
        self.store.save()
        return ticket

    def delete(self, ticket_id):
        self.get(ticket_id)
        self.store.remove(ticket_id)
        self.store.save()

    def get(self, ticket_id):
        try:
            return self.store.get(ticket_id)
        except StoreError as e:
            raise ServiceError(str(e))

    def list(self, status=None, assignee=None, overdue_on=None):
        return [t for t in self.store.all()
                if (status is None or t.status == status)
                and (assignee is None or t.assignee == assignee)
                and (overdue_on is None or t.is_overdue(overdue_on))]
