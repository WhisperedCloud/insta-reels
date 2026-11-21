"""Account A: "Guess the Place" quiz Reels.

Layout: the footage plays in its own clear window (nothing covers the place), over a blurred copy of
itself; the question sits above the window and the four answers in a 2x2 grid below it.

Timeline (12 s, loops cleanly):
  0.0  footage + "Where is this?" + 4 options (hook is on screen from the first frame)
  1.5  5-second countdown with ticks
  6.5  reveal: correct option turns green, place name + one fact, prompt to comment
"""
import os
import random
import subprocess

from PIL import Image, ImageDraw

from audio import quiz_track
from common import FFMPEG, H, W, clean_hashtags, download, font, gemini_json, load_used, pixabay_search, plain
from places import PLACES
from render import canvas, compose, fit_lines, save, shadow_text, swap_audio

DURATION = 12.0
COUNT_START, REVEAL = 1.5, 6.5
ACCENT = (255, 196, 61)
GREEN = (34, 197, 94)
WIN_X, WIN_Y, WIN_W, WIN_H = 40, 410, 1000, 880      # footage window
GRID_Y, CELL_H, GAP = 1322, 100, 16                   # answers: 2 x 2 below the window
CELL_W = (WIN_W - GAP) // 2
LETTERS = "ABCD"


def _other_place_tags(place):
    """Tags that belong to a different place in the list. A clip carrying one of them is tagged with
    several cities at once (or is really somewhere else), so it cannot be trusted as the answer."""
    own = set(place[2]) | {w.strip().lower() for w in place[0].split(",")}
    out = set()
    for other in PLACES:
        if other[0] != place[0]:
            out |= set(other[2]) - {"pyramid"}         # the other place's own tags (minus generic words)
            out.add(other[0].split(",")[0].lower())    # and its name
    return {t for t in out if len(t) > 3 and t not in own and not any(t in o or o in t for o in own)}


def candidates(used):
    """(place, clip) pairs whose tags name this place and no other place, newest places first."""
    recent = [u[6:] for u in used if u.startswith("place:")][-40:]
    pool = [p for p in PLACES if p[0] not in recent] or PLACES[:]
    random.shuffle(pool)
    for place in pool[:14]:
        answer, query, tags, _region = place
        try:
            clips = pixabay_search(query, must_tags=tags, min_seconds=8, exclude=used)
        except Exception as e:
            print(f"   ⚠️ Pixabay search failed for {query}: {e}")
            continue
        clash = _other_place_tags(place)
        clean = [c for c in clips if not any(t in [x.strip() for x in c["tags"].split(",")] for t in clash)]
        random.shuffle(clean)
        if not clean:
            print(f"   · no trustworthy clip for {answer}")
        for clip in clean[:2]:
            yield place, clip


def looks_right(clip_path, answer, work):
    """Ask Gemini to look at a frame: is this really (and recognisably) the place? None = could not check."""
    frame = os.path.join(work, "check.jpg")
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin", "-ss", "3", "-i", clip_path,
                    "-frames:v", "1", "-vf", "scale=768:-2", frame], capture_output=True, timeout=120)
    if not os.path.exists(frame):
        return None
    g = gemini_json(f"""This video frame is tagged as "{answer}" on a stock site and will be the answer in a
"guess the place" quiz. Return JSON: {{"is_place": true/false, "recognisable": true/false, "reason": "short"}}
- is_place: false if the frame clearly shows somewhere else or nothing place-specific (food, a person, an
  interior, abstract, plain sky/water/forest). true if it plausibly is {answer}.
- recognisable: true only if a traveller could reasonably identify {answer} from what is visible
  (landmark, skyline, distinctive architecture or landscape).""", temperature=0.1, image_jpeg=open(frame, "rb").read())
    if not g:
        return None
    ok = bool(g.get("is_place")) and bool(g.get("recognisable"))
    print(f"   👁️ visual check for {answer}: {'OK' if ok else 'rejected'} ({str(g.get('reason', ''))[:90]})")
    return ok


def pick_place(used, work):
    """A place plus a clip of it that passed the tag rules and, when Gemini is reachable, a visual check."""
    unchecked = None
    for n, (place, clip) in enumerate(candidates(used)):
        if n >= 8:
            break
        path = os.path.join(work, f"clip{n}.mp4")
        try:
            download(clip["url"], path)
        except Exception as e:
            print(f"   ⚠️ {e}")
            continue
        verdict = looks_right(path, place[0], work)
        if verdict:
            print(f"   📍 {place[0]}  ←  Pixabay {clip['id']} ({clip['tags'][:120]})")
            return place, clip, path
        if verdict is None and unchecked is None:
            unchecked = (place, clip, path)
    if unchecked:  # Gemini was down for every candidate: fall back to the tag-verified clip
        print(f"   📍 {unchecked[0][0]}  ←  Pixabay {unchecked[1]['id']} (tags only, visual check unavailable)")
        return unchecked
    raise RuntimeError("No verified footage found for any place")


