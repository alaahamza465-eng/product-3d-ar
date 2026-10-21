# The leather clutch as a Cycles scene. 1 unit = 1 mm, Z up, the bag's front faces -Y, floor at z = 0.
# Sizes follow the first film (estimates from reference photos); every part is built so it could exist:
# rounded painted edges, grain outside / flesh inside, sunk saddle stitches, a real zip chain, a snap hook.
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy, bmesh, math, sys
from mathutils import Vector, Matrix
sys.path.insert(0, ROOT)
from geo import *
from geo import _capsule_template, _jit
import mats as MT
import numpy as np

BW, BH, BD, BR, BT = 210., 120., 50., 16., 2.6          # body outer size, corner radius, leather thickness
INNER = BD - 2 * BT                                      # band depth between the panels (44.8)
PK = dict(w=150., h=82., r=6., x=4., z=56., t=2.4, d=14.)  # front pocket: face + U gusset, 14 deep
FLAP = dict(w=154., t=3.0, x=4., r=7.)
ZIP = dict(x0=-87., x1=87., gap=10.4, pitch=1.5)
SL_PARK = 83.5
PITCH = 4.3                                              # stitch pitch
HDR = ROOT + '/hdri/photo_studio_loft_hall_2k.hdr'
R = {}                                                   # registry of everything anim.py needs

def smooth01(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- stitches on flat outlines
def outline_stitches(outline2d, inset, keep, to3d, normal, step=PITCH):
    """stitch items along an outline inset by `inset`; keep(x, y) filters (open edges); to3d maps 2D → local 3D"""
    pts, _ = resample(offset_poly(outline2d, -inset), step, closed=True)
    out = []
    for p, t in pts:
        if keep(p.x, p.y): out.append((to3d(p.x, p.y), Vector((t.x, 0, t.y)), normal))
    return out

def line_stitches(a, b, step, normal):
    a, b = Vector(a), Vector(b); L = (b - a).length; n = max(1, int(L / step)); t = (b - a).normalized()
    return [(a + (b - a) * (i / n), t, Vector(normal)) for i in range(n + 1)]

# ---------------------------------------------------------------- panels
def panels(M, G):
    out = rrect_pts(BW, BH, BR, n=16)
    for side, k, y in (('front', 'front', -BD / 2 + BT / 2), ('back', 'back', BD / 2 - BT / 2)):
        p = slab(side + '_panel', out, BT, 1.0, [M['L'], M['E'], M['F']], parent=G[k], res=5); weighted(p)
        p.location = (0, y, BH / 2)
        if side == 'back': p.rotation_euler.z = math.pi
        items = outline_stitches(out, 4.4, lambda x, z: True, lambda x, z: Vector((x, -BT / 2 + .02, z)), Vector((0, -1, 0)))
        stitch_row(side + '_st', items, [M['TH']], parent=p); R['items_' + side] = items
        items = outline_stitches(out, 4.4, lambda x, z: True, lambda x, z: Vector((x, BT / 2 - .02, z)), Vector((0, 1, 0)))
        stitch_row(side + '_st_in', items, [M['TH']], parent=p)
        R[side + '_panel'] = p

# ---------------------------------------------------------------- band (U gusset), zip strips, zipper
def band(M, G):
    P = densify(u_path(BW - BT, BH - BT, BR - BT / 2, cz=BH / 2, n=14), 6)
    fr = frames_for(P, fixedW=(0, 1, 0))
    prof = support(rr_profile(INNER - .2, BT, 1.0, n=4))
    pm = prof_mat(INNER - .2, 1.0)(prof)
    b = sweep2('band', fr, lambda i: prof, mats=[M['L'], M['E'], M['F']], parent=G['band'], mat_fn=pm, cap_mat=1)
    R['band'] = b; R['band_fr'] = fr
    # two top strips with the zip between them
    sw = (INNER - ZIP['gap']) / 2
    for s in (-1, 1):
        yc = s * (ZIP['gap'] / 2 + sw / 2)
        P = densify([Vector((BW / 2 - BR, yc, BH - BT / 2)), Vector((-(BW / 2 - BR), yc, BH - BT / 2))],1.5)
        fr = frames_for(P, fixedW=(0, 1, 0))
        prof = support(rr_profile(sw, BT, 1.0, n=4)); pm = prof_mat(sw, 1.0)(prof)
        st = sweep2('strip_%d' % (s > 0), fr, lambda i: prof, mats=[M['L'], M['E'], M['F']], parent=G['band'], mat_fn=pm, cap_mat=1)
        # stitch rows that hold the zip tape, near the inner edge
        y = s * (ZIP['gap'] / 2 + 2.7)
        it = line_stitches((ZIP['x1'] - 1, y, BH - .02), (ZIP['x0'] + 1, y, BH - .02), PITCH, (0, 0, 1))
        sto = stitch_row('strip_st_%d' % (s > 0), it, [M['TH']], parent=G['band']); R['strip_%d' % (s > 0)] = (st, fr, it); R['strip_st_%d' % (s > 0)] = sto
        # the zip tape under the strip, its bead edge where the teeth clamp (swept so it can bend with the opening)
        Pt = densify([Vector((ZIP['x1'] + 3, s * 7.6, BH - BT - .45)), Vector((ZIP['x0'] - 3, s * 7.6, BH - BT - .45))],1.5)
        tpo = sweep2('tape_%d' % (s > 0), frames_for(Pt, fixedW=(0, 1, 0)), lambda i: support(rr_profile(12.0, .7, .3, n=2)), mats=[M['TP']], parent=G['band'], wn=False)
        R['tape_%d' % (s > 0)] = tpo
    # inside lining of the gusset seen when the stack opens: the band's flesh side does that job

# ---------------------------------------------------------------- zip teeth (one mesh; vertices driven by the slider)
def _tooth_template():
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=(1.15, 4.4, 2.3), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=.42, segments=3, affect='EDGES', profile=.5)
    # the scoop: the tip (y > 0 half) is a little thicker and lower, like a real formed tooth
    for v in bm.verts:
        if v.co.y > .8: v.co.x *= 1.25; v.co.z -= .12
    V = [v.co.copy() for v in bm.verts]; F = [[v.index for v in f.verts] for f in bm.faces]; bm.free(); return V, F
