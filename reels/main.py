"""Make one Reel for one account and post it.

  python reels/main.py quiz     # "Guess the Place" account
  python reels/main.py stoic    # Stoic quotes account

Env: PIXABAY_API_KEY, GEMINI_API_KEY, IG_TOKEN_QUIZ / IG_TOKEN_STOIC.
  RUN_MODE=schedule  post only if a slot is due (see slots.py), exactly at the slot time
  RUN_MODE=manual    post right away (default)
  DRY_RUN=1          render + check + save to OUT_DIR, never post (also used when no token is set)
"""
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import mark_used  # noqa: E402
import instagram  # noqa: E402
import qc  # noqa: E402
import quiz  # noqa: E402
import slots  # noqa: E402
import stoic  # noqa: E402

FORMATS = {"quiz": quiz, "stoic": stoic}
OUT_DIR = os.environ.get("OUT_DIR", "reels_output")


def wait_until(t):
    left = (t - datetime.now(timezone.utc)).total_seconds()
    if left > 0:
        print(f"   ⏳ Reel ready. Waiting {left / 60:.0f} min to post at {t:%H:%M} UTC")
        time.sleep(left)


def main(acct: str) -> int:
    fmt = FORMATS[acct]
    token = os.environ.get(f"IG_TOKEN_{acct.upper()}", "").strip()
    scheduled = os.environ.get("RUN_MODE") == "schedule"
    dry = os.environ.get("DRY_RUN") == "1" or not token
    os.makedirs(OUT_DIR, exist_ok=True)

    slot = None
    if scheduled:
        if not token:
            print(f"⏭️ No Instagram token for '{acct}' yet, nothing to do.")
            return 0
        slot = slots.due_slot(acct)
        if not slot:
            print(f"⏭️ No posting slot due for '{acct}'.")
            return 0
        print(f"🕒 Slot due: {slot[0]} UTC")

    handle = os.environ.get(f"IG_HANDLE_{acct.upper()}", "").strip().lstrip("@")
    if token:
        try:
            handle = instagram.account(token, handle).get("username") or handle
        except Exception as e:
            print(f"❌ Instagram token for '{acct}' is not working: {e}")
            if not dry:
                return 1
    print(f"🎬 Account: {acct}  handle: @{handle or '?'}  mode: {'DRY RUN (save only)' if dry else 'POST'}")

    for attempt in (1, 2, 3):
        work = tempfile.mkdtemp(prefix=f"reel_{acct}_")
        try:
            kw = {}
            if acct == "stoic" and slot:  # India-evening slot speaks Thanglish, US-evening slot English
                kw["variant"] = slots.VARIANTS.get(slot[0][-5:])
            r = fmt.build(handle, work, dry, **kw)
            expected = r.get("duration", getattr(fmt, "DURATION", 12.0))
            ok, report = qc.check(r["video"], expected)
            print(f"   🔍 QC: {'✅ PASS' if ok else '❌ FAIL'} — {report}")
            print(f"   📝 {r['summary']}")
            if not ok:
                continue
            n = sum(f.startswith(acct) and f.endswith(".mp4") for f in os.listdir(OUT_DIR)) + 1
            shutil.copy(r["video"], os.path.join(OUT_DIR, f"{acct}_{n}.mp4"))
            with open(os.path.join(OUT_DIR, f"{acct}_{n}.txt"), "w") as f:
                f.write(r["caption"] + "\n")
            if dry:
                print(f"   💾 saved {OUT_DIR}/{acct}_{n}.mp4 (not posted)")
                return 0
            if slot:
                wait_until(slot[1])
            music = r.get("music") if (os.environ.get("IG_MUSIC") or "on") != "off" else None
            res = instagram.publish_reel(token, r["video"], r["caption"], r.get("thumb_ms", 3000), handle, music)
            print(f"   ✅ Posted: {res.get('permalink') or res['id']}"
                  f"  (music: {res.get('music') or 'built-in soundtrack'})")
            mark_used(acct, *r["used"])
            if slot:
                slots.record(acct, slot[0], res.get("permalink", ""))
            new = instagram.refresh_token(token)
            if new and new != token:
                with open(os.path.join(OUT_DIR, f"new_token_{acct}.secret"), "w") as f:
                    f.write(new)
            return 0
        except Exception as e:
            print(f"   ❌ attempt {attempt} failed: {e}")
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "quiz"))
