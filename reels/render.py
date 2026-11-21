"""Overlay drawing helpers and the ffmpeg compositor shared by both formats."""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

from common import FPS, H, W, ff, media_duration


def canvas():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_lines(draw, text, make_font, max_w, max_lines, start, smallest):
    """Largest font size (from `start` down) at which `text` wraps into ≤ max_lines."""
    size = start
    while size > smallest:
        f = make_font(size)
        lines = wrap(draw, text, f, max_w)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        size -= 4
    f = make_font(smallest)
    return f, wrap(draw, text, f, max_w)


def shadow_text(img, xy, text, fnt, fill, anchor="mm", blur=10, strength=200):
    sh = canvas()
    ImageDraw.Draw(sh).text(xy, text, font=fnt, fill=(0, 0, 0, strength), anchor=anchor)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).text(xy, text, font=fnt, fill=fill, anchor=anchor)


def gradient(y0, y1, alpha0, alpha1, color=(0, 0, 0)):
    img = canvas()
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0)
        d.line([(0, y), (W, y)], fill=color + (int(alpha0 + (alpha1 - alpha0) * t),))
    return img


def save(img, path):
    img.save(path)
    return path


def prepare_clip(clip, out, duration):
    """Cut the source down to a clean 1080x1920, 30 fps, silent clip of exactly `duration` seconds
    (looping it if it is shorter). Doing this first keeps the final composite fast on CI."""
    have = media_duration(clip)
    loops = max(0, math.ceil(duration / have) - 1) if have > 0 else 0
    pre = ["-stream_loop", str(loops)] if loops else []
    ff([*pre, "-t", f"{duration + 0.5:.2f}", "-i", clip, "-an",
        "-vf", f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1",
        "-t", f"{duration:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", out])
    return out


def compose(clip, overlays, audio, out, duration, grade=""):
    """Prepared clip + colour grade, then PNG overlays (each with its own start/end/fade), mixed with
    `audio` loudness-normalised to -14 LUFS (Instagram's playback target)."""
    prepared = prepare_clip(clip, clip + ".prep.mp4", duration)
    inputs = ["-i", prepared]
    for o in overlays:
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.2f}", "-i", o["png"]]
    inputs += ["-i", audio]
    chain = [f"[0:v]{grade + ',' if grade else ''}format=yuv420p,setpts=PTS-STARTPTS[v0]"]
    last = "v0"
    for i, o in enumerate(overlays, start=1):
        start, end, fade = o.get("start", 0.0), o.get("end", duration), o.get("fade", 0.0)
        f = f"[{i}:v]format=rgba"
        if fade:
            f += f",fade=t=in:st={start:.2f}:d={fade:.2f}:alpha=1"
        chain.append(f + f"[o{i}]")
        chain.append(f"[{last}][o{i}]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'[v{i}]")
        last = f"v{i}"
    a = len(overlays) + 1
    chain.append(f"[{a}:a]atrim=duration={duration:.2f},afade=t=in:st=0:d=0.15,"
                 f"afade=t=out:st={duration - 0.5:.2f}:d=0.5,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]")
    ff([*inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "[a]",
        "-t", f"{duration:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100",
        "-movflags", "+faststart", out])
    return out


def swap_audio(video, wav, out, normalise=True):
    """Same picture, different soundtrack (no re-encode of the video)."""
    af = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100"] if normalise else ["-ar", "44100"]
    ff(["-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", *af, "-c:a", "aac", "-b:a", "192k",
        "-ac", "2", "-shortest", "-movflags", "+faststart", out])
    return out


def cleanup(paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass
