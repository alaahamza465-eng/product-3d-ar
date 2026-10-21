# Leather surface detail ("what a real panel does"): the leather puffs between stitch lines, dips into the stitch
# channel and the holes, carries a fine crease line along the edges, and is never quite flat.
# Heights in mm, painted with numpy into float images over each part's UV domain (UV is in mm), saved as EXR.
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy, math, os
import numpy as np
from mathutils import Vector

PX = 8.0                      # pixels per mm
OUT = ROOT + '/maps'

def grid(u0, u1, v0, v1):
    w, h = int(math.ceil((u1 - u0) * PX)), int(math.ceil((v1 - v0) * PX))
    u = u0 + (np.arange(w) + .5) / PX; v = v0 + (np.arange(h) + .5) / PX
    U, V = np.meshgrid(u, v); return U, V

def sd_rrect(U, V, w, h, r, cu=0., cv=0.):
    qx = np.abs(U - cu) - (w / 2 - r); qz = np.abs(V - cv) - (h / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - r

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

def lowfreq(shape, cell_px, seed, amp):
    """smooth value noise: random lattice every cell_px pixels, smoothstep-interpolated"""
    rng = np.random.default_rng(seed); h, w = shape
    gh, gw = int(h / cell_px) + 3, int(w / cell_px) + 3
    g = rng.standard_normal((gh, gw)).astype(np.float32)
    y = np.arange(h) / cell_px; x = np.arange(w) / cell_px
    y0 = np.floor(y).astype(int); x0 = np.floor(x).astype(int); fy = y - y0; fx = x - x0
    fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
    a00 = g[y0][:, x0]; a01 = g[y0][:, x0 + 1]; a10 = g[y0 + 1][:, x0]; a11 = g[y0 + 1][:, x0 + 1]
    top = a00 + (a01 - a00) * fx[None, :]; bot = a10 + (a11 - a10) * fx[None, :]
    a = top + (bot - top) * fy[:, None]
    return a / (a.std() + 1e-6) * amp

def stamp(H, U0, V0, pts, depth, sigma):
    """add -depth·gaussian at UV points (mm) into H (grid origin U0, V0)"""
    rad = int(math.ceil(sigma * 3 * PX)); h, w = H.shape
    k = (np.arange(-rad, rad + 1) / PX)
    for (pu, pv) in pts:
        cx = (pu - U0) * PX - .5; cy = (pv - V0) * PX - .5; ix, iy = int(round(cx)), int(round(cy))
        x0, x1, y0, y1 = max(0, ix - rad), min(w, ix + rad + 1), max(0, iy - rad), min(h, iy + rad + 1)
        if x0 >= x1 or y0 >= y1: continue
        xs = (np.arange(x0, x1) - cx) / PX; ys = (np.arange(y0, y1) - cy) / PX
        H[y0:y1, x0:x1] -= depth * np.exp(-(xs[None, :] ** 2 + ys[:, None] ** 2) / sigma ** 2)

def thread_channels(H, U0, V0, holes, depth=.10, sigma=.42):
    """each stitch lies in a shallow channel between its two holes"""
    pts = []
    for a, b in holes:
        for k in range(1, 8): pts.append((a[0] + (b[0] - a[0]) * k / 8, a[1] + (b[1] - a[1]) * k / 8))
    stamp(H, U0, V0, pts, depth, sigma)

def save(name, H, u0, u1, v0, v1):
    os.makedirs(OUT, exist_ok=True)
    h, w = H.shape
    img = bpy.data.images.new('detail_' + name, w, h, float_buffer=True, is_data=True)
    px = np.zeros((h, w, 4), np.float32); px[..., 0] = H; px[..., 1] = H; px[..., 2] = H; px[..., 3] = 1
    img.pixels.foreach_set(px.ravel())
    path = f'{OUT}/{name}.exr'; img.filepath_raw = path; img.file_format = 'OPEN_EXR'; img.save()
    img.source = 'FILE'; img.filepath = path; img.reload(); img.colorspace_settings.is_data = True
    return dict(img=img, u0=u0, u1=u1, v0=v0, v1=v1)

def panel_map(name, w, h, r, stitch_inset, holes, seed, keep=None, crease=1.7, puff=.30, deboss=None):
    """flat parts with a rounded-rect outline, UV = local (x, z) centred at 0"""
    u0, u1, v0, v1 = -w / 2 - 1, w / 2 + 1, -h / 2 - 1, h / 2 + 1
    U, V = grid(u0, u1, v0, v1); d = -sd_rrect(U, V, w, h, r)           # distance inside the edge
    on_line = np.ones_like(d) if keep is None else keep(U, V)
    H = np.zeros_like(d, dtype=np.float32)
    H += puff * smoothstep(0, 11, d - stitch_inset) * on_line + puff * .55 * smoothstep(0, 14, d - 6) * (1 - on_line)
    H += .07 * np.sin(np.pi * np.clip(d / stitch_inset, 0, 1)) * on_line          # the margin outside the stitches rolls a little
    H -= .13 * np.exp(-((d - stitch_inset) / .75) ** 2) * on_line                  # the stitch channel
    H -= .085 * np.exp(-((d - crease) / .22) ** 2)                                # decorative edge crease
    H -= .05 * smoothstep(1.2, 0, d)                                              # edge burnished down
    H += lowfreq(H.shape, 40 * PX, seed, .045) + lowfreq(H.shape, 6 * PX, seed + 1, .012)
    stamp(H, u0 + .5 / PX, v0 + .5 / PX, [p for pr in holes for p in pr], .20, .34)
    thread_channels(H, u0 + .5 / PX, v0 + .5 / PX, holes)
    if deboss:
        H -= deboss['depth'] * sample_mask(deboss, U, V)
    return save(name, H, u0, u1, v0, v1)

def sample_mask(db, U, V):
    """a hot-stamped mark: mask image (rows top→bottom) placed with centre (cx, cz) and width w in mm"""
    M = db['mask']; mh, mw = M.shape; ppm = mw / db['w']; hh = mh / ppm
    col = (U - (db['cx'] - db['w'] / 2)) * ppm - .5; row = ((db['cz'] + hh / 2) - V) * ppm - .5
    c0 = np.floor(col).astype(int); r0 = np.floor(row).astype(int); fc = col - c0; fr = row - r0
    ok = (c0 >= 0) & (c0 < mw - 1) & (r0 >= 0) & (r0 < mh - 1)
    c0 = np.clip(c0, 0, mw - 2); r0 = np.clip(r0, 0, mh - 2)
    v = (M[r0, c0] * (1 - fc) + M[r0, c0 + 1] * fc) * (1 - fr) + (M[r0 + 1, c0] * (1 - fc) + M[r0 + 1, c0 + 1] * fc) * fr
    return np.where(ok, v, 0).astype(np.float32)

def strip_map(name, a_half, s_len, lines, holes, seed, crease=1.5, pillow=.18, edges=True, wrinkle=None):
    """swept parts, UV = (a across, s along); lines: [a positions of stitch rows]"""
    u0, u1, v0, v1 = -a_half - 1, a_half + 1, -1, s_len + 1
    U, V = grid(u0, u1, v0, v1); H = np.zeros_like(U, dtype=np.float32)
    H += pillow * (1 - np.clip(np.abs(U) / a_half, 0, 1) ** 2.2)
    for a in lines: H -= .12 * np.exp(-((U - a) / .7) ** 2)
    if edges:
        for sgn in (-1, 1): H -= .08 * np.exp(-((U - sgn * (a_half - crease)) / .22) ** 2)
    if wrinkle is not None: H += wrinkle(U, V)
    H += lowfreq(H.shape, 40 * PX, seed, .04) + lowfreq(H.shape, 6 * PX, seed + 1, .012)
    stamp(H, u0 + .5 / PX, v0 + .5 / PX, [p for pr in holes for p in pr], .20, .34)
    thread_channels(H, u0 + .5 / PX, v0 + .5 / PX, holes)
    return save(name, H, u0, u1, v0, v1)

# ---------------------------------------------------------------- stitch holes in UV
def holes_3d(items, length=3.8, slant=.42, sink=.2):
    from geo import stitch_frame
    out = []
    for k, (p, t, n) in enumerate(items):
        o, Rm, dl = stitch_frame(p, t, n, k, length, .5, slant, sink)
        e = Rm @ Vector((length / 2 * dl * .92, 0, 0)); c = o + Vector(n).normalized() * sink
        out.append((c - e, c + e))
    return out

def to_uv_slab(P): return (P.x, P.z)

def sweep_uv_fn(frames):
    Pn = np.array([tuple(f[0]) for f in frames]); S = [0.0]
    for i in range(1, len(frames)): S.append(S[-1] + (frames[i][0] - frames[i - 1][0]).length)
    def f(P):
        i = int(np.argmin(((Pn - np.array(tuple(P))) ** 2).sum(1))); p, t, W, N = frames[i]
        d = P - p; return (d.dot(W), S[i] + d.dot(t))
    return f, S[-1]