TOOTH = None
def teeth_list():
    out = []; x = ZIP['x0']; i = 0
    while x <= ZIP['x1'] + 1e-6:
        out.append((x, -1 if i % 2 == 0 else 1)); x += ZIP['pitch']; i += 1
    return out
def teeth_verts(sx, g=0.):
    """slider at x = sx; teeth right of the slider are open (the slider opens the chain as it moves left); g = mouth opening"""
    V0, _ = TOOTH; out = []
    for x, s in teeth_list():
        k = smooth01((x - sx - 1.5) / 9.0)
        rot = Matrix.Rotation(-s * .35 * k, 3, 'X')
        base = Vector((x, s * (1.05 + 2.0 * k), BH - BT - .75 + .45 * k))
        for v in V0:
            w = Vector((v.x, -s * v.y, v.z))           # the tip points across the chain
            out.append(gape_point(base + rot @ w, s, g) if g > 0 else base + rot @ w)
    return out
# The open mouth, as a pulled-open soft pouch: the two zip chains part from the slider's open shoulder and from the
# zip's end stop in a short V, then round out to almost upright strips along the middle. Defined by the half-width
# between the tooth tips (what limits what can pass), then turned into the strips' hinge angle.
GAPE_MAX = math.radians(88)
MOUTH = (-SL_PARK + 5.5, ZIP['x1'])            # open span: slider shoulder → end stop
GAPE_SLOPE = 1.0                               # half-width gained per mm away from either end (the V)
def _tip_half(a): return INNER / 2 - 21.55 * math.cos(a) - 3.5 * math.sin(a)
def _gape_lut():
    h0, hc = _tip_half(0.), _tip_half(GAPE_MAX); out = []
    for i in range(int((MOUTH[1] - MOUTH[0]) * 4) + 1):
        d = min(i / 4, MOUTH[1] - MOUTH[0] - i / 4)
        h = h0 + (hc - h0) * (1 - math.exp(-GAPE_SLOPE * d / (hc - h0)))
        lo, hi = 0., GAPE_MAX
        for _ in range(28):
            m = (lo + hi) / 2
            if _tip_half(m) < h: lo = m
            else: hi = m
        out.append(lo)
    return out
GAPE_LUT = _gape_lut()
def gape_angle(x, g):
    if g <= 0 or not (MOUTH[0] < x < MOUTH[1]): return 0.
    f = (x - MOUTH[0]) * 4; i = min(int(f), len(GAPE_LUT) - 2); w = f - i
    return g * (GAPE_LUT[i] * (1 - w) + GAPE_LUT[i + 1] * w)
def gape_point(P, side, g):
    """side -1 = front strip, +1 = back strip"""
    a = gape_angle(P.x, g)
    if a == 0: return Vector(P)
    hy, hz = side * INNER / 2, BH
    v = Matrix.Rotation(-side * a, 3, 'X') @ Vector((0, P.y - hy, P.z - hz))
    return Vector((P.x, hy + v.y, hz + v.z))
def teeth(M, G):
    global TOOTH; TOOTH = _tooth_template(); V0, F0 = TOOTH
    n = len(teeth_list()); F = []
    for i in range(n): F += [[i * len(V0) + j for j in f] for f in F0]
    me = bpy.data.meshes.new('teeth'); me.from_pydata([tuple(v) for v in teeth_verts(ZIP['x1'] + 2)], [], F); me.update()
    ob = mesh_obj('teeth', me, [M['BD']], G['band']); R['teeth'] = ob

