"""Score + foley + mix for the HAMZA bag film. Reads events.json (window.EV) and the timeline numbers; writes out/mix.wav.
Score: 90 BPM, A minor (Am9 – Fmaj7 – C – G/B), resolving to A major on the card. Tuned mallets (marimba, vibraphone,
glockenspiel), a round bass, a soft kick and a shaker, all synthesised (no sample download). Foley is the material:
brass ring, leather creak and thock, zip ratchet, swooshes, label ticks, a fine hiss for the glint."""
import json, os, sys
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                     # sfx.py (synth helpers) sits next to this file
import sfx
from sfx import SR, t_, env_exp, bp, lp, hp, noise, norm, add

rng = np.random.default_rng(11)
EVJ = json.load(open(os.path.join(HERE, 'events2.json')))
DUR = EVJ['dur']; EV = EVJ['ev']
BEAT = 60 / 90; BAR = 4 * BEAT
N = int((DUR + .2) * SR)
mus = np.zeros((N, 2)); fol = np.zeros((N, 2)); amb = np.zeros((N, 2))

def mtof(m): return 440 * 2 ** ((m - 69) / 12)

# ---------- instruments ----------
def marimba(m, v=1.0, d=1.2):
    f = mtof(m); tt = t_(d); tau = .32 * (440 / f) ** .35
    x = np.sin(2 * np.pi * f * tt) * env_exp(d, tau) + .28 * np.sin(2 * np.pi * f * 3.93 * tt) * env_exp(d, tau * .22) + .08 * np.sin(2 * np.pi * f * 9.2 * tt) * env_exp(d, tau * .08)
    x += hp(noise(d), 1500) * env_exp(d, .002) * .15        # mallet
    return x * v

def vibes(m, v=1.0, d=3.0):
    f = mtof(m); tt = t_(d); trem = 1 + .22 * np.sin(2 * np.pi * 5.2 * tt)
    att = np.minimum(1, tt / .012)
    x = (np.sin(2 * np.pi * f * tt) + .18 * np.sin(2 * np.pi * f * 4.0 * tt) * env_exp(d, .25) + .05 * np.sin(2 * np.pi * f * 10.0 * tt) * env_exp(d, .08))
    return x * env_exp(d, 1.6) * att * trem * v

def glock(m, v=1.0, d=1.6):
    f = mtof(m); tt = t_(d)
    x = np.sin(2 * np.pi * f * tt) * env_exp(d, .7) + .35 * np.sin(2 * np.pi * f * 2.76 * tt) * env_exp(d, .25) + .15 * np.sin(2 * np.pi * f * 5.4 * tt) * env_exp(d, .1)
    return x * np.minimum(1, tt / .002) * v

def bass(m, d, v=1.0):
    f = mtof(m); tt = t_(d)
    x = np.sin(2 * np.pi * f * tt) + .45 * np.sin(4 * np.pi * f * tt) + .2 * np.sin(6 * np.pi * f * tt)
    e = np.minimum(1, tt / .01) * np.minimum(1, (d - tt) / .08) * (.75 + .25 * np.exp(-tt / .25))
    return lp(x * e, 900) * v

def kick(v=1.0):
    d = .4; tt = t_(d); f = 46 + 70 * np.exp(-tt / .03)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(d, .13) + hp(noise(d), 2500) * env_exp(d, .003) * .2) * v

def shaker(v=1.0):
    d = .09; tt = t_(d)
    return bp(noise(d), 5000, 11000) * np.sin(np.pi * tt / d) ** 2 * v

# ---------- score ----------
CH = {  # chord tones (MIDI) per chord: arpeggio notes, pad notes, bass root
    'Am9':   ([57, 60, 64, 67, 71], [60, 64, 67, 71], 45),
    'Fmaj7': ([53, 57, 60, 64, 67], [57, 60, 64, 67], 41),
    'C':     ([55, 60, 64, 67, 72], [60, 64, 67, 72], 48),
    'G/B':   ([55, 59, 62, 67, 71], [59, 62, 67, 71], 47),
    'A':     ([57, 61, 64, 68, 71], [61, 64, 68, 71], 45),
}
PROG = ['Am9', 'Fmaj7', 'C', 'G/B', 'Am9', 'Fmaj7', 'C', 'G/B', 'Fmaj7', 'A', 'A']
SIL = [(14.42, 14.667), (22.45, 22.667)]
def silent(t): return any(a - .02 <= t < b for a, b in SIL)

def put(buf, x, t, g, pan=0.0):
    if t < 0 or t >= DUR or silent(t): return
    add(buf, x, t, g, pan)

