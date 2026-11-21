"""One-time setup: read keys from the local .env file and save them as GitHub secrets for this repo.

  python3 reels/setup_secrets.py

Reads (.env, never committed):
  GEMINI_API_KEY, PIXABAY_API_KEY
  FB_APP_ID, FB_APP_SECRET, FB_USER_TOKEN   (from the Meta developer app; the user token is short-lived)
  QUIZ_HANDLE, STOIC_HANDLE                  (Instagram usernames of the two accounts)
It swaps the short-lived Facebook token for a long-lived one, then fetches the Page token of the Page
linked to each Instagram account (Page tokens made this way do not expire) and stores it as
IG_TOKEN_QUIZ / IG_TOKEN_STOIC. Only standard-library modules are used.
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = "https://graph.facebook.com/v23.0"


def env():
    out = {}
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        sys.exit("No .env file found. Copy .env.example to .env and fill it in.")
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def get(url, **params):
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=30) as r:
        return json.load(r)


def set_secret(name, value):
    subprocess.run(["gh", "secret", "set", name], input=value, text=True, check=True, cwd=ROOT)
    print(f"  ✓ {name}")


def set_var(name, value):
    subprocess.run(["gh", "variable", "set", name, "--body", value], check=True, cwd=ROOT)
    print(f"  ✓ {name} = {value}")


def main():
    e = env()
    for k in ("GEMINI_API_KEY", "PIXABAY_API_KEY"):
        if e.get(k):
            set_secret(k, e[k])
        else:
            print(f"  · {k} is empty, skipped")
    if not all(e.get(k) for k in ("FB_APP_ID", "FB_APP_SECRET", "FB_USER_TOKEN")):
        print("  · Facebook app details are empty, Instagram tokens skipped")
        return
    long_token = get(f"{G}/oauth/access_token", grant_type="fb_exchange_token", client_id=e["FB_APP_ID"],
                     client_secret=e["FB_APP_SECRET"], fb_exchange_token=e["FB_USER_TOKEN"])["access_token"]
    pages = get(f"{G}/me/accounts", fields="name,access_token,instagram_business_account{id,username}",
                limit=100, access_token=long_token).get("data", [])
    linked = {p["instagram_business_account"]["username"].lower(): p for p in pages
              if p.get("instagram_business_account")}
    print("Instagram accounts found:", ", ".join("@" + u for u in linked) or "none")
    for acct in ("QUIZ", "STOIC"):
        handle = e.get(f"{acct}_HANDLE", "").lower().lstrip("@")
        if not handle:
            print(f"  · {acct}_HANDLE is empty, skipped")
        elif handle not in linked:
            print(f"  ✗ @{handle} is not linked to any of your Facebook Pages")
        else:
            set_secret(f"IG_TOKEN_{acct}", linked[handle]["access_token"])
            set_var(f"IG_HANDLE_{acct}", handle)


if __name__ == "__main__":
    main()
