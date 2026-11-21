"""Quality gate: a Reel is only posted if it is a valid 1080x1920 H.264/AAC file with audible, unclipped sound."""
import re
import subprocess

from common import FFMPEG


def _run(args):
    return subprocess.run([FFMPEG, "-hide_banner", *args], capture_output=True, text=True).stderr


def check(path: str, expected: float):
    head = _run(["-i", path])
    problems = []
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", head)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    v = re.search(r"Video: (\w+).*?, (\d{2,5})x(\d{2,5})", head)
    a = re.search(r"Audio: (\w+).*?(\d+) Hz, (\w+)", head)
    if abs(dur - expected) > 0.6:
        problems.append(f"duration {dur:.1f}s (expected {expected}s)")
    if not v or v.group(1) != "h264" or (int(v.group(2)), int(v.group(3))) != (1080, 1920):
        problems.append(f"video {v.groups() if v else None}")
    if not a or a.group(1) != "aac":
        problems.append(f"audio {a.groups() if a else None}")
    loud = _run(["-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    s = loud[loud.rfind("Summary:"):]
    i = re.search(r"I:\s+([-\d.]+) LUFS", s)
    tp = re.search(r"Peak:\s+([-\d.]+) dBFS", s)
    lufs = float(i.group(1)) if i else None
    peak = float(tp.group(1)) if tp else None
    if lufs is None or not (-18 <= lufs <= -11):
        problems.append(f"loudness {lufs} LUFS")
    if peak is not None and peak > -0.5:
        problems.append(f"peak {peak} dBFS")
    report = f"{dur:.1f}s, {v.group(2) + 'x' + v.group(3) if v else '?'}, {lufs} LUFS, peak {peak}"
    return not problems, report + ("" if not problems else "  ❌ " + "; ".join(problems))
