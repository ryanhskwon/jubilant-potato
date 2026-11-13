This repository is a small ticket tracker (package `tracker/`: models, JSON store, service, report, command line).
Implement the change request below. It touches several modules; read the code first.
Use only the Python 3.9 standard library; the machine is offline.
The visible tests cover part of the request. More tests check every point below when you finish, so follow the names and formats exactly.

## 1. Bug: deleting a ticket can overwrite another ticket

With tickets #1 and #2, deleting #1 and then adding a ticket gives the new ticket id 2, and it replaces the old #2.
Ticket ids must never be reused, also after the file is saved and loaded again (for example: create #1 #2 #3, delete #3, reload, create -> #4).

## 2. Assignee and due date

- `Ticket` gets two optional fields, `assignee` (str) and `due` (str, `YYYY-MM-DD`). Both default to `None`.
- `Tracker.create(title, priority="normal", assignee=None, due=None)`.
- `Tracker.assign(ticket_id, assignee)` sets the assignee and returns the ticket. `None` or `""` clears it.
- `Tracker.set_due(ticket_id, due)` sets the due date and returns the ticket. `None` clears it.
- A due date that is not a real calendar date in `YYYY-MM-DD` form (for example `2026-02-30`, `2026/01/05`, `tomorrow`) raises `ServiceError`, in both `create` and `set_due`.
- A ticket is overdue on a day `today` (a `datetime.date`) when it is not closed, has a due date, and the due date is before `today`. A ticket due today is not overdue.
- `Tracker.list(status=None, assignee=None, overdue_on=None)`: each given argument filters the list, and they combine. `overdue_on` is a `datetime.date`; with it, only tickets overdue on that day are listed.

## 3. Data file, version 2

- Saving writes `{"version": 2, "next_id": <id the next new ticket gets>, "tickets": [...]}`. Every ticket object also has `"assignee"` and `"due"` (`null` when unset).
- Version 1 files, the format this program writes today, must still load: missing `assignee` and `due` become `None`, and the next id is one more than the largest id in the file (1 for an empty file).
- Loading a file whose `"version"` is greater than 2 raises `StoreError`, so newer data is never silently dropped.

## 4. Command line

- `main(argv=None, path=None, out=None, today=None)`: the new `today` argument is a `datetime.date` used by `list --overdue` and `report`. When it is `None`, use `datetime.date.today()`.
- A ticket line is `#ID [STATUS] TITLE (PRIORITY)`, then ` @ASSIGNEE` if there is an assignee, then ` due YYYY-MM-DD` if there is a due date.
  Example: `#3 [open] Fix login (high) @kim due 2026-11-20`
- `add TITLE [--priority P] [--assignee NAME] [--due YYYY-MM-DD]` prints `created ` + the ticket line.
- `assign ID NAME` prints `assigned #ID to NAME`.
- `unassign ID` prints `unassigned #ID`.
- `due ID YYYY-MM-DD` prints `due #ID YYYY-MM-DD`.
- `list [--status S] [--assignee NAME] [--overdue]` prints one ticket line per ticket; the options combine like `Tracker.list`.
- Errors (including a bad due date and a newer data file) print `error: <message>` and return 1, as today.

## 5. Report

`summary(tickets, today=None)` keeps the current lines and adds:
- `open by assignee`, then one row per assignee of tickets that are not closed, sorted by name, then `(none)` for those without an assignee (only when there are any). Rows use the same format as the other rows.
- When `today` is given, a last line `overdue N`, where N is the number of tickets overdue on that day.
The `report` command passes `today`.

Example with `today` = 2026-11-13, tickets: #1 open high @kim due 2026-11-10, #2 in_progress normal @lee, #3 open normal @kim due 2026-11-20, #4 closed low @lee due 2026-11-01, #5 open high (no assignee):

```
5 tickets
  open        3
  in_progress 1
  closed      1
open by priority
  low         0
  normal      2
  high        2
open by assignee
  kim         2
  lee         1
  (none)      1
overdue 1
```