def section(t):
    return ('drive' if t < 4.0 else 'full' if t < 8.0 else 'drive' if t < 10.667 else 'full' if t < 22.667
            else 'gap' if t < 25.333 else 'card')

PAT = [0, 2, 1, 3, 2, 4, 3, 1]   # eighth-note arpeggio walk through the chord
for bar, name in enumerate(PROG):
    t0 = bar * BAR; arp, pad, root = CH[name]
    for k in range(8):
        t = t0 + k * BEAT / 2; sec = section(t)
        if sec == 'gap' and k not in (0, 3, 6): continue
        if sec == 'card' and k % 2: continue
        n = arp[PAT[k] % len(arp)] + (12 if sec in ('full', 'card') and k in (5, 7) else 0)
        put(mus, marimba(n, .9 if k % 2 == 0 else .62), t, .2 if sec == 'card' else .32, -.25 + .5 * ((k * 37) % 7) / 6)
    for k in range(4):
        t = t0 + k * BEAT; sec = section(t)
        if sec in ('drive', 'full'):
            put(mus, bass(root if k != 3 else root + 7, BEAT * .9), t, .3)
            if k in (0, 2): put(mus, kick(), t, .34)
            put(mus, shaker(), t + BEAT / 2, .05, .3)
    sec0 = section(t0 + .01)
    if sec0 in ('full', 'gap') or (sec0 == 'drive' and t0 >= 8):
        for i, n in enumerate(pad): put(mus, vibes(n, 1, BAR + 1.2), t0 + .01 * i, .085, -.4 + .27 * i)
    if sec0 == 'gap':
        put(mus, glock(arp[-1] + 12, .7, 2.4), t0 + BEAT * 2, .07, .35)
# the end card resolves: A major pad, long bass, two glock notes
tc = 25.333; arp, pad, root = CH['A']
for i, n in enumerate(pad): put(mus, vibes(n, 1, 5.0), tc + .015 * i, .11, -.45 + .3 * i)
put(mus, bass(root, 3.2), tc, .42); put(mus, glock(81, .8, 2.6), tc + .02, .08, .2); put(mus, glock(88, .6, 2.6), tc + BEAT, .05, -.2)
# accents on the big moments
for t in (0.0, 4.0, 14.667, 25.333): add(mus, kick(1.2), t, .5); add(mus, bass(45, .9), t, .34)
# a glockenspiel sparkle as each thing lands inside
for i, e in enumerate([e for e in EV if e['type'] in ('tick', 'slide')][:6]):
    put(mus, glock([81, 84, 88, 86, 91, 93][i], .7, 2.0), e['t'], .05, -.4 + .16 * i)

# ---------- foley ----------
def ring_j(v=1.0):
    d = 1.2; tt = t_(d); out = np.zeros(len(tt))
    for k, (dt, a) in enumerate([(0, 1), (.085, .55), (.19, .35), (.33, .2)]):
        s = int(dt * SR); n = len(tt) - s; tk = tt[:n]
        x = sum(b * np.sin(2 * np.pi * f * (1 + .01 * k) * tk) * np.exp(-tk / tau) for f, b, tau in [(2210, 1, .35), (3180, .7, .22), (4630, .45, .15), (6120, .3, .08)])
        x += hp(noise(n / SR), 3000)[:n] * np.exp(-tk / .002) * .5
        out[s:] += x * a
    return norm(out) * v

def leather_creak(v=1.0):
    d = .55; tt = t_(d); f0 = 38
    saw = 2 * ((tt * f0 * (1 + .25 * np.sin(2 * np.pi * 3 * tt))) % 1) - 1
    stick = (np.abs(np.sin(2 * np.pi * 17 * tt)) ** 4)
    x = bp(saw, 300, 2200) * stick * np.sin(np.pi * tt / d) + bp(noise(d), 600, 2500) * .15 * np.sin(np.pi * tt / d)
    return norm(x) * v

def thock(v=1.0):
    d = .45; tt = t_(d)
    body = np.sin(2 * np.pi * 92 * tt * (1 - .25 * tt)) * env_exp(d, .06)
    slap = bp(noise(d), 700, 2600) * env_exp(d, .012)
    air = lp(noise(d), 350) * env_exp(d, .05)
    return norm(body * .9 + slap * .7 + air * .4) * v

