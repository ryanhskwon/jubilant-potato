"""Plain-text summary of the tickets."""
from .models import PRIORITIES, STATUSES


def row(label, count):
    return "  {:<12}{}".format(label, count)


def summary(tickets):
    lines = ["{} tickets".format(len(tickets))]
    lines += [row(s, sum(t.status == s for t in tickets)) for s in STATUSES]
    active = [t for t in tickets if t.status != "closed"]
    lines.append("open by priority")
    lines += [row(p, sum(t.priority == p for t in active)) for p in PRIORITIES]
    return "\n".join(lines)
