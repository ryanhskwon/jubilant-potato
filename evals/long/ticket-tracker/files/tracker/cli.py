"""Command line: python -m tracker <command> [options]

The data file is $TRACKER_FILE, or tickets.json in the current folder.
"""
import argparse
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
    move = sub.add_parser("move")
    move.add_argument("id", type=int)
    move.add_argument("status")
    delete = sub.add_parser("delete")
    delete.add_argument("id", type=int)
    lst = sub.add_parser("list")
    lst.add_argument("--status")
    sub.add_parser("report")
    return p


def line(ticket):
    return "#{} [{}] {} ({})".format(ticket.id, ticket.status, ticket.title, ticket.priority)


def main(argv=None, path=None, out=None):
    out = out or sys.stdout
    args = parser().parse_args(argv)
    try:
        tracker = Tracker(Store(path or os.environ.get("TRACKER_FILE", "tickets.json")))
        if args.command == "add":
            out.write("created {}\n".format(line(tracker.create(args.title, args.priority))))
        elif args.command == "move":
            out.write("moved {}\n".format(line(tracker.move(args.id, args.status))))
        elif args.command == "delete":
            tracker.delete(args.id)
            out.write("deleted #{}\n".format(args.id))
        elif args.command == "list":
            for ticket in tracker.list(args.status):
                out.write(line(ticket) + "\n")
        elif args.command == "report":
            out.write(summary(tracker.list()) + "\n")
    except (ServiceError, StoreError) as e:
        out.write("error: {}\n".format(e))
        return 1
    return 0