# ---------------------------------------------------------------- slider and pull tab
def rbox(name, size, r, seg, mats_, parent, loc=(0, 0, 0)):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=r, segments=seg, affect='EDGES', profile=.5)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); ob = mesh_obj(name, me, mats_, parent); weighted(ob); return ob

def slider(M, G):
    sl = empty('slider', (SL_PARK, 0, 0), G['band']); R['slider'] = sl
    z0 = BH - BT + .2
    # top plate: tapered (wide at the shoulder that faces the open side, +X)
    tr = [(-5.5, -3.4), (5.5, -4.9), (5.5, 4.9), (-5.5, 3.4)]
    pl = []
    for i in range(4):
        a, b, c = Vector(tr[i - 1]), Vector(tr[i]), Vector(tr[(i + 1) % 4])
        for k in range(7):                                  # round each corner a little
            u = k / 6; p1 = b + (a - b).normalized() * 1.4; p2 = b + (c - b).normalized() * 1.4
            pl.append(tuple((1 - u) ** 2 * p1 + 2 * (1 - u) * u * b + u * u * p2))
    top = slab('slider_top', pl, 2.2, .7, [M['B']], parent=sl, res=3); weighted(top)
    top.rotation_euler.x = -math.pi / 2; top.location = (0, 0, z0 + 2.4)
    for s in (-1, 1):                                       # side flanges over the chain
        rbox('slider_fl', (10.5, 1.0, 3.2), .35, 2, [M['B']], sl, (0, s * 4.4, z0 + 1.0))
    # the pull bridge: an arch on top
    arch = [Vector((-3.2 + 6.4 * i / 16, 0, z0 + 3.4 + 2.6 * math.sin(math.pi * i / 16))) for i in range(17)]
    fr = frames_for(arch, fixedW=(0, 1, 0)); pr = support(rr_profile(3.2, 1.3, .5, n=3))
    sweep2('slider_bridge', fr, lambda i: pr, mats=[M['B']], parent=sl)
    # a short brass link hinged on the bridge, the leather tab riveted to it
    piv = empty('tab_pivot', (0, 0, z0 + 6.0), sl); R['tab_pivot'] = piv
    lk = slab('pull_link', [(x + 3.4, y) for x, y in rrect_pts(7.0, 4.4, 1.8, n=6)], 1.0, .35, [M['B']], parent=piv, res=2); weighted(lk)
    lk.rotation_euler.x = -math.pi / 2
    tab_o = [(x + 22.0, y) for x, y in rrect_pts(34, 10, 4.5, n=10, rt=2.0)]
    tb = slab('pull_tab', tab_o, 2.4, .9, [M['L'], M['E'], M['F']], parent=piv, res=4); weighted(tb)
    tb.rotation_euler.x = -math.pi / 2               # lie in the XY plane, thickness along Z
    for zz, nn in ((1.2 - .02, 1), (-1.2 + .02, -1)):
        items = outline_stitches(tab_o, 2.0, lambda x, y: x > 11, lambda x, y: Vector((x, y, zz)), Vector((0, 0, nn)), step=3.6)
        stitch_row('tab_st', items, [M['TH']], parent=piv, length=2.6, radius=.4)
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=1)
        for v in bm.verts: v.co = Vector((v.co.x * 1.4, v.co.y * 1.4, max(v.co.z, 0) * .7 * nn))
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4); bmesh.ops.translate(bm, vec=(7.4, 0, zz), verts=bm.verts)
        me = bpy.data.meshes.new('tab_rivet'); bm.to_mesh(me); bm.free(); mesh_obj('tab_rivet', me, [M['B']], piv)
    R['tab_len'] = 34.0

def tab_angle(px, pz):
    """the tab rests on the bag: largest downward angle (to the right) at which it doesn't enter the leather"""
    def ok(a):
        d = Vector((math.cos(a), 0, -math.sin(a)))
        for i in range(2, 40):
            q = Vector((px, 0, pz)) + d * float(i)
            if sd_rrect(q.x, q.z, BW, BH, BR, 0, BH / 2) < 1.45: return False
        return True
    lo, hi = -0.3, 1.5
    if ok(hi): return hi
    for _ in range(30):
        m = (lo + hi) / 2
        if ok(m): lo = m
        else: hi = m
    return lo

