"""Tickets saved in one JSON file.

File format, version 1:
    {"version": 1, "tickets": [{"id": 1, "title": "...", "status": "open", "priority": "normal"}]}
"""
import json
import os

from .models import Ticket

VERSION = 1


class StoreError(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        self.tickets = {}
        if os.path.exists(path):
            self.load()

    def load(self):
        with open(self.path) as f:
            data = json.load(f)
        self.tickets = {}
        for item in data["tickets"]:
            ticket = Ticket.from_dict(item)
            self.tickets[ticket.id] = ticket

    def save(self):
        data = {"version": VERSION, "tickets": [t.to_dict() for t in self.all()]}
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, self.path)

    def next_id(self):
        return len(self.tickets) + 1

    def add(self, ticket):
        self.tickets[ticket.id] = ticket

    def get(self, ticket_id):
        if ticket_id not in self.tickets:
            raise StoreError("no ticket #{}".format(ticket_id))
        return self.tickets[ticket_id]

    def remove(self, ticket_id):
        self.get(ticket_id)
        del self.tickets[ticket_id]

    def all(self):
        return [self.tickets[k] for k in sorted(self.tickets)]
