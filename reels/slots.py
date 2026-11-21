"""Posting slots (UTC) and the 'is anything due?' check. Standard library only, so the workflow can
run it before installing anything.

Instagram's API cannot schedule a post, and GitHub starts scheduled workflows late. The repo is private,
so GitHub minutes are limited (2,000 free a month) and the job must not sit waiting for long. So the
workflow is triggered three times before each slot (80, 40 and 12 minutes ahead). A run that starts
within LOOKAHEAD of the slot renders the Reel, waits the few minutes left and posts on time; a run that
starts after the slot posts straight away (up to GRACE late); a run that starts too early just exits.

Slots are chosen for a global English audience (US + India are the two largest Reels audiences):
  quiz   13:30 UTC = 7:00 PM India / 8:30 AM US East      23:30 UTC = 6:30 PM US East / 3:30 PM US West
  stoic  01:30 UTC = 8:30 PM US East / 7:00 AM India      16:00 UTC = 9:30 PM India / 11:00 AM US East
"""
import os
import sys
from datetime import datetime, timedelta, timezone

SLOTS = {"quiz": ["13:30", "23:30"], "stoic": ["01:30", "16:00"]}
VARIANTS = {"01:30": "english", "16:00": "thanglish"}  # Stoic account: which slot posts which language
LOOKAHEAD = timedelta(minutes=15)
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
    # prints e.g. "accounts=quiz" : accounts with a slot due now AND an Instagram token configured
    due = [a for a in sys.argv[1:] if os.environ.get(f"HAS_{a.upper()}") == "true" and due_slot(a)]
    print(f"accounts={' '.join(due)}")