# ---------------------------------------------------------------- front pocket
def pocket(M, G):
    o = rrect_pts(PK['w'], PK['h'], PK['r'], n=12)
    yface = -BD / 2 - PK['d'] + PK['t'] / 2
    f = slab('pocket_face', o, PK['t'], 1.0, [M['L'], M['E'], M['F']], parent=G['pocket'], res=5); weighted(f)
    f.location = (PK['x'], yface, PK['z']); R['pocket'] = f
    keep = lambda x, z: z < PK['h'] / 2 - 5
    it = outline_stitches(o, 3.3, keep, lambda x, z: Vector((x, -PK['t'] / 2 + .02, z)), Vector((0, -1, 0)))
    stitch_row('pocket_st', it, [M['TH']], parent=f); R['items_pocket'] = it
    stitch_row('pocket_st_in', outline_stitches(o, 3.3, keep, lambda x, z: Vector((x, PK['t'] / 2 - .02, z)), Vector((0, 1, 0))), [M['TH']], parent=f)
    # U gusset between the face and the front panel
    gw = PK['d'] - PK['t'] - .3; gy = -BD / 2 - .15 - gw / 2
    P = densify(u_path(PK['w'] - 2.0, 80.5, PK['r'] - 1.0, cx=PK['x'], cz=56.25, n=10, top_arcs=False, y=gy), 5)
    fr = frames_for(P, fixedW=(0, 1, 0)); pr = support(rr_profile(gw, 2.0, .8, n=4)); pm = prof_mat(gw, .8)(pr)
    sweep2('pocket_gusset', fr, lambda i: pr, mats=[M['L'], M['E'], M['F']], parent=G['pocket'], mat_fn=pm, cap_mat=1)

# ---------------------------------------------------------------- flap: one swept piece that drapes over the pocket and bends to open
FL_CTRL = [(-26.6, 108.0), (-26.6, 104.4), (-27.7, 102.3), (-30.8, 100.6), (-35.0, 99.7), (-38.5, 98.7),
           (-40.4, 96.8), (-41.0, 93.8), (-41.0, 89.0), (-41.0, 70.0), (-41.0, 49.0)]
FL = {}
def _flap_rest():
    P = catmull([Vector((FLAP['x'], y, z)) for y, z in FL_CTRL], n=10)
    P, ds = even(P, .5); FL['P0'] = P; FL['ds'] = ds; FL['L'] = ds * (len(P) - 1)
    FL['phi'] = [math.atan2((P[i + 1] - P[i]).z, (P[i + 1] - P[i]).y) for i in range(len(P) - 1)]
    best = min(range(len(P)), key=lambda i: (P[i] - Vector((FLAP['x'], -40.6, 96.2))).length); FL['sh'] = best * ds
    FL['s_leaf'] = min(range(len(P)), key=lambda i: abs(P[i].z - 92.5) + (0 if P[i].y < -40 else 99)) * ds
    FL['s_root'] = min(range(len(P)), key=lambda i: abs(P[i].z - 106.0) + (0 if P[i].y > -27 else 99)) * ds
def flap_path(theta):
    P0, ds = FL['P0'], FL['ds']; P = [P0[0].copy()]
    for i, ph in enumerate(FL['phi']):
        s = (i + .5) * ds; ph2 = ph - theta * smooth01((s - (FL['sh'] - 6)) / 12)
        P.append(P[-1] + Vector((0, math.cos(ph2), math.sin(ph2))) * ds)
    return P
def flap_width(s):
    L, r, w = FL['L'], FLAP['r'], FLAP['w']
    if s < L - r: return w
    u = s - (L - r); return w - 2 * r + 2 * math.sqrt(max(0., r * r - u * u))
FL_PROF = None
def flap_frames(theta): return frames_for(flap_path(theta), fixedW=(-1, 0, 0))
def flap_prof(i):
    s = i * FL['ds']; d = (flap_width(s) - FLAP['w']) / 2
    return [(a + (d if a > 0 else -d), b) for a, b in FL_PROF]
def _frame_at(fr, s):
    x = s / FL['ds']; i = max(0, min(len(fr) - 2, int(x))); u = x - i
    p = fr[i][0].lerp(fr[i + 1][0], u); t = fr[i][1].lerp(fr[i + 1][1], u).normalized()
    W = fr[i][2].lerp(fr[i + 1][2], u).normalized(); N = fr[i][3].lerp(fr[i + 1][3], u).normalized(); return p, t, W, N
def flap_stitch_items(fr):
    """(a, s) stitch layout: root line across, then the leaf's sides and rounded bottom, both faces"""
    w, L, r, ins, h = FLAP['w'], FL['L'], FLAP['r'], 3.2, FLAP['t'] / 2 - .02
    U = [(w / 2 - ins, FL['s_leaf'])]
    U.append((w / 2 - ins, L - r))
    for k in range(1, 9):
        a = (math.pi / 2) * k / 8; U.append((w / 2 - r + (r - ins) * math.cos(a), L - r + (r - ins) * math.sin(a)))
    for k in range(8, -1, -1):
        a = (math.pi / 2) * k / 8; U.append((-(w / 2 - r) - (r - ins) * math.cos(a), L - r + (r - ins) * math.sin(a)))
    U.append((-(w / 2 - ins), FL['s_leaf']))
    leaf, _ = even([Vector((a, s, 0)) for a, s in U], PITCH)
    root, _ = even([Vector((w / 2 - 6, FL['s_root'], 0)), Vector((-(w / 2 - 6), FL['s_root'], 0))], PITCH)
    out = []
    def emit(seq, side):
        for k, q in enumerate(seq):
            d = seq[min(k + 1, len(seq) - 1)] - seq[max(k - 1, 0)]
            p, t, W, N = _frame_at(fr, q.y)
            out.append((p + W * q.x + N * (side * h), (W * d.x + t * d.y).normalized(), N * side))
    emit(leaf, 1); emit(leaf, -1); emit(root, 1)
    return out
