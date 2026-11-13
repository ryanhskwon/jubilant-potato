"""Tickets saved in one JSON file.

File format, version 2:
    {"version": 2, "next_id": 3, "tickets": [{"id": 1, "title": "...", "status": "open",
     "priority": "normal", "assignee": null, "due": null}]}
Version 1 files (no next_id, no assignee or due) are still read.
"""
import json
import os

from .models import Ticket

VERSION = 2


class StoreError(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        self.tickets = {}
        self.next = 1
        if os.path.exists(path):
            self.load()

    def load(self):
        with open(self.path) as f:
            data = json.load(f)
        version = data.get("version", 1)
        if version > VERSION:
            raise StoreError("{} is version {}; this program reads up to {}".format(self.path, version, VERSION))
        self.tickets = {}
        for item in data["tickets"]:
            ticket = Ticket.from_dict(item)
            self.tickets[ticket.id] = ticket
        self.next = max(self.tickets, default=0) + 1

    def save(self):
        data = {"version": VERSION, "next_id": max(self.tickets, default=0) + 1, "tickets": [t.to_dict() for t in self.all()]}
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, self.path)

    def next_id(self):
        ticket_id = max(self.tickets, default=0) + 1
        self.next += 1
        return ticket_id

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
