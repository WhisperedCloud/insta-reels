"""Frame-by-frame motion graphics for the Stoic Reels.

Every text element is a small sprite with its own start time: it eases in (fade + rise) and then stays.
Words of the quote arrive one by one at reading pace, the gold rule draws itself outward from the centre,
soft dust drifts up behind the text, and everything fades out together at the end so the Reel loops cleanly.
The background gets a slow push-in, a cinematic grade, light film grain and a vignette.
Frames are streamed straight into ffmpeg (no temp image files).
"""
import math
import random
import subprocess

from PIL import Image, ImageDraw, ImageFilter

from common import FFMPEG, FPS, H, W
from render import prepare_clip

PAD = 36  # room around each sprite for its soft shadow


def ease(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def text_sprite(text, fnt, fill, shadow=210, blur=10):
    """Text on a tight transparent canvas with a soft dark shadow (keeps it readable on any footage)."""
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, t, r, b = probe.textbbox((0, 0), text, font=fnt)
    w, h = r - l + PAD * 2, b - t + PAD * 2
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((PAD - l, PAD - t), text, font=fnt, fill=(0, 0, 0, shadow))
    img = sh.filter(ImageFilter.GaussianBlur(blur))
    ImageDraw.Draw(img).text((PAD - l, PAD - t), text, font=fnt, fill=fill)
    return img, (l, t)


def place_text(sprites, text, fnt, fill, cx, baseline_y, t0, dur=0.6, rise=22, **kw):
    """Add `text` centred on cx with its baseline at baseline_y."""
    img, (l, t) = text_sprite(text, fnt, fill, **kw)
    width = img.width - PAD * 2
    sprites.append({"img": img, "x": int(cx - width / 2 - PAD), "y": int(baseline_y - fnt.getmetrics()[0] + t - PAD),
                    "t0": t0, "dur": dur, "rise": rise})


def place_words(sprites, lines, fnt, fill, cx, first_baseline, line_h, t0, stagger=0.14, dur=0.55, rise=20):
    """Lay out wrapped lines centred on cx; each word gets its own start time. Returns when the last word lands."""
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    space = probe.textlength(" ", font=fnt)
    asc = fnt.getmetrics()[0]
    t = t0
    for i, line in enumerate(lines):
        words = line.split()
        widths = [probe.textlength(w, font=fnt) for w in words]
        x = cx - (sum(widths) + space * (len(words) - 1)) / 2
        base = first_baseline + i * line_h
        for word, ww in zip(words, widths):
            img, (l, top) = text_sprite(word, fnt, fill)
            sprites.append({"img": img, "x": int(x + l - PAD), "y": int(base - asc + top - PAD),
                            "t0": t, "dur": dur, "rise": rise})
            x += ww + space
            t += stagger * (1.6 if word[-1] in ",;:." else 1.0)  # tiny pause after punctuation
    return t + dur


def place_rule(sprites, cx, y, width, color, t0, dur=0.7, thickness=3):
    img = Image.new("RGBA", (width, thickness), color)
    sprites.append({"img": img, "x": int(cx - width / 2), "y": int(y), "t0": t0, "dur": dur, "rise": 0, "wipe": True})


def _put(frame, img, x, y):
    """alpha_composite that tolerates sprites hanging off the edge of the frame."""
    x, y = int(x), int(y)
    box = (max(0, -x), max(0, -y), min(img.width, W - x), min(img.height, H - y))
    if box[2] > box[0] and box[3] > box[1]:
        frame.alpha_composite(img.crop(box), (max(0, x), max(0, y)))


def _faded(img, alpha):
    if alpha >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    return out


def _dust(seed, n=22):
    rnd = random.Random(seed)
    motes = []
    for _ in range(n):
        r = rnd.randint(3, 9)
        dot = Image.new("RGBA", (r * 6, r * 6), (0, 0, 0, 0))
        ImageDraw.Draw(dot).ellipse((r * 2, r * 2, r * 4, r * 4), fill=(255, 236, 200, rnd.randint(70, 150)))
        motes.append({"img": dot.filter(ImageFilter.GaussianBlur(r * 0.7)), "x": rnd.uniform(0, W),
                      "y": rnd.uniform(0, H), "vy": rnd.uniform(14, 40), "sway": rnd.uniform(10, 34),
                      "ph": rnd.uniform(0, 6.28), "tw": rnd.uniform(0.3, 0.9)})
    return motes


def render(clip, static_base, sprites, audio, out, duration, seed=0, fade_out=0.6):
    """Composite: graded moving background + static dark base + animated sprites + audio -> out."""
    prepared = prepare_clip(clip, clip + ".prep.mp4", duration)
    n = int(round(duration * FPS))
    bg = (f"[0:v]scale={W * 2}:{H * 2}:flags=bilinear,"
          f"zoompan=z='1+0.08*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
          "eq=brightness=-0.07:contrast=1.08:saturation=0.5,colorbalance=rs=0.04:bs=-0.05:rh=0.03:bh=-0.03,"
          "noise=alls=7:allf=t,vignette=PI/4.2,format=yuv420p[bg]")
    ov = (f"[1:v]format=rgba,fade=t=out:st={duration - fade_out:.2f}:d={fade_out:.2f}:alpha=1[ov]")
    au = (f"[2:a]atrim=duration={duration:.2f},afade=t=in:st=0:d=0.3,"
          f"afade=t=out:st={duration - 0.8:.2f}:d=0.8,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]")
    cmd = [FFMPEG, "-hide_banner", "-y", "-loglevel", "error", "-i", prepared,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-i", audio, "-filter_complex", f"{bg};{ov};[bg][ov]overlay=0:0:shortest=1[v];{au}",
           "-map", "[v]", "-map", "[a]", "-t", f"{duration:.2f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100", "-movflags", "+faststart", out]
    err = open(out + ".log", "w")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)

    settled = static_base.copy()
    pending = sorted(sprites, key=lambda s: s["t0"])
    motes = _dust(seed)
    try:
        for f in range(n):
            t = f / FPS
            frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for m in motes:
                y = (m["y"] - m["vy"] * t) % (H + 80) - 40
                x = m["x"] + m["sway"] * math.sin(m["ph"] + t * 0.6)
                a = min(1.0, t / 1.5) * (0.55 + 0.45 * math.sin(m["ph"] + t * m["tw"]))
                _put(frame, _faded(m["img"], max(0.0, a)), int(x) % W - m["img"].width // 2, y)
            still = []
            for s in pending:
                p = (t - s["t0"]) / s["dur"]
                if p >= 1:
                    _put(settled, s["img"], s["x"], s["y"])
                else:
                    still.append(s)
            pending = still
            frame.alpha_composite(settled)
            for s in pending:
                p = (t - s["t0"]) / s["dur"]
                if p <= 0:
                    continue
                e = ease(p)
                if s.get("wipe"):
                    w = max(2, int(s["img"].width * e))
                    x0 = (s["img"].width - w) // 2
                    _put(frame, s["img"].crop((x0, 0, x0 + w, s["img"].height)), s["x"] + x0, s["y"])
                else:
                    _put(frame, _faded(s["img"], e), s["x"], s["y"] + (1 - e) * s["rise"])
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        if proc.wait(timeout=900) != 0:
            raise RuntimeError("ffmpeg failed: " + open(out + ".log").read()[-800:])
    except BrokenPipeError:
        proc.wait()
        raise RuntimeError("ffmpeg stopped early: " + open(out + ".log").read()[-800:])
    finally:
        err.close()
        if proc.poll() is None:
            proc.kill()
    return out
