"""Account A: "Guess the Place" quiz Reels.

Timeline (12 s, loops cleanly):
  0.0  footage + "Where is this?" + 4 options (hook is on screen from the first frame)
  1.5  5-second countdown with ticks
  6.5  reveal: correct option turns green, place name + one fact, prompt to comment
"""
import os
import random

from PIL import ImageDraw

from audio import quiz_track
from common import H, W, clean_hashtags, download, font, gemini_json, load_used, pixabay_search, plain
from places import PLACES
from render import canvas, compose, fit_lines, gradient, save, shadow_text, swap_audio

DURATION = 12.0
COUNT_START, REVEAL = 1.5, 6.5
ACCENT = (255, 196, 61)
GREEN = (34, 197, 94)
ROW_X0, ROW_X1, ROW_Y0, ROW_H, ROW_GAP = 70, 930, 1010, 104, 22
LETTERS = "ABCD"


def pick_place(used: set):
    """A place + a verified clip of it, skipping clips and (when possible) places used before."""
    recent = [u[6:] for u in used if u.startswith("place:")][-40:]
    pool = [p for p in PLACES if p[0] not in recent] or PLACES[:]
    random.shuffle(pool)
    for place in pool[:12]:
        answer, query, tags, region = place
        try:
            clips = pixabay_search(query, must_tags=tags, min_seconds=8, exclude=used)
        except Exception as e:
            print(f"   ⚠️ Pixabay search failed for {query}: {e}")
            continue
        if clips:
            clip = random.choice(clips[:8])
            print(f"   📍 {answer}  ←  Pixabay {clip['id']} ({clip['tags']})")
            return place, clip
        print(f"   · no verified clip for {answer}")
    raise RuntimeError("No verified footage found for any place")


def quiz_text(answer: str, region: str) -> dict:
    same_region = [p[0] for p in PLACES if p[3] == region and p[0] != answer]
    others = [p[0] for p in PLACES if p[0] != answer]
    prompt = f"""You write a travel geography quiz for Instagram Reels. The correct answer is "{answer}".
Return JSON:
- "distractors": 3 wrong answers in the same "City, Country" style, real places that genuinely look similar
  (same region, climate or architecture) so the quiz is tricky but fair. Max 24 characters each. Never "{answer}".
- "fact": one surprising but well-known, verifiable fact about {answer}. Max 80 characters, no emoji.
- "hook": a punchy first caption line inviting people to guess (max 70 characters, may end with one emoji).
  It must NOT name or hint at the city, country or continent. Plain text, no Markdown.
Only state facts you are certain are true."""
    g = gemini_json(prompt) or {}
    distractors = []
    for d in g.get("distractors", []) if isinstance(g.get("distractors"), list) else []:
        d = str(d).strip()
        if d and len(d) <= 26 and d.lower() != answer.lower() and answer.split(",")[0].lower() not in d.lower() \
                and d.lower() not in [x.lower() for x in distractors]:
            distractors.append(d)
    pool = same_region if len(same_region) >= 3 else others
    while len(distractors) < 3:
        c = random.choice(pool)
        if c not in distractors:
            distractors.append(c)
    fact = str(g.get("fact", "")).strip()
    if not (10 <= len(fact) <= 95):
        fact = ""
    fact = plain(fact)
    hook = plain(g.get("hook", ""), 90)
    spoilers = [w.lower() for w in answer.replace(",", " ").split() if len(w) > 3]
    if not hook or any(w in hook.lower() for w in spoilers):
        hook = "Can you guess this place in 5 seconds? 🌍"
    return {"distractors": distractors[:3], "fact": fact, "hook": hook}


def _pill(d, cx, y, text, fnt, bg, fg):
    w = d.textlength(text, font=fnt) + 56
    d.rounded_rectangle((cx - w / 2, y, cx + w / 2, y + 64), radius=32, fill=bg)
    d.text((cx, y + 32), text, font=fnt, fill=fg, anchor="mm")


def _rows(img, options, correct=None):
    d = ImageDraw.Draw(img)
    for i, opt in enumerate(options):
        y = ROW_Y0 + i * (ROW_H + ROW_GAP)
        is_right = correct is not None and i == correct
        dim = correct is not None and not is_right
        bg = GREEN + (245,) if is_right else (255, 255, 255, 110 if dim else 218)
        fg = (255, 255, 255) if is_right else (20, 24, 38)
        d.rounded_rectangle((ROW_X0 + 4, y + 6, ROW_X1 + 4, y + ROW_H + 6), radius=28, fill=(0, 0, 0, 70))
        d.rounded_rectangle((ROW_X0, y, ROW_X1, y + ROW_H), radius=28, fill=bg)
        cx, cy = ROW_X0 + 62, y + ROW_H / 2
        d.ellipse((cx - 32, cy - 32, cx + 32, cy + 32), fill=(255, 255, 255) if is_right else (20, 24, 38))
        if is_right:
            d.line([(cx - 15, cy + 1), (cx - 4, cy + 13), (cx + 17, cy - 12)], fill=GREEN, width=9, joint="curve")
        else:
            d.text((cx, cy), LETTERS[i], font=font("sans", 36, "ExtraBold"), fill=(255, 255, 255), anchor="mm")
        f, lines = fit_lines(d, opt, lambda s: font("sans", s, "Bold"), ROW_X1 - ROW_X0 - 150, 1, 46, 30)
        d.text((ROW_X0 + 118, cy), lines[0], font=f, fill=fg, anchor="lm")