def flap_verts(theta):
    fr = flap_frames(theta)
    V = sweep_verts(fr, flap_prof)
    S = stitch_verts(flap_stitch_items(fr))
    return V, S
def flap(M, G):
    global FL_PROF
    _flap_rest(); FL_PROF = support(rr_profile(FLAP['w'], FLAP['t'], 1.2, n=4))
    fr = flap_frames(0.)
    pm = prof_mat(FLAP['w'], 1.2)(FL_PROF)
    ob = sweep2('flap', fr, flap_prof, mats=[M['L'], M['E'], M['F']], parent=G['flap'], mat_fn=pm, cap_mat=1)
    st = stitch_row('flap_st', flap_stitch_items(fr), [M['TH']], parent=G['flap']); R['flap_fr0'] = fr
    R['flap'] = ob; R['flap_st'] = st

def stitch_verts(items, length=3.8, radius=.5, slant=.42, sink=.2):
    V0, _ = _capsule_template(length, radius); out = []
    for k, (p, t, n) in enumerate(items):
        o, Rm, dl = stitch_frame(p, t, n, k, length, radius, slant, sink)
        out += [o + Rm @ Vector((v.x * dl, v.y, v.z)) for v in V0]
    return out

# ---------------------------------------------------------------- hardware: anchor tab, ring, snap hook, wrist strap
HWX = -120.6
RING = dict(R=10.5, r=1.55, c=Vector((HWX, 0, 88.5)), beta=math.radians(20))
def anchor_tab(M, G):
    W = Vector((HWX, 0, 99.0)); rc = 1.55 + .15 + 1.0
    up = [Vector((-104.2, 0, 99.0 + 1.0)), Vector((-110.0, 0, 99.0 + 1.0)), Vector((-114.5, 0, 99.0 + 1.9)), Vector((-118.5, 0, 99.0 + rc))]
    fold = [W + Vector((-rc * math.sin(a), 0, rc * math.cos(a))) for a in [math.pi * k / 16 for k in range(17)]]
    dn = [Vector((-118.5, 0, 99.0 - rc)), Vector((-114.5, 0, 99.0 - 1.9)), Vector((-110.0, 0, 99.0 - 1.0)), Vector((-104.2, 0, 99.0 - 1.0))]
    P = catmull(up + fold[1:-1] + dn, n=6); P, _ = even(P, .4)
    fr = frames_for(P, fixedW=(0, 1, 0)); pr = support(rr_profile(12, 2.0, .8, n=4)); pm = prof_mat(12, .8)(pr)
    t = sweep2('anchor_tab', fr, lambda i: pr, mats=[M['L'], M['E'], M['F']], parent=G['band'], mat_fn=pm, cap_mat=1)
    stitch_row('anchor_st', line_stitches((-108.4, -4.3, 101.0 - .02), (-108.4, 4.3, 101.0 - .02), 4.3, (0, 0, 1)), [M['TH']], parent=G['band'], length=2.6)
    # one domed rivet through both layers
    for z, s in ((101.55, 1), (96.45, -1)):
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1)
        for v in bm.verts: v.co = Vector((v.co.x * 2.6, v.co.y * 2.6, max(v.co.z, 0) * 1.1 * s))
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bmesh.ops.translate(bm, vec=(-113.6, 0, z), verts=bm.verts)
        me = bpy.data.meshes.new('rivet'); bm.to_mesh(me); bm.free(); mesh_obj('rivet', me, [M['B']], G['band'])
    R['anchor'] = t

