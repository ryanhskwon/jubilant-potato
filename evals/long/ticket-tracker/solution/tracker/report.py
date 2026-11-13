"""Plain-text summary of the tickets."""
from .models import PRIORITIES, STATUSES


def row(label, count):
    return "  {:<12}{}".format(label, count)


def summary(tickets, today=None):
    lines = ["{} tickets".format(len(tickets))]
    lines += [row(s, sum(t.status == s for t in tickets)) for s in STATUSES]
    active = [t for t in tickets if t.status != "closed"]
    lines.append("open by priority")
    lines += [row(p, sum(t.priority == p for t in active)) for p in PRIORITIES]
    lines.append("open by assignee")
    for name in sorted({t.assignee for t in active if t.assignee}):
        lines.append(row(name, sum(t.assignee == name for t in active)))
    unassigned = sum(not t.assignee for t in active)
    if unassigned:
        lines.append(row("(none)", unassigned))
    if today is not None:
        lines.append("overdue {}".format(sum(t.is_overdue(today) for t in tickets)))
    return "\n".join(lines)
