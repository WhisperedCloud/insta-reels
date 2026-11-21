"""Publish a Reel with the official Instagram API. Two connection types are supported, detected from the token:

  Facebook Login  (token starts with "EA")  Instagram account linked to a Facebook Page.
                  Needed for Instagram's own music library (Audio API). Page tokens do not expire.
  Instagram Login (token starts with "IG")  No Page needed, but no Instagram music; token lasts 60 days
                  and is refreshed on every run.

Flow: create a REELS container (resumable upload) -> send the file -> wait for processing -> publish.
With Facebook Login a track from Instagram's music library is downloaded before rendering and mixed into the
video (see fetch_music); if that is not possible the Reel uses its own built-in soundtrack.
"""
import os
import random
import time

import requests

VERSION = "v23.0"


def _fb(token: str) -> bool:
    """Facebook Login tokens start with "EA..."; Instagram Login tokens start with "IG...". """
    return not token.startswith("IG")


def _host(token: str) -> str:
    return f"https://graph.{'facebook' if _fb(token) else 'instagram'}.com/{VERSION}"


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text[:500]}")
    return r.json()


def account(token: str, handle: str = "") -> dict:
    """{'user_id', 'username'} of the Instagram account this token posts to."""
    if not _fb(token):
        return _check(requests.get(f"{_host(token)}/me", timeout=30,
                                   params={"fields": "user_id,username", "access_token": token}))
    f = "instagram_business_account{id,username}"
    r = requests.get(f"{_host(token)}/me", params={"fields": f, "access_token": token}, timeout=30)
    if r.ok and r.json().get("instagram_business_account"):  # Page token
        a = r.json()["instagram_business_account"]
        return {"user_id": a["id"], "username": a.get("username", "")}
    pages = _check(requests.get(f"{_host(token)}/me/accounts", timeout=30,
                                params={"fields": f"name,{f}", "limit": 100, "access_token": token})).get("data", [])
    accts = [p["instagram_business_account"] for p in pages if p.get("instagram_business_account")]
    want = handle.lower().lstrip("@")
    for a in accts:
        if want and a.get("username", "").lower() == want:
            return {"user_id": a["id"], "username": a["username"]}
    if len(accts) == 1:
        return {"user_id": accts[0]["id"], "username": accts[0].get("username", "")}
    raise RuntimeError(f"Could not tell which Instagram account to use (found {[a.get('username') for a in accts]})")


def refresh_token(token: str):
    """Fresh 60-day token for Instagram Login; Facebook Page tokens need no refresh."""
    if _fb(token):
        return None
    try:
        r = requests.get("https://graph.instagram.com/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
        if r.ok and r.json().get("access_token"):
            return r.json()["access_token"]
        print(f"   ℹ️ token refresh skipped: {r.text[:200]}")
    except Exception as e:
        print(f"   ℹ️ token refresh failed: {e}")
    return None


def fetch_music(token, handle, out_path, queries, min_seconds, prefer=(), avoid=()):
    """Download a track from Instagram's music library to `out_path` so it can be mixed into the video.

    Why mix it in ourselves: attaching a track at publish time (audio_configuration) is accepted by the API
    but the published Reel then plays without it, so the music must already be inside the file.
    The search returns Meta's royalty-free Sound Collection tracks, which may be used in videos shared on
    Instagram and Facebook. Returns {"path", "title", "artist", "seconds"} or None (caller falls back to
    the built-in soundtrack)."""
    if not token or not _fb(token):
        return None
    try:
        uid = account(token, handle)["user_id"]
    except Exception as e:
        print(f"   ℹ️ Instagram music skipped: {str(e)[:160]}")
        return None
    qs = list(queries)
    random.shuffle(qs)
    pool, seen = [], set()
    for q in qs[:4]:
        try:
            r = _check(requests.get(f"{_host(token)}/ig_audio", timeout=30, params={
                "audio_type": "music", "user_id": uid, "search_query": q, "access_token": token}))
        except Exception as e:
            print(f"   ℹ️ Instagram music search '{q}' failed: {str(e)[:200]}")
            return None
        for a in r.get("audio") or r.get("data") or []:  # the API answers with "audio", the docs say "data"
            title = str(a.get("title", "")).lower()
            if a.get("audio_id") and a.get("download_url") and a["audio_id"] not in seen \
                    and (a.get("duration_in_ms") or 0) >= (min_seconds + 30) * 1000 \
                    and not any(w in title for w in avoid):
                seen.add(a["audio_id"])
                pool.append(a)
    liked = [a for a in pool if any(w in str(a.get("title", "")).lower() for w in prefer)]
    random.shuffle(liked)
    random.shuffle(pool)
    for pick in (liked + pool)[:4]:  # try a few in case one download fails
        try:
            with requests.get(pick["download_url"], stream=True, timeout=90,
                              headers={"User-Agent": "Mozilla/5.0 (reels-bot)"}) as resp:
                resp.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_content(1 << 18):
                        f.write(chunk)
            if os.path.getsize(out_path) > 50_000:
                print(f"   🎵 Instagram music: {pick.get('title')} — {pick.get('display_artist')}")
                return {"path": out_path, "title": pick.get("title", ""), "artist": pick.get("display_artist", ""),
                        "seconds": (pick.get("duration_in_ms") or 0) / 1000}
        except Exception as e:
            print(f"   ℹ️ could not download '{pick.get('title')}': {str(e)[:120]}")
    print("   ℹ️ Instagram music: no usable track, using the built-in soundtrack")
    return None


def _container(token, uid, video_path, caption, thumb_ms) -> str:
    data = {"media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
            "share_to_feed": "true", "thumb_offset": str(thumb_ms), "access_token": token}
    c = _check(requests.post(f"{_host(token)}/{uid}/media", data=data, timeout=60))
    cid = c["id"]
    uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VERSION}/{cid}"
    with open(video_path, "rb") as f:
        _check(requests.post(uri, data=f, timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(os.path.getsize(video_path))}))
    for _ in range(60):  # up to ~10 minutes
        s = _check(requests.get(f"{_host(token)}/{cid}", timeout=30,
                                params={"fields": "status_code,status", "access_token": token}))
        if s.get("status_code") == "FINISHED":
            return cid
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {s}")
        time.sleep(10)
    raise RuntimeError("Instagram processing timed out")


def publish_reel(token, video_path, caption, thumb_ms=3000, handle="") -> dict:
    me = account(token, handle)
    uid = me["user_id"]
    print(f"   📲 posting to @{me.get('username')}")
    cid = _container(token, uid, video_path, caption, thumb_ms)
    pub = _check(requests.post(f"{_host(token)}/{uid}/media_publish", timeout=60,
                               data={"creation_id": cid, "access_token": token}))
    link = ""
    try:
        link = _check(requests.get(f"{_host(token)}/{pub['id']}", timeout=30,
                                   params={"fields": "permalink", "access_token": token})).get("permalink", "")
    except Exception:
        pass
    return {"id": pub["id"], "permalink": link}