def hardware(M, G):
    hw = G['hw']
    # O-ring: hangs in a plane that contains Z, turned beta from the YZ plane
    rp = empty('ring_piv', tuple(RING['c']), hw); R['ring'] = rp
    pts = [Vector((0, RING['R'] * math.cos(2 * math.pi * i / 72), RING['R'] * math.sin(2 * math.pi * i / 72))) for i in range(72)]
    ro = tube('ring', pts, RING['r'], True, [M['B']], rp, n=16, fixedW=(1, 0, 0))
    ro.rotation_euler.z = -RING['beta']
    # snap hook: an oval link hooked over the ring's bottom wire, a gate on one side, a swivel neck
    hk = empty('hook_piv', (HWX, 0, 74.0), hw); R['hook'] = hk
    ztop = RING['c'].z - RING['R'] + RING['r'] + 1.5 - 74.0      # hook top wire rests on the ring wire
    hw_, zb = 4.0, 67.0 - 74.0
    body = [Vector((hw_ * math.cos(a), 0, (ztop - hw_) + hw_ * math.sin(a))) for a in [math.pi * k / 16 for k in range(17)]]
    body += [Vector((-hw_, 0, (ztop - hw_) + ((zb + 3.0) - (ztop - hw_)) * k / 7)) for k in range(1, 8)]
    body += [Vector((hw_ * math.cos(a), 0, zb + 3.0 + 3.0 * math.sin(a))) for a in [math.pi + math.pi / 2 * k / 8 for k in range(1, 9)]]
    body += [Vector((1.4, 0, zb + .15)), Vector((2.4, 0, zb + .7))]
    tube('hook_body', catmull(body, 3), 1.5, False, [M['B']], hk, n=14, fixedW=(0, 1, 0))
    # the spring gate: straight, a little thinner, tiny gaps at both ends, a hinge pin at the bottom
    g0, g1 = Vector((hw_, 0, ztop - hw_ - .5)), Vector((2.4, 0, zb + 2.0))
    tube('hook_gate', [g0.lerp(g1, k / 10) for k in range(11)], 1.15, False, [M['B']], hk, n=12, fixedW=(0, 1, 0))
    pin = [Vector((2.4, -1.9 + 3.8 * k / 4, zb + 1.4)) for k in range(5)]
    tube('hook_pin', pin, .55, False, [M['B']], hk, n=10, fixedW=(1, 0, 0))
    # swivel: barrel + washer + neck down to the strap bar
    for (z0, z1, r) in ((zb - .2, zb - 2.0, 2.2), (zb - 2.0, zb - 2.9, 3.0), (zb - 2.9, zb - 6.0, 1.7)):
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=28, radius1=r, radius2=r, depth=abs(z1 - z0))
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges if not e.is_manifold or abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6], offset=.3, segments=2, affect='EDGES')
        bmesh.ops.translate(bm, vec=(0, 0, (z0 + z1) / 2), verts=bm.verts)
        me = bpy.data.meshes.new('swivel'); bm.to_mesh(me); bm.free(); ob = mesh_obj('swivel', me, [M['B']], hk); weighted(ob)
    # strap bar loop (does not turn with the hook: it is below the swivel)
    zbar = 74.0 + zb - 6.0                      # top of the bar loop (world z)
    R['zbar_bottom'] = zbar - 8.5
    lp = rrect_pts(20.0, 8.5, 2.6, n=8)
    lp = [Vector((x, 0, zbar - 4.25 + y)) for x, y in lp]
    tube('strap_bar', [Vector((HWX, 0, 0)) + p for p in lp], 1.25, True, [M['B']], hw, n=14, fixedW=(0, 1, 0))
    strap(M, G, Vector((HWX, 0, zbar - 8.5)))

def catmull_closed(P, n=8):
    P = [Vector(p) for p in P]; N = len(P); out = []
    for i in range(N):
        p0, p1, p2, p3 = P[i - 1], P[i], P[(i + 1) % N], P[(i + 2) % N]
        for k in range(n):
            t = k / n; t2 = t * t; t3 = t2 * t
            out.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return out

def strap(M, G, bar):
    x, zb = bar.x, bar.z; rf = 1.25 + .1 + 2.1
    # the loop: front strand down, a teardrop on the floor to the left, back strand up, over the bar
    F = [Vector((x, -rf, zb)), Vector((x, -2.2, zb - 6)), Vector((x, -2.2, zb - 14)), Vector((x - 1, -5.5, zb - 25)),
         Vector((x - 4, -16, zb - 40)), Vector((x - 12, -31, 4.6)), Vector((x - 26, -44, 2.1)), Vector((x - 46, -47, 2.1)),
         Vector((x - 63, -34, 2.1)), Vector((x - 71, -11, 2.1)), Vector((x - 70, 13, 2.1)), Vector((x - 61, 35, 2.1)),
         Vector((x - 44, 47, 2.1)), Vector((x - 25, 43, 2.1)), Vector((x - 11, 30, 4.6)), Vector((x - 3.5, 15, zb - 40)),
         Vector((x - .8, 5.5, zb - 25)), Vector((x, 2.2, zb - 14)), Vector((x, 2.2, zb - 6)), Vector((x, rf, zb))]
    top = [Vector((x, rf * math.cos(a), zb + rf * math.sin(a))) for a in [math.pi * k / 10 for k in range(1, 10)]]
    P = catmull_closed(F + top, n=8)
    P, _ = even(P, 1.0, closed=True)
    def faceF(p):
        if p.z > zb - 3: return Vector((0, p.y, p.z - zb)).normalized() if (p.y, p.z - zb) != (0, 0) else Vector((0, 0, 1))
        k = smooth01((zb - 30 - p.z) / (zb - 30 - 6))
        return Vector((0, 1 if p.y > 0 else -1, 0)).lerp(Vector((0, 0, 1)), k).normalized()
    fr = frames_for(P, faceF=faceF, closed=True)
    pr = support(rr_profile(16, 4.2, 1.2, n=4)); pm = prof_mat(16, 1.2)(pr)
    s = sweep2('strap', fr, lambda i: pr, closed=True, mats=[M['L'], M['E'], M['L']], parent=G['hw'], mat_fn=pm)
    items = []
    for k, (p, t, W, N) in enumerate(fr):
        if k % 4: continue
        if p.z > zb - 1: continue
        for a in (-5.6, 5.6):
            items.append((p + W * a + N * (2.1 - .02), t, N))
    stitch_row('strap_st', items, [M['TH']], parent=G['hw']); R['items_strap'] = items
    R['strap'] = s; R['strap_frames'] = fr

