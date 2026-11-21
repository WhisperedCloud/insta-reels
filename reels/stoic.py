"""Account D: Stoic Reels, in two variants.

  english    a real Stoic quote (hand-checked list) + an original "today, this means" line
  thanglish  a Tamil line in English letters (Kural, Avvaiyar, proverbs, original lines) + its meaning

Motion: words arrive one by one, a gold rule draws itself, the author and meaning rise in, dust drifts
behind the text, the footage pushes in slowly, and everything fades together so the Reel loops (see anim.py).
"""
import os
import random

from PIL import Image, ImageDraw, ImageFilter

import anim
from audio import quiet_track, stoic_track
from common import H, W, clean_hashtags, download, font, gemini_json, load_used, mark_used, pixabay_search, plain
from quotes import BACKDROPS, QUOTES
from render import fit_lines, swap_audio
from thanglish import THANGLISH

GOLD = (214, 178, 112)
IVORY = (250, 246, 238)
CX = W // 2


def _pick(items, used, prefix, account="stoic"):
    done = {u[len(prefix):] for u in used if u.startswith(prefix)}
    pool = [q for q in items if q[0][:60] not in done]
    if not pool:  # whole list used -> next cycle (fresh footage and caption each time)
        mark_used(account, f"cycle:{prefix}reset")
        pool = list(items)
    return random.choice(pool)


def pick_backdrop(used):
    choices = BACKDROPS[:]
    random.shuffle(choices)
    for query, tags in choices:
        try:
            clips = pixabay_search(query, must_tags=tags, min_seconds=10, exclude=used)
        except Exception as e:
            print(f"   ⚠️ Pixabay search failed for {query}: {e}")
            continue
        if clips:
            clip = random.choice(clips[:10])
            print(f"   🌫️ backdrop '{query}'  ←  Pixabay {clip['id']}")
            return clip
    raise RuntimeError("No backdrop footage found")


def english_text(quote, author):
    prompt = f"""You run a thoughtful Stoicism Instagram account. Today's quote:
"{quote}" — {author}
Do NOT change or re-word the quote. Return JSON (plain text only, no Markdown):
- "meaning": ONE plain-English line applying it to modern life (work, phones, relationships, money, stress).
  Specific, warm, not preachy. Max 95 characters. No emoji, no quotation marks.
- "hook": first caption line that stops the scroll, max 70 characters, no emoji.
- "reflection": 2-3 short sentences expanding the idea for the caption, practical, second person.
- "hashtags": 6 relevant hashtags (no '#')."""
    g = gemini_json(prompt, temperature=0.9) or {}
    meaning = plain(g.get("meaning", "")).strip('"“”')
    return {"meaning": meaning if 15 <= len(meaning) <= 110 else "",
            "hook": plain(g.get("hook", ""), 90) or f"{author} wrote this 2,000 years ago. Still true.",
            "reflection": plain(g.get("reflection", ""), 600), "hashtags": g.get("hashtags", [])}


def thanglish_text(line, source, meaning):
    prompt = f"""You run an Instagram account sharing Tamil wisdom written in Thanglish (Tamil in English letters)
for young Tamil speakers. Today's line: "{line}"{' (' + source + ')' if source else ''}
Its meaning in English: "{meaning}"
Do NOT change the line or its meaning. Return JSON (plain text only, no Markdown):
- "hook": first caption line in casual Thanglish or English that stops the scroll, max 70 characters, no emoji.
- "reflection": 2 short, practical sentences in simple English about using this idea today.
- "hashtags": 5 relevant hashtags (no '#')."""
    g = gemini_json(prompt, temperature=0.9) or {}
    return {"hook": plain(g.get("hook", ""), 90) or ("Paati sonna vaarthai, innaikum unmai." if source else "Indha line innaiku unakku thaan."),
            "reflection": plain(g.get("reflection", ""), 400), "hashtags": g.get("hashtags", [])}


def _base(handle):
    """Static layer: an even dark wash plus a soft darker pool behind the text."""
    base = Image.new("RGBA", (W, H), (0, 0, 0, 70))
    pool = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(pool).ellipse((-120, 380, W + 120, 1500), fill=(0, 0, 0, 120))
    base.alpha_composite(pool.filter(ImageFilter.GaussianBlur(160)))
    if handle:
        f = font("sans", 26, "Bold")
        ImageDraw.Draw(base).text((CX, 205), f"@{handle}".upper(), font=f, fill=(255, 255, 255, 150), anchor="mm")
    return base


