"""Ticket operations. Every change is saved right away."""
from .models import PRIORITIES, TRANSITIONS, Ticket
from .store import StoreError


class ServiceError(Exception):
    pass


class Tracker:
    def __init__(self, store):
        self.store = store

    def create(self, title, priority="normal"):
        title = title.strip()
        if not title:
            raise ServiceError("title is empty")
        if priority not in PRIORITIES:
            raise ServiceError("unknown priority: {}".format(priority))
        ticket = Ticket(id=self.store.next_id(), title=title, priority=priority)
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

    def delete(self, ticket_id):
        self.get(ticket_id)
        self.store.remove(ticket_id)
        self.store.save()

    def get(self, ticket_id):
        try:
            return self.store.get(ticket_id)
        except StoreError as e:
            raise ServiceError(str(e))

    def list(self, status=None):
        return [t for t in self.store.all() if status is None or t.status == status]
