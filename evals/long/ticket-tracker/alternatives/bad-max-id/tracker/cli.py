"""Command line: python -m tracker <command> [options]

The data file is $TRACKER_FILE, or tickets.json in the current folder.
"""
import argparse
import datetime
import os
import sys

from .report import summary
from .service import ServiceError, Tracker
from .store import Store, StoreError


def parser():
    p = argparse.ArgumentParser(prog="tracker")
    sub = p.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("--priority", default="normal")
    add.add_argument("--assignee")
    add.add_argument("--due")
    move = sub.add_parser("move")
    move.add_argument("id", type=int)
    move.add_argument("status")
    assign = sub.add_parser("assign")
    assign.add_argument("id", type=int)
    assign.add_argument("name")
    unassign = sub.add_parser("unassign")
    unassign.add_argument("id", type=int)
    due = sub.add_parser("due")
    due.add_argument("id", type=int)
    due.add_argument("date")
    delete = sub.add_parser("delete")
    delete.add_argument("id", type=int)
    lst = sub.add_parser("list")
    lst.add_argument("--status")
    lst.add_argument("--assignee")
    lst.add_argument("--overdue", action="store_true")
    sub.add_parser("report")
    return p


def line(ticket):
    text = "#{} [{}] {} ({})".format(ticket.id, ticket.status, ticket.title, ticket.priority)
    if ticket.assignee:
        text += " @" + ticket.assignee
    if ticket.due:
        text += " due " + ticket.due
    return text


def main(argv=None, path=None, out=None, today=None):
    out = out or sys.stdout
    today = today or datetime.date.today()
    args = parser().parse_args(argv)
    try:
        tracker = Tracker(Store(path or os.environ.get("TRACKER_FILE", "tickets.json")))
        if args.command == "add":
            ticket = tracker.create(args.title, args.priority, args.assignee, args.due)
            out.write("created {}\n".format(line(ticket)))
        elif args.command == "move":
            out.write("moved {}\n".format(line(tracker.move(args.id, args.status))))
        elif args.command == "assign":
            tracker.assign(args.id, args.name)
            out.write("assigned #{} to {}\n".format(args.id, args.name))
        elif args.command == "unassign":
            tracker.assign(args.id, None)
            out.write("unassigned #{}\n".format(args.id))
        elif args.command == "due":
            tracker.set_due(args.id, args.date)
            out.write("due #{} {}\n".format(args.id, args.date))
        elif args.command == "delete":
            tracker.delete(args.id)
            out.write("deleted #{}\n".format(args.id))
        elif args.command == "list":
            for ticket in tracker.list(args.status, args.assignee, today if args.overdue else None):
                out.write(line(ticket) + "\n")
        elif args.command == "report":
            out.write(summary(tracker.list(), today) + "\n")
    except (ServiceError, StoreError) as e:
        out.write("error: {}\n".format(e))
        return 1
    return 0