def quiz_text(answer: str, region: str) -> dict:
    same_region = [p[0] for p in PLACES if p[3] == region and p[0] != answer]
    others = [p[0] for p in PLACES if p[0] != answer]
    prompt = f"""You write a travel geography quiz for Instagram Reels. The correct answer is "{answer}".
Return JSON:
- "distractors": 3 wrong answers in the same "City, Country" style, real places that genuinely look similar
  (same region, climate or architecture) so the quiz is tricky but fair. Max 24 characters each. Never "{answer}".
- "fact": one well-known, easily verifiable fact about {answer}. Max 80 characters, no emoji.
  Prefer simple facts (what it is famous for, when it was built, a UNESCO listing). Avoid statistics,
  percentages and "largest / oldest / only" claims unless they are textbook-certain.
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
    if fact:  # second opinion: a wrong fact on a quiz account costs more than no fact
        v = gemini_json(f'''Fact-check this statement about {answer}: "{fact}"
Return JSON {{"accurate": true/false, "reason": "short"}}. Answer true ONLY if you are certain it is correct
exactly as written, including any numbers, dates and superlatives. If in doubt, answer false.''', temperature=0.0)
        if not v or not v.get("accurate"):
            print(f"   · fact dropped ({'not confirmed' if v else 'could not check'}): {fact}")
            fact = ""
    hook = plain(g.get("hook", ""), 90)
    spoilers = [w.lower() for w in answer.replace(",", " ").split() if len(w) > 3]
    if not hook or any(w in hook.lower() for w in spoilers):
        hook = "Can you guess this place in 5 seconds? 🌍"
    return {"distractors": distractors[:3], "fact": fact, "hook": hook}


def _pill(d, cx, y, text, fnt, bg, fg):
    w = d.textlength(text, font=fnt) + 56
    d.rounded_rectangle((cx - w / 2, y, cx + w / 2, y + 64), radius=32, fill=bg)
    d.text((cx, y + 32), text, font=fnt, fill=fg, anchor="mm")


def _grid(img, options, correct=None):
    d = ImageDraw.Draw(img)
    for i, opt in enumerate(options):
        x = WIN_X + (i % 2) * (CELL_W + GAP)
        y = GRID_Y + (i // 2) * (CELL_H + GAP)
        is_right = correct is not None and i == correct
        dim = correct is not None and not is_right
        bg = GREEN + (255,) if is_right else (255, 255, 255, 95 if dim else 240)
        fg = (255, 255, 255) if is_right else (20, 24, 38)
        d.rounded_rectangle((x, y, x + CELL_W, y + CELL_H), radius=26, fill=bg)
        cx, cy = x + 52, y + CELL_H / 2
        d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=(255, 255, 255) if is_right else (20, 24, 38))
        if is_right:
            d.line([(cx - 14, cy + 1), (cx - 4, cy + 12), (cx + 16, cy - 11)], fill=GREEN, width=8, joint="curve")
        else:
            d.text((cx, cy), LETTERS[i], font=font("sans", 34, "ExtraBold"), fill=(255, 255, 255), anchor="mm")
        f, lines = fit_lines(d, opt, lambda s: font("sans", s, "Bold"), CELL_W - 112, 1, 38, 24)
        d.text((x + 96, cy), lines[0], font=f, fill=fg, anchor="lm")


def build(handle: str, work: str, dry_run: bool):
    used = load_used("quiz")
    (answer, _q, _t, region), clip, clip_path = pick_place(used, work)
    text = quiz_text(answer, region)
    options = text["distractors"] + [answer]
    random.shuffle(options)
    correct = options.index(answer)

    p = lambda n: os.path.join(work, n)
    win_r, win_b = WIN_X + WIN_W, WIN_Y + WIN_H

    mask = Image.new("L", (WIN_W, WIN_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, WIN_W - 1, WIN_H - 1), radius=44, fill=255)
    mask.save(p("mask.png"))

    base = canvas()
    d = ImageDraw.Draw(base)
    _pill(d, W / 2, 168, "GUESS THE PLACE", font("sans", 32, "ExtraBold"), ACCENT + (255,), (20, 24, 38))
    d.rounded_rectangle((WIN_X, WIN_Y, win_r, win_b), radius=44, outline=(255, 255, 255, 235), width=5)
    if handle:
        hf = font("sans", 28, "Bold")
        hw = d.textlength(f"@{handle}", font=hf) + 36
        d.rounded_rectangle((WIN_X + 22, WIN_Y + 22, WIN_X + 22 + hw, WIN_Y + 72), radius=25, fill=(15, 18, 30, 150))
        d.text((WIN_X + 22 + hw / 2, WIN_Y + 47), f"@{handle}", font=hf, fill=(255, 255, 255, 235), anchor="mm")

    q = canvas()
    shadow_text(q, (W / 2, 296), "Where is this?", font("sans", 104, "ExtraBold"), (255, 255, 255))
    shadow_text(q, (W / 2, 374), "Answer before the timer hits 0", font("sans", 36, "SemiBold"), (255, 255, 255, 235))

    opts = canvas()
    _grid(opts, options)

    counts = []
    for k, n in enumerate(range(5, 0, -1)):
        c = canvas()
        cd = ImageDraw.Draw(c)
        r = 62
        cx, cy = win_r - 28 - r, WIN_Y + 28 + r  # top-right corner of the window
        cd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(20, 24, 38, 225), outline=(255, 255, 255, 60), width=6)
        cd.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * n / 5, fill=ACCENT + (255,), width=11)
        cd.text((cx, cy + 2), str(n), font=font("sans", 72, "ExtraBold"), fill=(255, 255, 255), anchor="mm")
        counts.append({"png": save(c, p(f"count{n}.png")), "start": COUNT_START + k, "end": COUNT_START + k + 1})

    rv = canvas()
    _grid(rv, options, correct)
    rd = ImageDraw.Draw(rv)
    f, lines = fit_lines(rd, f"It's {answer}!", lambda s: font("sans", s, "ExtraBold"), 1000, 1, 104, 52)
    shadow_text(rv, (W / 2, 296), lines[0], f, (255, 255, 255))
    shadow_text(rv, (W / 2, 374), "Did you get it? Comment your answer", font("sans", 36, "Bold"), ACCENT + (255,))
    if text["fact"]:  # a slim band along the bottom edge of the window, only after the reveal
        ff_, flines = fit_lines(rd, text["fact"], lambda s: font("sans", s, "SemiBold"), WIN_W - 110, 2, 38, 28)
        box_h = len(flines) * (ff_.size + 12) + 36
        y = win_b - 24 - box_h
        rd.rounded_rectangle((WIN_X + 24, y, win_r - 24, y + box_h), radius=26, fill=(15, 18, 30, 215))
        for i, line in enumerate(flines):
            rd.text((W / 2, y + 18 + (ff_.size + 12) * i + ff_.size / 2), line, font=ff_, fill=(255, 255, 255), anchor="mm")

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
    out = compose(clip_path, overlays, audio, p("reel.mp4"), DURATION, grade="eq=saturation=1.12:contrast=1.04",
                  window=(WIN_X, WIN_Y, WIN_W, WIN_H, p("mask.png")))
    # second cut with only the countdown ticks + reveal chime, for when Instagram's music plays underneath
    sfx = swap_audio(out, quiz_track(p("sfx.wav"), DURATION, ticks, REVEAL, seed=seed, music_on=False), p("reel_sfx.mp4"))
    music = {"video": sfx, "duration": DURATION, "audio_volume": 70, "video_volume": 100,
             "queries": ["feel good", "upbeat travel", "happy acoustic", "chill vibes", "summer"],
             "prefer": ["good", "explore", "vibe", "sunny", "way to go", "fly", "enjoy", "little things", "best day"],
             "avoid": ["piano", "peace", "om", "hymn"]}

    # generic tags only: a place hashtag would give the answer away in the caption
    tags = clean_hashtags([], ["GuessThePlace", "GeographyQuiz", "TravelQuiz", "Geography", "Travel", "Quiz", "WhereIsThis"], 7)
    caption = (f"{text['hook']}\n\n"
               f"A) {options[0]}\nB) {options[1]}\nC) {options[2]}\nD) {options[3]}\n\n"
               "Comment your answer before the reveal, then send this to the friend who thinks they know geography.\n"
               f"{'Follow @' + handle + ' for a new place every day.' if handle else 'Follow for a new place every day.'}\n\n"
               f"{' '.join(tags)}")
    return {"video": out, "caption": caption, "thumb_ms": 3000, "music": music, "used": [clip["id"], f"place:{answer}"],
            "summary": f"{answer} | options {options} | fact: {text['fact']}"}
