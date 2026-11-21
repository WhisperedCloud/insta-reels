"""Original soundtracks synthesised in numpy (no licensing issues, every Reel slightly different)."""
import wave

import numpy as np

SR = 44100


def _env(n, attack, release):
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def _note(freq, dur, decay=4.0, harmonics=((1, 1.0), (2, 0.35), (3, 0.12))):
    t = np.arange(int(dur * SR)) / SR
    s = sum(a * np.sin(2 * np.pi * freq * h * t) for h, a in harmonics)
    return s * np.exp(-decay * t)


def _add(buf, sig, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i]


def _echo(x, delay=0.28, fb=0.35, taps=4):
    out = x.copy()
    d = int(delay * SR)
    for k in range(1, taps + 1):
        out[d * k:] += x[: len(x) - d * k] * (fb ** k)
    return out


def _write(path, left, right):
    st = np.stack([left, right], axis=1)
    st /= max(1e-9, np.abs(st).max()) / 0.8
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    return path


def quiz_track(path, duration, ticks, reveal_at, seed=0, music_on=True):
    """Light marimba arpeggio + clock ticks during the countdown + a bright 'ding' at the reveal."""
    rnd = np.random.default_rng(seed)
    n = int(duration * SR)
    music = np.zeros(n)
    roots = [[261.63, 329.63, 392.0, 523.25], [220.0, 261.63, 329.63, 440.0],
             [174.61, 220.0, 261.63, 349.23], [196.0, 246.94, 293.66, 392.0]]
    rnd.shuffle(roots)
    beat = 60 / 112 / 2  # eighth notes at 112 bpm
    t, i = 0.0, 0
    while t < duration:
        chord = roots[int(t // (beat * 8)) % len(roots)]
        f = chord[[0, 2, 1, 3, 2, 1, 3, 2][i % 8]]
        _add(music, 0.22 * _note(f * 2, 0.6, decay=7), t)
        if i % 8 == 0:
            _add(music, 0.35 * _note(chord[0] / 2, beat * 8, decay=0.9, harmonics=((1, 1), (2, 0.2))), t)
        t += beat
        i += 1
    fx = np.zeros(n)
    for k, at in enumerate(ticks):
        _add(fx, 0.55 * _note(1900 if k < len(ticks) - 1 else 2300, 0.08, decay=60, harmonics=((1, 1),)), at)
    for f, a in ((1318.5, 0.5), (1975.5, 0.35), (2637.0, 0.2)):
        _add(fx, a * _note(f, 1.6, decay=2.8, harmonics=((1, 1),)), reveal_at)
    music *= _env(n, 0.05, 0.6)
    music = _echo(music) * (1.0 if music_on else 0.0)
    return _write(path, music * 0.8 + fx, music * 0.8 + np.roll(fx, 40))


def stoic_track(path, duration, seed=0):
    """Slow cinematic drone: low minor chord swelling in, soft filtered air, sparse piano notes."""
    rnd = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n) / SR
    root = rnd.choice([55.0, 58.27, 61.74, 65.41])  # A1, Bb1, B1, C2
    ratios = [1, 1.5, 2, 2.378, 3]                 # root, fifth, octave, minor third, fifth
    pad_l = np.zeros(n)
    pad_r = np.zeros(n)
    for k, r in enumerate(ratios):
        f = root * r
        lfo = 1 + 0.25 * np.sin(2 * np.pi * (0.07 + 0.03 * k) * t + k)
        pad_l += (0.5 / (k + 1)) * lfo * np.sin(2 * np.pi * f * t)
        pad_r += (0.5 / (k + 1)) * lfo * np.sin(2 * np.pi * f * 1.003 * t + 0.4)
        # same chord two octaves up: phone speakers cannot reproduce the low layer on their own
        pad_l += (0.34 / (k + 1)) * lfo * np.sin(2 * np.pi * f * 4 * t + 1.1)
        pad_r += (0.34 / (k + 1)) * lfo * np.sin(2 * np.pi * f * 4.01 * t + 0.2)
    air = np.convolve(rnd.standard_normal(n), np.ones(60) / 60, mode="same") * 0.35
    env = _env(n, 2.5, 1.5)
    piano = np.zeros(n)
    scale = [root * 8 * r for r in (1, 1.189, 1.335, 1.498, 1.782, 2)]
    at = 1.2
    while at < duration - 2:
        _add(piano, 0.30 * _note(rnd.choice(scale), 3.0, decay=1.4), at)
        at += rnd.uniform(1.6, 2.6)
    piano = _echo(piano, delay=0.42, fb=0.45, taps=5)
    return _write(path, (pad_l + air) * env + piano, (pad_r + np.roll(air, 300)) * env + np.roll(piano, 200))


def quiet_track(path, duration, seed=0):
    """Barely audible air, used as the video's own sound when an Instagram library track carries the music."""
    rnd = np.random.default_rng(seed)
    n = int(duration * SR)
    air = np.convolve(rnd.standard_normal(n), np.ones(80) / 80, mode="same")
    st = np.stack([air, np.roll(air, 300)], axis=1) * 0.004 / max(1e-9, np.abs(air).max())
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    return path
