"""Posting slots (UTC) and the 'is anything due?' check. Standard library only, so the workflow can
run it before installing anything.

GitHub starts scheduled workflows late and only a few times a day, and Instagram's API cannot schedule a
post. So an outside timer (cron-job.org) calls the workflow every 30 minutes, in any time zone; when a slot
is coming up within LOOKAHEAD the run renders the Reel, waits, and publishes at the slot time. A slot that
was missed is still posted up to GRACE late.

Slots are chosen for a global English audience (US + India are the two largest Reels audiences):
  quiz   13:30 UTC = 7:00 PM India / 8:30 AM US East      23:30 UTC = 6:30 PM US East / 3:30 PM US West
  stoic  01:30 UTC = 8:30 PM US East / 7:00 AM India      16:00 UTC = 9:30 PM India / 11:00 AM US East
"""
import os
import sys
from datetime import datetime, timedelta, timezone

SLOTS = {"quiz": ["13:30", "23:30"], "stoic": ["01:30", "16:00"]}
VARIANTS = {"01:30": "english", "16:00": "thanglish"}  # Stoic account: which slot posts which language
LOOKAHEAD = timedelta(minutes=40)  # a little over the timer's 30 minutes: one call always lands before the slot
GRACE = timedelta(hours=5)
HERE = os.path.dirname(os.path.abspath(__file__))


def _posted_path(acct):
    return os.path.join(HERE, f"posted_{acct}.txt")


def posted(acct) -> set:
    p = _posted_path(acct)
    if not os.path.exists(p):
        return set()
    with open(p) as f:
        return {line.split()[0] for line in f if line.strip()}


def record(acct, slot_key, note=""):
    with open(_posted_path(acct), "a") as f:
        f.write(f"{slot_key} {note}".strip() + "\n")


def due_slot(acct, now=None):
    """The slot to serve now as (key, datetime), or None."""
    now = now or datetime.now(timezone.utc)
    done = posted(acct)
    candidates = []
    for day in (-1, 0, 1):
        d = (now + timedelta(days=day)).date()
        for hhmm in SLOTS[acct]:
            h, m = map(int, hhmm.split(":"))
            t = datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)
            candidates.append((t.strftime("%Y-%m-%dT%H:%M"), t))
    for key, t in sorted(candidates, key=lambda c: c[1]):
        if key not in done and t - LOOKAHEAD <= now <= t + GRACE:
            return key, t
    return None


if __name__ == "__main__":
    s = due_slot(sys.argv[1])
    print(f"due={s[0] if s else ''}")
