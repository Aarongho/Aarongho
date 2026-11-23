"""Synthesize horror SFX + a drone music bed for candle_guard (numpy only)."""
import json, os, sys, wave
import numpy as np

SR = 48000
ROOT = sys.argv[1]
rng = np.random.default_rng(7)


def t(d):
    return np.arange(int(d * SR)) / SR


def env(n, a=0.005, r=0.2, hold=0.0):
    x = np.arange(n) / SR
    e = np.minimum(1, x / max(a, 1e-4))
    rel = np.clip((x - a - hold) / r, 0, None)
    return e * np.exp(-rel * 5)


def lp(x, k):
    """one-pole low pass, k in (0,1): smaller = darker"""
    y = np.zeros_like(x); s = 0.0
    for i in range(len(x)):
        s += k * (x[i] - s); y[i] = s
    return y


def lp_fast(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def hp_fast(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (cutoff / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X, len(x))


def bp(x, lo, hi):
    return hp_fast(lp_fast(x, hi), lo)


def norm(x, p=0.9):
    return x / max(np.abs(x).max(), 1e-9) * p


def save(name, x):
    x = np.clip(norm(x), -1, 1)
    fade = min(len(x), int(0.01 * SR))
    x[-fade:] *= np.linspace(1, 0, fade)
    with wave.open(os.path.join(ROOT, "sfx", name + ".wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def noise(d):
    return rng.standard_normal(int(d * SR))


# hiss: a flame snuffed (fssst): bright noise, quick swell, long tail
d = 0.75; x = bp(noise(d), 2500, 9000); tt = t(d)
x *= np.minimum(1, tt / 0.04) * np.exp(-np.clip(tt - 0.05, 0, None) * 5)
save("hiss", x)

# scratch: match strike (short gritty burst) + flare whoosh
d = 0.55; tt = t(d)
g = bp(noise(d), 1500, 7000) * (rng.random(len(tt)) < 0.35)
g *= np.exp(-tt * 18)
fl = lp_fast(noise(d), 1200) * np.minimum(1, np.clip(tt - 0.05, 0, None) / 0.05) * np.exp(-np.clip(tt - 0.1, 0, None) * 6)
save("scratch", g + 0.6 * fl)

# puff: small blow-out
d = 0.35; tt = t(d)
save("puff", lp_fast(noise(d), 900) * np.minimum(1, tt / 0.01) * np.exp(-tt * 14))

# ignite: whoomp of a flame catching
d = 0.8; tt = t(d)
x = lp_fast(noise(d), 1500) * np.minimum(1, tt / 0.06) * np.exp(-np.clip(tt - 0.08, 0, None) * 5)
x += 0.4 * np.sin(2 * np.pi * (90 + 40 * tt) * tt) * np.exp(-tt * 6)
save("ignite", x)

# sting: horror hit (low boom + dissonant high cluster + noise)
d = 2.4; tt = t(d)
boom = np.sin(2 * np.pi * (55 * tt - 10 * tt ** 2)) * np.exp(-tt * 2.2)
cl = sum(np.sin(2 * np.pi * f * tt + rng.uniform(0, 6)) for f in (1240, 1316, 1397, 1480)) * 0.12 * np.exp(-tt * 1.6)
cl *= np.minimum(1, tt / 0.01)
nz = bp(noise(d), 300, 4000) * np.exp(-tt * 6) * 0.5
save("sting", boom + cl + nz)

# drone: dark swell (low detuned saws filtered)
d = 4.0; tt = t(d)
s = sum(np.sin(2 * np.pi * f * tt) * a for f, a in ((41.2, 1), (41.7, 0.8), (61.9, 0.5), (82.4, 0.3), (87.3, 0.25)))
s += 0.3 * lp_fast(noise(d), 200)
s *= np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 1.5
save("drone", s)

# heartbeat: two thumps x3
d = 2.6; tt = t(d); x = np.zeros_like(tt)
for b in range(3):
    for off, a in ((0.0, 1.0), (0.22, 0.7)):
        t0 = b * 0.85 + off
        m = tt >= t0; u = tt[m] - t0
        x[m] += a * np.sin(2 * np.pi * (60 - 20 * u) * u) * np.exp(-u * 18)
save("heartbeat", x)

# whisper: breathy formant noise "eddieee"
d = 1.2; tt = t(d)
x = bp(noise(d), 1800, 5500) * 0.6 + bp(noise(d), 600, 1200) * 0.4
x *= (0.5 + 0.5 * np.sin(2 * np.pi * 2.2 * tt + 1)) * np.minimum(1, tt / 0.1) * np.exp(-np.clip(tt - 0.6, 0, None) * 4)
save("whisper", x)

# breath: slow cold exhale
d = 1.6; tt = t(d)
x = bp(noise(d), 400, 2500) * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 2
save("breath", x)

# bell: midnight bell (inharmonic partials)
d = 3.0; tt = t(d)
x = sum(np.sin(2 * np.pi * f * tt) * a * np.exp(-tt * k) for f, a, k in
        ((220, 1, 1.2), (440 * 1.19, 0.5, 1.8), (220 * 2.76, 0.35, 2.5), (220 * 5.4, 0.2, 4)))
save("bell", x * np.minimum(1, tt / 0.003))

# bark: one dog bark then whimper fade
d = 0.9; tt = t(d)
f = 420 - 200 * np.clip(tt / 0.15, 0, 1)
b = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.6 * bp(noise(d), 500, 2500)) * np.exp(-tt * 14)
wh = np.sin(2 * np.pi * np.cumsum(900 - 300 * tt) / SR) * 0.3 * np.exp(-np.abs(tt - 0.6) * 12)
save("bark", b + wh)

# rattle: matchbox shake
d = 0.5; tt = t(d)
x = bp(noise(d), 2000, 8000) * (np.sin(2 * np.pi * 14 * tt) > 0.6) * np.exp(-tt * 3)
save("rattle", x)

# buzz: electric flicker
d = 0.4; tt = t(d)
x = (np.sign(np.sin(2 * np.pi * 120 * tt)) * 0.4 + bp(noise(d), 1000, 6000) * 0.3) * (rng.random(len(tt)) < 0.8)
x *= (np.sin(2 * np.pi * 18 * tt) > -0.2) * np.exp(-np.clip(tt - 0.3, 0, None) * 30)
save("buzz", x)

# sizzle: footprint burning into snow
d = 0.5; tt = t(d)
save("sizzle", bp(noise(d), 3000, 10000) * np.minimum(1, tt / 0.02) * np.exp(-tt * 6))

# screech: creature shriek (detuned rising tones + noise)
d = 1.0; tt = t(d)
f = 700 + 900 * tt
x = sum(np.sin(2 * np.pi * np.cumsum(f * k) / SR) for k in (1, 1.06, 1.5)) + bp(noise(d), 2000, 7000)
save("screech", x * np.minimum(1, tt / 0.05) * np.exp(-np.clip(tt - 0.4, 0, None) * 5))

# tap: knuckle tap on a shoulder
d = 0.25; tt = t(d)
save("tap", (np.sin(2 * np.pi * 180 * tt) + 0.5 * lp_fast(noise(d), 2500)) * np.exp(-tt * 40))

pack = json.load(open(os.path.join(ROOT, "sfx", "pack.json")))
pack.update({"hiss": {"gain": -1, "lead": 0.04}, "scratch": {"gain": -2}, "puff": {"gain": -4}, "ignite": {"gain": -2},
             "sting": {"gain": 1}, "drone": {"gain": -3, "lead": 0.4}, "heartbeat": {"gain": 0}, "whisper": {"gain": -5, "lead": 0.1},
             "breath": {"gain": -5, "lead": 0.2}, "bell": {"gain": -3}, "bark": {"gain": -4}, "rattle": {"gain": -5},
             "buzz": {"gain": -7}, "sizzle": {"gain": -8}, "screech": {"gain": -4}, "tap": {"gain": -2}})
json.dump(pack, open(os.path.join(ROOT, "sfx", "pack.json"), "w"), indent=2)

# music bed: 100s dark ambient (drone + slow pulse + high shimmer), will be sped 1.5x by finish
d = 150.0; tt = t(d)
bed = sum(np.sin(2 * np.pi * f * tt + p) * a for f, a, p in ((36.7, 1, 0), (37.1, 0.8, 1), (55.0, 0.45, 2), (73.4, 0.25, 3)))
bed *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.07 * tt)
pulse = np.zeros_like(tt)
for b0 in np.arange(0, d, 1.6):
    m = (tt >= b0) & (tt < b0 + 0.5); u = tt[m] - b0
    pulse[m] += np.sin(2 * np.pi * 48 * u) * np.exp(-u * 9)
shim = sum(np.sin(2 * np.pi * f * tt + p) for f, p in ((1174.7, 0), (1244.5, 1))) * 0.04 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * tt))
wind = lp_fast(rng.standard_normal(len(tt)), 400) * 0.25 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.03 * tt))
m = norm(bed * 0.8 + pulse * 0.6 + shim + wind, 0.8)
os.makedirs(os.path.join(ROOT, "music"), exist_ok=True)
with wave.open(os.path.join(ROOT, "music", "horror_bed.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((m * 32767).astype(np.int16).tobytes())
print("ok")