# ---------------------------------------------------------------- studio: floor, world, lights, camera
def studio(M):
    sc = bpy.context.scene
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30000)
    me = bpy.data.meshes.new('floor'); bm.to_mesh(me); bm.free(); fl = mesh_obj('floor', me, [M['FL']], smooth=False)
    fl.location.z = -.05; R['floor'] = fl
    w = bpy.data.worlds.new('studio'); sc.world = w; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld'); env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(HDR)
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (0, 0, math.radians(130))
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], env.inputs['Vector'])
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = .35; nt.links.new(env.outputs[0], bg.inputs[0])
    dark = nt.nodes.new('ShaderNodeBackground'); dark.inputs[0].default_value = (.0045, .0040, .0038, 1)
    lp = nt.nodes.new('ShaderNodeLightPath'); mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mx.inputs[0]); nt.links.new(bg.outputs[0], mx.inputs[1]); nt.links.new(dark.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs['Surface']); R['world_bg'] = bg
    def area(name, size, loc, aim, power, col, shape='RECTANGLE'):
        L = bpy.data.lights.new(name, 'AREA'); L.shape = shape; L.size, L.size_y = size; L.energy = power; L.color = col
        o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc; o.visible_camera = False
        d = Vector(aim) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); R[name] = o; return o
    area('key', (520, 360), (-430, -560, 470), (0, 0, 55), 1.25e7, (1, .93, .85))
    area('rim', (760, 110), (360, 560, 320), (0, 0, 70), 9e6, (1, .95, .88))
    area('rim_bag', (760, 110), (360, 560, 320), (0, 0, 70), 9e6 * .3, (1, .95, .88))   # +30% rim on the bag only (light-linked in build)
    area('top', (520, 520), (40, 60, 700), (0, 0, 60), 1.8e6, (1, .98, .95))
    area('fill', (900, 600), (620, -540, 140), (0, 0, 60), 1.6e6, (1, .97, .93))
    area('gapL', (40, 70), (-300, -126, 66), (0, -134, 58), 0, (1, .86, .70))
    gl = bpy.data.lights.new('glint', 'POINT'); gl.energy = 0; gl.color = (1, .78, .52); gl.shadow_soft_size = .6
    go = bpy.data.objects.new('glint', gl); sc.collection.objects.link(go); go.visible_camera = False; R['glint'] = go
    cd = bpy.data.cameras.new('cam'); cd.lens = 85; cd.sensor_width = 36; cd.clip_start = 2; cd.clip_end = 20000
    cd.dof.use_dof = True; cd.dof.aperture_fstop = 5.6; cd.dof.aperture_blades = 7; cd.dof.aperture_rotation = math.radians(12)
    cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam; R['cam'] = cam
    ft = empty('focus', (0, 0, 60)); cd.dof.focus_object = ft; R['focus'] = ft

def render_settings(w=1920, h=1080, spp=512, thr=.03):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; cy = sc.cycles; cy.device = 'CPU'
    cy.samples = spp; cy.use_adaptive_sampling = True; cy.adaptive_threshold = thr; cy.adaptive_min_samples = 0
    cy.seed = 0; cy.use_animated_seed = False            # one fixed noise pattern for every frame (no temporal crawl)
    cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
    try: cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'; cy.denoising_prefilter = 'ACCURATE'; cy.denoising_quality = 'HIGH'
    except Exception: pass
    cy.max_bounces = 8; cy.diffuse_bounces = 3; cy.glossy_bounces = 4; cy.transmission_bounces = 2; cy.transparent_max_bounces = 4
    cy.volume_bounces = 0; cy.caustics_reflective = False; cy.caustics_refractive = False
    cy.sample_clamp_indirect = 4.0; cy.blur_glossy = .6
    try: cy.use_light_tree = True
    except Exception: pass
    sc.render.resolution_x, sc.render.resolution_y = w, h; sc.render.resolution_percentage = 100
    sc.render.film_transparent = False; sc.render.use_persistent_data = True
    sc.render.fps = 30
    sc.view_settings.view_transform = 'AgX'
    try: sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    sc.view_settings.exposure = 0.0
    sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = .001; sc.unit_settings.length_unit = 'MILLIMETERS'

