import sqlite3


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, name TEXT, plan TEXT)")
    return conn


def add_account(conn, name, plan):
    conn.execute("INSERT INTO accounts (name, plan) VALUES (?, ?)", (name, plan))
    conn.commit()


def accounts_on_plan(conn, plan):
    """Names of the accounts on a billing plan, sorted."""
    rows = conn.execute("SELECT name FROM accounts WHERE plan = ? ORDER BY name", (plan,)).fetchall()
    return [r[0] for r in rows]