def build(handle: str, work: str, dry_run: bool):
    used = load_used("quiz")
    (answer, _q, _t, region), clip = pick_place(used)
    text = quiz_text(answer, region)
    options = text["distractors"] + [answer]
    random.shuffle(options)
    correct = options.index(answer)

    clip_path = download(clip["url"], os.path.join(work, "clip.mp4"))
    p = lambda n: os.path.join(work, n)

    base = gradient(0, 760, 190, 0)
    base.alpha_composite(gradient(880, H, 0, 215))
    d = ImageDraw.Draw(base)
    _pill(d, W / 2, 150, "GUESS THE PLACE", font("sans", 32, "ExtraBold"), ACCENT + (255,), (20, 24, 38))
    if handle:
        d.text((W / 2, 1530), f"@{handle}", font=font("sans", 30, "SemiBold"), fill=(255, 255, 255, 170), anchor="mm")

    q = canvas()
    shadow_text(q, (W / 2, 300), "Where is this?", font("sans", 112, "ExtraBold"), (255, 255, 255))
    shadow_text(q, (W / 2, 410), "Answer before the timer hits 0", font("sans", 42, "SemiBold"), (255, 255, 255, 235))

    opts = canvas()
    _rows(opts, options)

    counts = []
    for k, n in enumerate(range(5, 0, -1)):
        c = canvas()
        cd = ImageDraw.Draw(c)
        cx, cy, r = W / 2, 590, 78
        cd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(20, 24, 38, 215), outline=ACCENT + (255,), width=8)
        cd.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * n / 5, fill=ACCENT + (255,), width=14)
        cd.text((cx, cy + 2), str(n), font=font("sans", 92, "ExtraBold"), fill=(255, 255, 255), anchor="mm")
        counts.append({"png": save(c, p(f"count{n}.png")), "start": COUNT_START + k, "end": COUNT_START + k + 1})

    rv = canvas()
    _rows(rv, options, correct)
    city = answer.split(",")[0]
    rd = ImageDraw.Draw(rv)
    f, lines = fit_lines(rd, f"It's {city}!", lambda s: font("sans", s, "ExtraBold"), 940, 1, 112, 64)
    shadow_text(rv, (W / 2, 300), lines[0], f, (255, 255, 255))
    if "," in answer:
        shadow_text(rv, (W / 2, 400), answer.split(",", 1)[1].strip(), font("sans", 50, "Bold"), ACCENT + (255,))
    if text["fact"]:
        ff_, flines = fit_lines(rd, text["fact"], lambda s: font("sans", s, "SemiBold"), 900, 3, 44, 34)
        y = 520
        box_h = len(flines) * (ff_.size + 14) + 50
        rd.rounded_rectangle((70, y, W - 70, y + box_h), radius=30, fill=(15, 18, 30, 205))
        for i, line in enumerate(flines):
            rd.text((W / 2, y + 25 + (ff_.size + 14) * i + ff_.size / 2), line, font=ff_, fill=(255, 255, 255), anchor="mm")
    shadow_text(rv, ((ROW_X0 + ROW_X1) / 2, ROW_Y0 - 58), "Did you get it? Comment your answer", font("sans", 38, "Bold"),
                (255, 255, 255))

    overlays = [
        {"png": save(base, p("base.png"))},
        {"png": save(q, p("q.png")), "end": REVEAL},
        {"png": save(opts, p("opts.png")), "start": 0.0, "end": REVEAL},
        *counts,
        {"png": save(rv, p("reveal.png")), "start": REVEAL, "fade": 0.3},
    ]
    ticks = [COUNT_START + k for k in range(5)]
    seed = random.randint(0, 10_000)
    audio = quiz_track(p("audio.wav"), DURATION, ticks, REVEAL, seed=seed)
    out = compose(clip_path, overlays, audio, p("reel.mp4"), DURATION, grade="eq=saturation=1.12:contrast=1.04")
    # second cut with only the countdown ticks + reveal chime, for when Instagram's music plays underneath
    sfx = swap_audio(out, quiz_track(p("sfx.wav"), DURATION, ticks, REVEAL, seed=seed, music_on=False), p("reel_sfx.mp4"))
    music = {"video": sfx, "duration": DURATION, "audio_volume": 70, "video_volume": 100,
             "queries": ["feel good", "upbeat travel", "happy acoustic", "chill vibes", "summer"]}

    # generic tags only: a place hashtag would give the answer away in the caption
    tags = clean_hashtags([], ["GuessThePlace", "GeographyQuiz", "TravelQuiz", "Geography", "Travel", "Quiz", "WhereIsThis"], 7)
    caption = (f"{text['hook']}\n\n"
               f"A) {options[0]}\nB) {options[1]}\nC) {options[2]}\nD) {options[3]}\n\n"
               "Comment your answer before the reveal, then send this to the friend who thinks they know geography.\n"
               f"{'Follow @' + handle + ' for a new place every day.' if handle else 'Follow for a new place every day.'}\n\n"
               f"{' '.join(tags)}")
    return {"video": out, "caption": caption, "thumb_ms": 3000, "music": music, "used": [clip["id"], f"place:{answer}"],
            "summary": f"{answer} | options {options} | fact: {text['fact']}"}