def build(handle, work, dry_run, variant=None):
    used = load_used("stoic")
    variant = variant or os.environ.get("STOIC_VARIANT") or random.choice(["english", "thanglish"])
    if variant == "thanglish":
        quote, source, meaning = _pick(THANGLISH, used, "tq:")
        author, label = source, "MEANING"
        text = thanglish_text(quote, source, meaning)
        key = f"tq:{quote[:60]}"
    else:
        quote, author, source = _pick(QUOTES, used, "q:")
        text = english_text(quote, author)
        meaning, label = text["meaning"], "TODAY, THIS MEANS"
        key = f"q:{quote[:60]}"
    clip = pick_backdrop(used)
    clip_path = download(clip["url"], os.path.join(work, "clip.mp4"))

    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    qf, lines = fit_lines(probe, quote, lambda s: font("serif", s, "SemiBold"), 880, 6, 118 if len(quote) < 45 else 96, 58)
    lh = int(qf.size * 1.2)
    mf, mlines = (fit_lines(probe, meaning, lambda s: font("sans", s, "SemiBold"), 850, 3, 44, 34)
                  if meaning else (None, []))
    block = lh * len(lines)
    below = (185 if author else 80) + ((70 + len(mlines) * (mf.size + 16)) if mlines else 0)
    top = int(max(330, 860 - (block + below) / 2))

    sprites = []
    anim.place_text(sprites, "“", font("serif", 190, "Bold"), GOLD + (255,), CX, top + 40, 0.15, dur=0.8, rise=30)
    first_baseline = top + 90 + qf.getmetrics()[0]
    done = anim.place_words(sprites, lines, qf, IVORY + (255,), CX, first_baseline, lh, 0.55)
    y = first_baseline + lh * (len(lines) - 1) + 62
    t = done + 0.15
    anim.place_rule(sprites, CX, y, 96, GOLD + (235,), t)
    if author:
        if variant == "english":
            anim.place_text(sprites, author.upper(), font("sans", 38, "ExtraBold"), GOLD + (255,), CX, y + 66, t + 0.35)
            anim.place_text(sprites, source, font("serif", 40, "Medium"), (235, 230, 220, 215), CX, y + 116, t + 0.6)
        else:
            anim.place_text(sprites, author.upper(), font("sans", 32, "ExtraBold"), GOLD + (255,), CX, y + 62, t + 0.35)
        y += 185
    else:
        y += 80
    author_at = t + 0.35
    meaning_at = author_at + 1.1 + min(1.2, 0.05 * len(quote.split()))
    end_hold = 2.6
    if mlines:
        anim.place_text(sprites, label, font("sans", 26, "ExtraBold"), (255, 255, 255, 175), CX, y + 30, meaning_at,
                        blur=6)
        for i, line in enumerate(mlines):
            anim.place_text(sprites, line, mf, (255, 255, 255, 255), CX, y + 92 + i * (mf.size + 16),
                            meaning_at + 0.3 + 0.22 * i)
        end_hold = 2.4 + 0.3 * len(meaning.split())
        last_in = meaning_at + 0.3 + 0.22 * len(mlines) + 0.6
    else:
        last_in = author_at + 0.9
    duration = round(min(20.0, max(10.0, last_in + end_hold)), 2)

    seed = random.randint(0, 10_000)
    out = os.path.join(work, "reel.mp4")
    audio = stoic_track(os.path.join(work, "audio.wav"), duration, seed=seed)
    anim.render(clip_path, _base(handle), sprites, audio, out, duration, seed=seed)
    # second cut with a near-silent bed, for when a soothing track from Instagram's library carries the music
    quiet = swap_audio(out, quiet_track(os.path.join(work, "quiet.wav"), duration, seed), os.path.join(work, "reel_quiet.mp4"),
                       normalise=False)
    music = {"video": quiet, "duration": duration, "audio_volume": 100, "video_volume": 1,
             "queries": ["calm piano", "peaceful", "ambient", "soothing", "meditation", "cinematic calm", "soft piano"]}

    if variant == "thanglish":
        tags = clean_hashtags(text["hashtags"], ["Thanglish", "TamilQuotes", "TamilMotivation", "Tamil"] + (["Thirukkural"] if "Thirukkural" in source else []), 8)
        body = f"{text['hook']}\n\n“{quote}”\n" + (f"— {source}\n" if source else "") + f"\nMeaning: {meaning}\n"
        follow = "one Tamil thought every day"
    else:
        tags = clean_hashtags(text["hashtags"], ["Stoicism", "Stoic", "MarcusAurelius", "Seneca", "Philosophy", "Mindset"], 8)
        body = f"{text['hook']}\n\n“{quote}”\n— {author}, {source}\n"
        if meaning:
            body += f"\nToday, this means: {meaning}\n"
        follow = "one Stoic idea every day"
    if text["reflection"]:
        body += f"\n{text['reflection']}\n"
    body += ("\nSave this for the day you need it, and send it to someone who does.\n"
             f"Follow {'@' + handle + ' ' if handle else ''}for {follow}.\n\n{' '.join(tags)}")
    return {"video": out, "caption": body, "duration": duration, "thumb_ms": int((last_in + 0.6) * 1000), "music": music,
            "used": [clip["id"], key], "summary": f"[{variant}] {author or 'original'}: {quote} | meaning: {meaning}"}
