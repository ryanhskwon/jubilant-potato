#!/usr/bin/env python3
"""Pick the best model from results/ (test json, eval summary, loadtest csv).

Gates drop models that cannot serve the team. The rest are ranked by vulnerability
eval pass rate, then capacity. Pass rates one task apart count as a tie.
The long coding task score (evals/long) is shown next to them but does not change the
order: it is one task, too noisy to rank by.
Capacity comes from the newest loadtest csv already on disk; a model without one
is listed as missing, not excluded.

e.g. ./serve.sh report
"""
import csv
import glob
import json
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "results"
MIN_USERS = 4
INF = float("inf")
STAMP = re.compile(r"^(.+)-\d{8}-\d{4}\.csv$")


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rows_of(path):
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error):
        return []


def read_tool(model):
    try:
        with open(os.path.join(ROOT, "test", model + ".json")) as f:
            return bool(json.load(f)["checks"]["tool"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def read_eval(name, keys):
    """Latest row per model among runs on the same task list as the newest run, so a
    6-task quick run is never compared with a 21-task run."""
    rows = [r for r in rows_of(os.path.join(ROOT, "eval", name)) if r.get("model")]
    task_ids = rows[-1].get("task_ids") if rows else None
    latest = {}
    for r in rows:
        if r.get("task_ids") == task_ids:
            latest[r["model"]] = r
    return {m: {k: num(r.get(k)) for k in keys} for m, r in latest.items()}


def read_quality():
    return read_eval("summary-vuln.csv", ("pass_rate", "passed", "tasks", "detect_rate", "fix_rate", "regressions",
                                          "false_alarms", "clean", "vulnerable"))


def read_long():
    return {m: v["score"] for m, v in read_eval("summary-long.csv", ("score",)).items()}


def loadtest_files(model):
    return [p for p in glob.glob(os.path.join(ROOT, "loadtest", model + "-*.csv"))
            if STAMP.match(os.path.basename(p)) and STAMP.match(os.path.basename(p)).group(1) == model]


def read_capacity(model):
    for path in sorted(loadtest_files(model), key=os.path.getmtime, reverse=True):
        rows = [r for r in rows_of(path) if num(r.get("users")) is not None]
        if not rows:
            continue
        good = [r for r in rows if r.get("ok") == "True"]
        top = max(good, key=lambda r: num(r["users"]), default=None)
        one = next((r for r in rows if num(r["users"]) == 1), None)
        return {
            "max_users": int(num(top["users"])) if top else 0,
            "all_passed": len(good) == len(rows),
            "ttft1": num(one.get("ttft_p95")) if one else None,
            "session_s": num(top.get("session_s")) if top else None,
        }
    return None


def discover(quality):
    names = set(quality)
    for p in glob.glob(os.path.join(ROOT, "test", "*.json")):
        names.add(os.path.basename(p)[:-len(".json")])
    for p in glob.glob(os.path.join(ROOT, "loadtest", "*.csv")):
        m = STAMP.match(os.path.basename(p))
        if m:
            names.add(m.group(1))
    return names


GATES = [
    ("tool", lambda r: r["tool_ok"] is not False, "failed the tool-call check"),
    ("capacity", lambda r: r["capacity"] is None or r["capacity"]["max_users"] >= MIN_USERS,
     "fewer than {} users pass the speed target".format(MIN_USERS)),
]


def gate_failures(r):
    return [reason for _, ok, reason in GATES if not ok(r)]


def task_points(r):
    return 100.0 / r["quality"]["tasks"] if r["quality"]["tasks"] else 0.0


def tied(r, top):
    gap = max(task_points(r), task_points(top))
    return top["quality"]["pass_rate"] - r["quality"]["pass_rate"] <= gap + 1e-9


def sort_key(r, top):
    pass_rate = r["quality"]["pass_rate"]
    c = r["capacity"] or {"max_users": 0, "session_s": None}
    eff = top["quality"]["pass_rate"] if tied(r, top) else pass_rate
    return (-eff, -c["max_users"], c["session_s"] if c["session_s"] is not None else INF)


def fmt(v, spec):
    return "-" if v is None else format(v, spec)


ROW = "{:<17} {:>9} {:>4} {:>4} {:>5} {:>6} {:>5} {:>6} {:>6} {:>4} {:>4}"


def table(records):
    head = ROW.format("model", "pass", "det%", "fix%", "broke", "alarms", "users", "TTFT@1", "sess s", "long", "tool")
    lines = [head, "-" * len(head)]
    for r in records:
        q, c = r["quality"], r["capacity"]
        alarms = pas = "-"
        if q and q["pass_rate"] is not None:
            pas = "{:.0f}% {:.0f}/{:.0f}".format(q["pass_rate"], q["passed"] or 0, q["tasks"] or 0)
        if q and q["false_alarms"] is not None:
            alarms = "{:.0f}/{:.0f}".format(q["false_alarms"], q["clean"] or 0)
        tool = {True: "ok", False: "FAIL", None: "-"}[r["tool_ok"]]
        lines.append(ROW.format(
            r["model"][:17], pas, fmt(q and q["detect_rate"], ".0f"), fmt(q and q["fix_rate"], ".0f"),
            fmt(q and q["regressions"], ".0f"), alarms, fmt(c and c["max_users"], "d"),
            fmt(c and c["ttft1"], ".1f"), fmt(c and c["session_s"], ".0f"), fmt(r["long"], ".0f"), tool))
    return lines


def write_csv(path, ordered, ranked):
    cols = ["model", "status", "pass_rate", "passed", "tasks", "detect_rate", "fix_rate", "regressions",
            "false_alarms", "clean", "vulnerable", "max_users", "all_passed", "ttft1", "session_s", "long_score",
            "tool_ok",
            "reason"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in ordered:
            status = ("recommended" if ranked and r is ranked[0] else "ranked" if r in ranked
                      else "excluded" if r["excluded"] else "unranked")
            row = {"model": r["model"], "status": status, "tool_ok": r["tool_ok"], "long_score": r["long"],
                   "reason": "; ".join(r["excluded"])}
            row.update(r["quality"] or {})
            row.update(r["capacity"] or {})
            w.writerow({k: "" if v is None else v for k, v in row.items()})


def main():
    quality, long_scores = read_quality(), read_long()
    records = [{"model": m, "tool_ok": read_tool(m), "quality": quality.get(m), "capacity": read_capacity(m),
                "long": long_scores.get(m)}
               for m in sorted(discover(quality) | set(long_scores))]
    if not records:
        print("no results found under " + ROOT)
        return

    for r in records:
        r["excluded"] = gate_failures(r)
    ranked = [r for r in records if not r["excluded"] and r["quality"] and r["quality"]["pass_rate"] is not None]
    top = max(ranked, key=lambda r: r["quality"]["pass_rate"], default=None)
    if top:
        ranked.sort(key=lambda r: sort_key(r, top))
    ordered = ranked + [r for r in records if r not in ranked]

    print("\n".join(table(ordered)))
    print()
    if ranked:
        w = ranked[0]
        c = w["capacity"]
        tie_gap = task_points(top)
        group = [r for r in ranked if tied(r, top)]
        print("recommended: " + w["model"])
        print("  pass {:.0f}% ({:.0f}/{:.0f} tasks), {}".format(
            w["quality"]["pass_rate"], w["quality"]["passed"] or 0, w["quality"]["tasks"] or 0,
            "{} users, session {}s".format(c["max_users"], fmt(c["session_s"], ".0f")) if c
            else "no loadtest yet"))
        if w["long"] is not None:
            print("  long coding task score {:.0f} (shown, not used for the order)".format(w["long"]))
        print("  tie rule: pass rates 1 task apart ({:.1f} points) tie; capacity decides.".format(tie_gap))
        if len(group) > 1:
            print("  tied with the best pass rate: " + ", ".join(r["model"] for r in group))
        same = [r["model"] for r in ranked[1:] if sort_key(r, top) == sort_key(w, top)]
        if same:
            print("  NOT DECIDED, equal on pass and users, no session time to split them:")
            print("    " + ", ".join([w["model"]] + same))
            print("    rerun ./serve.sh loadtest for them (newer csv has session_s)")
    else:
        print("recommended: none (no model passed the gates with eval data)")
    excluded = [r for r in records if r["excluded"]]
    if excluded:
        print("\nexcluded:")
        for r in excluded:
            print("  {}: {}".format(r["model"], "; ".join(r["excluded"])))
    missing = []
    for r in records:
        gaps = [n for n, v in (("quality", r["quality"]), ("capacity", r["capacity"]), ("long", r["long"]))
                if v is None]
        if gaps:
            missing.append("{} ({})".format(r["model"], ", ".join(gaps)))
    if missing:
        print("\nmissing: " + ", ".join(missing))

    path = os.path.join(ROOT, "report.csv")
    try:
        write_csv(path, ordered, ranked)
        print("\nsaved: " + path)
    except OSError as e:
        print("\ncould not write {}: {}".format(path, e))


main()
