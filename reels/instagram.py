"""Publish a Reel with the official Instagram API. Two connection types are supported, detected from the token:

  Facebook Login  (token starts with "EA")  Instagram account linked to a Facebook Page.
                  Needed for Instagram's own music library (Audio API). Page tokens do not expire.
  Instagram Login (token starts with "IG")  No Page needed, but no Instagram music; token lasts 60 days
                  and is refreshed on every run.

Flow: create a REELS container (resumable upload) -> send the file -> wait for processing -> publish.
With Facebook Login the Reel is first tried with a track from Instagram's library; if anything about that
fails, the same Reel is posted with its own built-in soundtrack instead, so a post is never lost.
"""
import json
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


def find_music(token: str, uid: str, queries, min_ms: int, prefer=(), avoid=()):
    """A track from Instagram's library (Meta's royalty-free Sound Collection is what the search returns)
    matching one of `queries` and long enough for the Reel. Titles containing a `prefer` word are chosen
    first; titles containing an `avoid` word are skipped."""
    if not _fb(token):
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
            return None  # not available for this app/account -> don't keep trying
        for a in r.get("audio") or r.get("data") or []:  # the API answers with "audio", the docs say "data"
            title = str(a.get("title", "")).lower()
            if a.get("audio_id") and a["audio_id"] not in seen and (a.get("duration_in_ms") or 0) >= min_ms \
                    and not any(w in title for w in avoid):
                seen.add(a["audio_id"])
                pool.append(a)
    if not pool:
        print("   ℹ️ Instagram music: no suitable track found")
        return None
    liked = [a for a in pool if any(w in str(a.get("title", "")).lower() for w in prefer)]
    pick = random.choice(liked or pool)
    print(f"   🎵 Instagram music: {pick.get('title')} — {pick.get('display_artist')}")
    return pick


def _container(token, uid, video_path, caption, thumb_ms, audio_cfg=None) -> str:
    data = {"media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
            "share_to_feed": "true", "thumb_offset": str(thumb_ms), "access_token": token}
    if audio_cfg:
        data["audio_configuration"] = json.dumps(audio_cfg)
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


def publish_reel(token, video_path, caption, thumb_ms=3000, handle="", music=None) -> dict:
    """music = {"queries": [...], "video": path of the cut without built-in music, "duration": s,
                "audio_volume": 1-100, "video_volume": 1-100}"""
    me = account(token, handle)
    uid = me["user_id"]
    print(f"   📲 posting to @{me.get('username')}")

    cid, used_music = None, None
    if music and _fb(token):
        track = find_music(token, uid, music["queries"], int(music["duration"] * 1000),
                           music.get("prefer", ()), music.get("avoid", ()))
        if track:
            try:
                cid = _container(token, uid, music["video"], caption, thumb_ms, {
                    "audio_id": track["audio_id"], "audio_volume": music.get("audio_volume", 100),
                    "video_volume": music.get("video_volume", 1)})
                used_music = f"{track.get('title')} — {track.get('display_artist')}"
            except Exception as e:
                print(f"   ℹ️ Instagram music could not be attached ({str(e)[:200]}); using built-in soundtrack")
    if cid is None:
        cid = _container(token, uid, video_path, caption, thumb_ms)

    pub = _check(requests.post(f"{_host(token)}/{uid}/media_publish", timeout=60,
                               data={"creation_id": cid, "access_token": token}))
    link = ""
    try:
        link = _check(requests.get(f"{_host(token)}/{pub['id']}", timeout=30,
                                   params={"fields": "permalink", "access_token": token})).get("permalink", "")
    except Exception:
        pass
    return {"id": pub["id"], "permalink": link, "music": used_music}