def zip_r(d, v=1.0):
    n = int(d * SR); out = np.zeros(n); tt = np.arange(n) / SR
    rate = 85; tk = 0.0
    while tk < d:
        s = int(tk * SR); m = min(n - s, int(.012 * SR))
        if m <= 0: break
        c = hp(noise(.012), 2500)[:m] * np.exp(-np.arange(m) / SR / .0015) + np.sin(2 * np.pi * (3600 + 400 * rng.random()) * np.arange(m) / SR) * np.exp(-np.arange(m) / SR / .003) * .3
        out[s:s + m] += c * (.7 + .3 * rng.random())
        tk += 1 / rate * (.85 + .3 * rng.random())
    e = np.minimum(1, tt / .06) * np.minimum(1, (d - tt) / .12)
    return norm(out * e + bp(noise(d), 1500, 6000) * e * .08) * v

def tick(v=1.0):
    d = .04; tt = t_(d)
    return norm(hp(noise(d), 4000) * env_exp(d, .0015) + np.sin(2 * np.pi * 5200 * tt) * env_exp(d, .004) * .4) * v

def hiss(d, v=1.0):
    tt = t_(d); return norm(bp(noise(d), 5000, 9500)) * np.sin(np.pi * tt / d) ** 1.5 * v

for e in EV:
    t, ty = e['t'], e['type']; g = e.get('g', 1.0)
    if ty == 'ring': add(fol, ring_j(), t + .01, .5, -.45)
    elif ty == 'creak': add(fol, leather_creak(), t, .35, .1)
    elif ty == 'thock': add(fol, thock(), t, 1.25 * g, .05)
    elif ty == 'zip': add(fol, zip_r(e['d']), t, .32, .15 if e['d'] > 1 else -.1)
    elif ty == 'swoosh': add(fol, sfx.whoosh(.55, 1), t - .1, .32 * g, .3)
    elif ty == 'ringtick': add(fol, ring_j() * .4, t, .25, -.5)
    elif ty == 'tick': add(fol, tick(), t, .18, .55)
    elif ty == 'dive': w = sfx.whoosh(e['d'], 1); add(fol, w + lp(noise(e['d']), 500)[:len(w)] * .3 * np.sin(np.pi * t_(e['d']) / e['d'])[:len(w)], t, .34, 0)
    elif ty == 'swooshR': w = sfx.whoosh(.45, 1)[::-1]; add(fol, w, t - .3, .3 * g, -.2)
    elif ty == 'hit': add(fol, thock(.6), t, .5)
    elif ty == 'hiss': add(fol, hiss(e['d']), t, .1, .1)
    elif ty == 'slide':
        d = .32; tt = t_(d); x = bp(noise(d), 1800, 7000) * np.minimum(1, tt / .02) * np.exp(-tt / .12)
        add(fol, norm(x) * .8 + thock(.4)[:len(x)] * .5, t - .25, .22 * g, .1)

# ---------- ambience: room tone everywhere, a filtered air bed inside the gap ----------
room = hp(lp(sfx.brown(DUR + .2), 260), 45) * .03 + hp(noise(DUR + .2), 6000) * .004
amb[:len(room), 0] += room[:N]; amb[:len(room), 1] += np.roll(room, 997)[:N]
gap = lp(noise(8.0), 900) * np.sin(np.pi * t_(8.0) / 8.0) ** 2
add(amb, norm(gap), 14.667, .03)

# ---------- mix ----------
def comp2(x, **k): return np.stack([sfx.compress(x[:, c], **k) for c in range(2)], 1)
mus = comp2(mus, thr=.35, ratio=2.5)
# duck the music a little under the big foley hits
duck = np.ones(N)
for e in EV:
    if e['type'] in ('thock', 'zip', 'dive', 'hit'):
        s = int(e['t'] * SR); d = int(.5 * SR); duck[s:s + d] = np.minimum(duck[s:s + d], np.linspace(.6, 1, len(duck[s:s + d])))
mix = mus * duck[:, None] + fol + amb
mix = np.stack([hp(mix[:, c], 32) for c in range(2)], 1)
fade = np.ones(N); fs = int((DUR - 1.0) * SR); fade[fs:] = np.linspace(1, 0, N - fs) ** 1.5
mix *= fade[:, None]
mix = np.stack([sfx.limit(mix[:, c], .92) for c in range(2)], 1)
os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
sf.write(os.path.join(HERE, 'out', 'mix2.wav'), mix.astype(np.float32), SR, subtype='PCM_24')
# band check: low end vs the rest
from numpy.fft import rfft, rfftfreq
F = np.abs(rfft(mix[:, 0])) ** 2; fr = rfftfreq(N, 1 / SR)
lo = F[(fr > 20) & (fr < 120)].sum(); rest = F[(fr >= 120) & (fr < 16000)].sum()
print(f'mix2.wav {DUR:.1f}s  peak {np.abs(mix).max():.2f}  low(20–120 Hz) vs rest: {10 * np.log10(lo / rest):+.1f} dB')
