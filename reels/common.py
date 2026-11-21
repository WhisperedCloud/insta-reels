"""Shared helpers: ffmpeg, fonts, Pixabay footage, Gemini JSON, used-item trackers."""
import json
import os
import random
import re
import shutil
import subprocess
import time

import requests
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "assets", "fonts")
W, H, FPS = 1080, 1920, 30


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = ffmpeg_bin()


def ff(args, check=True):
    r = subprocess.run([FFMPEG, "-hide_banner", "-y", "-loglevel", "error", "-nostdin", *args], capture_output=True, text=True,
                       timeout=900)
    if check and r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-800:]}")
    return r


def media_duration(path: str) -> float:
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def font(name: str, size: int, weight: str) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONTS, {"sans": "Manrope-Variable.ttf", "serif": "CormorantGaramond.ttf"}[name])
    f = ImageFont.truetype(path, size)
    f.set_variation_by_name(weight)
    return f


# ── Trackers (committed back to the repo so nothing repeats) ────────────────
def tracker_path(account: str) -> str:
    return os.path.join(HERE, f"used_{account}.txt")


def load_used(account: str) -> list:
    """Used items, oldest first."""
    p = tracker_path(account)
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [line.strip() for line in f if line.strip()]


def mark_used(account: str, *keys: str) -> None:
    with open(tracker_path(account), "a") as f:
        for k in keys:
            f.write(f"{k}\n")


# ── Pixabay footage ─────────────────────────────────────────────────────────
def pixabay_search(query: str, must_tags=(), min_seconds: float = 8, exclude=()) -> list:
    """Return usable clips for `query`. A clip qualifies only if its own tags contain one of `must_tags`
    (so a 'Venice' answer is never shown over random footage)."""
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("PIXABAY_API_KEY missing")
    r = requests.get("https://pixabay.com/api/videos/", timeout=30, params={
        "key": key, "q": query, "per_page": 80, "safesearch": "true", "order": "popular"})
    r.raise_for_status()
    out = []
    for hit in r.json().get("hits", []):
        tags = hit.get("tags", "").lower()
        if must_tags and not any(t in tags for t in must_tags):
            continue
        if hit.get("duration", 0) < min_seconds or f"px{hit['id']}" in exclude:
            continue
        v = hit.get("videos", {})
        best = None
        for size in ("large", "medium"):
            c = v.get(size) or {}
            if c.get("url") and (c.get("height", 0) >= 1080 or c.get("width", 0) >= 1920):
                best = c
                break
        if not best:
            continue
        out.append({"id": f"px{hit['id']}", "url": best["url"], "tags": tags, "duration": hit["duration"],
                    "w": best.get("width", 0), "h": best.get("height", 0)})
    return out


def download(url: str, path: str) -> str:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return path


# ── Gemini ──────────────────────────────────────────────────────────────────
def gemini_json(prompt: str, temperature: float = 0.8):
    """Return parsed JSON from Gemini, or None if unavailable (callers always have a fallback)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("   ⚠️ GEMINI_API_KEY missing, using fallback text")
        return None
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=40_000))
    cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature)
    for model in ("gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"):
        for attempt in range(2):
            try:
                raw = (client.models.generate_content(model=model, contents=prompt, config=cfg).text or "").strip()
                return json.loads(re.sub(r"^```(?:json)?|```$", "", raw).strip())
            except Exception as e:
                print(f"   ⚠️ Gemini {model} attempt {attempt + 1}: {str(e)[:140]}")
                if "NOT_FOUND" in str(e):
                    break
                time.sleep(4 * (attempt + 1))
    return None


def clean_hashtags(tags, base, limit=8) -> list:
    out = []
    for t in list(tags or []) + list(base):
        t = "#" + re.sub(r"[^A-Za-z0-9]", "", str(t))
        if len(t) > 2 and t.lower() not in [x.lower() for x in out]:
            out.append(t)
    return out[:limit]


def plain(text, limit=None) -> str:
    """Caption-safe text: Instagram shows Markdown symbols literally, so strip them."""
    t = re.sub(r"[*_`#]+", "", str(text or ""))
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t[:limit] if limit else t