def details(M):
    """per-part leather with its own surface detail map (stitch channels, holes, puff, edge crease)"""
    import maps as MP
    def setmat(ob, mat, slots=(0,)):
        for i in slots: ob.material_slots[i].material = mat
    for side in ('front', 'back'):
        H = MP.holes_3d(R['items_' + side]); H = [(MP.to_uv_slab(a), MP.to_uv_slab(b)) for a, b in H]
        d = MP.panel_map(side, BW, BH, BR, 4.4, H, seed=11 if side == 'front' else 23)
        setmat(R[side + '_panel'], MT.leather('leather_' + side, d))
    H = [(MP.to_uv_slab(a), MP.to_uv_slab(b)) for a, b in MP.holes_3d(R['items_pocket'])]
    LOGO = dict(mask=np.load(ROOT + '/logo/plate_mask.npy'), cx=38.0, cz=-23.0, w=46.0, depth=.42)
    d = MP.panel_map('pocket', PK['w'], PK['h'], PK['r'], 3.3, H, seed=31, keep=lambda U, V: (V < PK['h'] / 2 - 5).astype(np.float32), deboss=LOGO)
    setmat(R['pocket'], MT.leather('leather_pocket', d))
    # flap: UV = (a, s) on the rest shape
    fr = R['flap_fr0']; fuv, L = MP.sweep_uv_fn(fr)
    items = [it for it in flap_stitch_items(fr) if it[2].dot(fr[len(fr) // 2][3]) > 0 or True]
    H = [(fuv(a), fuv(b)) for a, b in MP.holes_3d(items)]
    H = [h for h in H]
    def flap_wr(U, V):
        k = np.exp(-((V - FL['sh']) / 5.0) ** 2)
        return 0 * U
    d = MP.strip_map('flap', FLAP['w'] / 2, L, [], H, seed=41, crease=1.7, pillow=.12, wrinkle=flap_wr)
    setmat(R['flap'], MT.leather('leather_flap', d))
    fuv, L = MP.sweep_uv_fn(R['band_fr'])
    d = MP.strip_map('band', INNER / 2, L, [], [], seed=51, crease=0, pillow=.22, edges=False)
    setmat(R['band'], MT.leather('leather_band', d))
    for k in (0, 1):
        ob, fr, it = R['strip_%d' % k]; fuv, L = MP.sweep_uv_fn(fr)
        H = [(fuv(a), fuv(b)) for a, b in MP.holes_3d(it)]
        line = fuv(it[len(it) // 2][0])[0]
        d = MP.strip_map('strip%d' % k, (INNER - ZIP['gap']) / 4, L, [line], H, seed=61 + k, crease=1.5, pillow=.16)
        setmat(ob, MT.leather('leather_strip%d' % k, d))
    fuv, L = MP.sweep_uv_fn(R['strap_frames'])
    H = [(fuv(a), fuv(b)) for a, b in MP.holes_3d(R['items_strap'])]
    d = MP.strip_map('strap', 8.0, L, [-5.6, 5.6], H, seed=71, crease=1.4, pillow=.2)
    setmat(R['strap'], MT.leather('leather_strap', d), slots=(0, 2))

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = dict(L=MT.leather(), E=MT.edge(), F=MT.flesh(), TH=MT.thread(), B=MT.brass(), BD=MT.brass('brass_dark', (0.58, 0.41, 0.19, 1), .26, .42),
             TP=MT.tape(), FL=MT.floor())
    G = {k: empty('G_' + k) for k in ('flap', 'pocket', 'front', 'band', 'back', 'hw')}
    R['G'] = G; R['M'] = M
    panels(M, G); band(M, G); teeth(M, G); slider(M, G); pocket(M, G); flap(M, G); anchor_tab(M, G); hardware(M, G); studio(M)
    details(M)
    render_settings()
    # the bag's extra rim: light-linked so only the bag's own parts receive it
    bag = bpy.data.collections.new('bag_only')
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.name != 'floor': bag.objects.link(o)
    R['rim_bag'].light_linking.receiver_collection = bag; R['bag_coll'] = bag
    # slider parked at the right end, tab resting on the corner
    sl = R['slider']; sl.location.x = SL_PARK
    piv = R['tab_pivot']; px = sl.location.x + piv.location.x; pz = piv.location.z
    piv.rotation_euler.y = tab_angle(px, pz)
    return R

if __name__ == '__main__':
    build()
    bpy.ops.wm.save_as_mainfile(filepath=ROOT + '/bag.blend')
    print('BUILT', len(bpy.data.objects), 'objects')
