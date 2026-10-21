# «HAMZA» v2 — the brief's story, 16:9, 30 fps:
#   1 hook: everything floats around the open bag · 2 it all goes into the main compartment · 3 the zip closes
#   4 the flap lifts, two cards slide into the front pocket · 5 a slow 360° orbit of the closed bag (strap and gold
#   clasps, the back, the zip, the stitching) · 6 the stamped mark under a moving light · 7 end card.
# Bakes all motion into film2.blend, label anchors into anchors2.json and the sound cues into audio/events2.json.
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy, sys, math, json
from mathutils import Vector, Quaternion, Matrix, Euler
sys.path.insert(0, ROOT)
import scene as S, items as IT
import anim as A1
from anim import clamp, lerp, seg, ss, eio, eo, ei, orbit, _cr, bake_shapes, kf, Q, RZ90, LOGO_W
from bpy_extras.object_utils import world_to_camera_view

FPS = 30
BEAT = 2 / 3; b = lambda n: round(n * BEAT, 4)
DUR = b(44)                                   # 29.33 s, 11 bars at 90 BPM
NF = int(round(DUR * FPS))
tof = lambda f: (f - 1) / FPS
W_, H_ = 1920, 1080

CUT = [0.0, b(6), b(12), b(16), b(22), b(34), b(38), DUR]     # hook · in · zip · pocket · orbit · mark · end
T = dict(
    gapeClose=(b(12.0), b(12.9)), zipClose=(b(13.0), b(14.8)), tabClose=(b(13.0), b(13.6)),
    flapUp=(b(16.5), b(18.0)), flapDown=(b(20.7), b(21.5)),
    sweep=(b(34.4), b(37.7)), card=b(39.0), tag=b(39.7), cta=b(40.6),
    lblItems=(0.55, b(6) - .25),
)
CARDS = {  # front pocket: glide over the pocket, then slide down into it
    'card1': (b(17.2), b(18.9), b(20.0), Vector((-22.0, -34.2, 55.0))),
    'card2': (b(17.8), b(19.5), b(20.6), Vector((26.0, -35.4, 54.0)))}
SHOW = dict(A1.SHOW)
SHOW['phone'] = (Vector((-208, -46, 158)), SHOW['phone'][1])     # clear of the memo: no shadow step on the paper
# Into the main compartment one at a time, the way a hand does it: over the middle of the open mouth, straight down the
# centre of the opening (the only place a 15 cm item clears the zip chains), then pushed back or forward into its own
# layer. Layers, back → front: cash, keys, phone, letter — each about 2 mm clear of the next one and of the walls.
Q_IN = {k: A1.INSIDE[k][1] for k in ('phone', 'letter', 'keys', 'cash')}
XM = (S.MOUTH[0] + S.MOUTH[1]) / 2            # middle of the open mouth
Z_UP = 152.0                                  # an item's lowest point as it hangs over the mouth (the raised tips reach ~141)
Z_FLOOR = 4.4                                 # its lowest point at rest (the inside bottom is at 2.6)
LANE = {'cash': 16.75, 'keys': 10.15, 'phone': .3, 'letter': -11.15}     # centre depth (y) of each layer
REST_X = {'cash': 0.0, 'keys': 46.0, 'phone': 0.0, 'letter': 0.0}        # centre x of each item at rest
DROP_X = {'keys': 30.0}                       # where an item sinks through the mouth if not its middle (keys: clear of the floating memo)
INTO = {'cash': 4.10, 'keys': 4.95, 'letter': 5.80, 'phone': 6.65}       # each starts its flight in
T_FLY, T_DROP, T_SET = .55, 1.05, 1.35        # after the start: over the mouth · down at the bottom · pushed into its layer
EXT = {}                                      # (lo, hi) of each item about its origin, in its inside orientation (main())
def home_t(k): return INTO[k] + T_SET

def item_extents(IR):
    dg = bpy.context.evaluated_depsgraph_get()
    for k, q in Q_IN.items():
        r = IR[k]; inv = r.matrix_world.inverted(); V = []
        for o in r.children_recursive:
            if o.type != 'MESH' or o.hide_render: continue
            ev = o.evaluated_get(dg); me = ev.to_mesh(); m = inv @ o.matrix_world
            V += [q @ (m @ v.co) for v in me.vertices]; ev.to_mesh_clear()
        EXT[k] = (Vector([min(v[i] for v in V) for i in range(3)]), Vector([max(v[i] for v in V) for i in range(3)]))
        lo, hi = EXT[k]; print('EXT', k, tuple(round(c, 1) for c in lo), tuple(round(c, 1) for c in hi))

def anchor(k, cx, cy, zlo):
    """origin that puts the item's box centre at (cx, cy) and its lowest point at zlo"""
    lo, hi = EXT[k]; c = (lo + hi) / 2
    return Vector((cx - c.x, cy - c.y, zlo - lo.z))
LBL_ITEMS = {'phone': 'جوال', 'letter': 'أوراق', 'keys': 'مفاتيح', 'card1': 'بطاقات', 'cash': 'نقود'}

# ---------------------------------------------------------------- items
def bob(k, t, p, q):
    h = (sum(map(ord, k)) % 97) / 97.0
    p = p + Vector((0, 0, 2.4 * math.sin(2 * math.pi * (t * .42 + h))))
    q = Quaternion((0, 0, 1), .03 * math.sin(2 * math.pi * (t * .31 + h))) @ q
    return p, q

def _bez3(a, c1, c2, b, w): return (1 - w) ** 3 * a + 3 * (1 - w) ** 2 * w * c1 + 3 * (1 - w) * w * w * c2 + w ** 3 * b
RISE = {'cash': 125.0, 'keys': 0.0, 'letter': 0.0, 'phone': 20.0}     # how far each first lifts before it heads over the bag
def _herm(t, p0, p1, m0, m1):
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1

def main_item_pose(k, t):
    """floats at SHOW; flies over the middle of the mouth, sinks straight down into it, then is pushed into its layer"""
    s0 = INTO[k]; p_sh, q_sh = SHOW[k]; q_in = Q_IN[k]
    xd = DROP_X.get(k, XM); p_up = anchor(k, xd, 0., Z_UP); p_dn = anchor(k, xd, 0., Z_FLOOR + 2.5)
    p_in = anchor(k, REST_X[k], LANE[k], Z_FLOOR)
    if t <= s0:
        return bob(k, t, p_sh, q_sh)
    if t >= s0 + T_SET:
        return p_in, q_in
    if t >= s0 + T_DROP:
        w = ss((t - s0 - T_DROP) / (T_SET - T_DROP)); return p_dn.lerp(p_in, w), q_in
    # one path (flight curve, then straight down), walked by arc length: the flight eases out into a gentle, steady sink
    c1 = p_sh + Vector((0, 0, RISE[k])); c2 = p_up + Vector((0, 0, 35)); N = 64
    pts = [_bez3(p_sh, c1, c2, p_up, i / N) for i in range(N + 1)] + [p_up.lerp(p_dn, i / 16) for i in range(1, 17)]
    L = [0.]
    for i in range(1, len(pts)): L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    LA, LT = L[N], L[-1]; tt = t - s0; vA = .7 * (LT - LA) / (T_DROP - T_FLY)
    if tt < T_FLY: u = _herm(tt / T_FLY, 0., LA, 0., vA * T_FLY)
    else: u = _herm((tt - T_FLY) / (T_DROP - T_FLY), LA, LT, vA * (T_DROP - T_FLY), 0.)
    u = min(max(u, 0.), LT)
    i = max(1, next((j for j in range(1, len(L)) if L[j] >= u), len(L) - 1))
    w = (u - L[i - 1]) / max(1e-9, L[i] - L[i - 1]); p = pts[i - 1].lerp(pts[i], w)
    q = q_sh.slerp(q_in, ss(min(1., u / max(1e-9, LA) * 1.2)))
    fl = 1 - ss(min(1., tt / .3))                          # the float fades out as it leaves
    if fl > 0:
        pb, qb = bob(k, t, p, q); p = p.lerp(pb, fl); q = q.slerp(qb, fl)
    return p, q

def card_pose(k, t):
    t0, t1, t2, home = CARDS[k]; p_sh, q_sh = SHOW[k]
    hover = home + Vector((0, 0, 150)); q_home = Quaternion()
    if t <= t0:
        return bob(k, t, p_sh, q_sh)
    if t < t1:
        w = eio((t - t0) / (t1 - t0)); c = (p_sh + hover) / 2 + Vector((0, 0, 30))
        p = (1 - w) ** 2 * p_sh + 2 * (1 - w) * w * c + w * w * hover
        pb, qb = bob(k, t, p_sh, q_sh); p = p + (pb - p_sh) * (1 - w)
        return p, q_sh.slerp(q_home, ss(w * 1.1))
    w = clamp((t - t1) / (t2 - t1)); w = 1 - (1 - w) ** 2.2        # slides in, slowing as it seats
    return hover.lerp(home, w), q_home

def item_pose(k, t):
    return card_pose(k, t) if k in CARDS else main_item_pose(k, t)

# ---------------------------------------------------------------- zip, mouth, flap
def slider_x(t): return lerp(-S.SL_PARK, S.SL_PARK, eio(seg(t, *T['zipClose'])))
def gape(t): return 1 - eio(seg(t, *T['gapeClose']))
def tab_beta(t, sx, pz):
    right = S.tab_angle(sx, pz); left = -math.pi - S.tab_angle(-sx, pz)
    return lerp(left, right, ss(seg(t, *T['tabClose'])))

def flap_k(t):
    up = eo(seg(t, *T['flapUp'])); down = ei(seg(t, *T['flapDown'])); d1 = T['flapDown'][1]
    k = up * (1 - down)
    if t > d1: k += math.exp(-(t - d1) * 10) * math.sin((t - d1) * 32) * -.03    # the leaf taps down and settles
    return max(k, 0.)

def flap_open_path(k):
    """root stays sewn; the leaf folds up from the root seam (a tight U), stands, then leans back over the top"""
    FL = S.FL; P0, ds = FL['P0'], FL['ds']; s_h = FL['s_root'] + 1.0
    P = [P0[0].copy()]
    for i, ph in enumerate(FL['phi']):
        if ph > 0: ph -= 2 * math.pi
        s = (i + .5) * ds
        if s < s_h: pt = ph
        else:
            a = s - s_h
            pt = -math.pi / 2 - math.pi * ss(a / 7.0) - (math.pi / 4) * ss((a - 21.0) / 14.0)
        p = ph + (pt - ph) * k
        P.append(P[-1] + Vector((0, math.cos(p), math.sin(p))) * ds)
    return P

def flap_verts(k):
    fr = S.frames_for(flap_open_path(k), fixedW=(-1, 0, 0))
    return S.sweep_verts(fr, S.flap_prof), S.stitch_verts(S.flap_stitch_items(fr))

# ---------------------------------------------------------------- camera: (t, eye, target, lens, f-stop, focus, shift_x)
def zip_close_keys():
    K = []
    for tt in [CUT[2], 8.5, 8.9, 9.3, 9.7, 10.1, CUT[3]]:
        sx = slider_x(tt); tx = lerp(-62, 72, eio(seg(tt, 8.6, 9.95)))
        tg = Vector((tx, -2, 120)); K.append((tt, orbit(tg, 22, 52, 430), tg, 85, 11, Vector((sx, 0, 121)), 0))
    return K

ORB_T = (-26.0, 0.0, 58.0)
def orbit_keys():
    K = []; t0, t1 = CUT[4], CUT[5]; n = 48
    for i in range(n + 1):
        x = i / n; u = .78 * x + .22 * (.5 - .5 * math.cos(math.pi * x))
        az = -28 - 360 * u; el = 13 + 3 * math.sin(math.pi * x)
        K.append((t0 + (t1 - t0) * x, orbit(ORB_T, az, el, 1080), Vector(ORB_T), 85, 11, Vector(ORB_T), 0))
    return K

SHOTS = [
    # 1 · hook: the open bag, everything it carries floating around it (85 mm, slow push and drift)
    lambda: [(CUT[0], orbit((4, -18, 136), -9, 12, 1580), (4, -18, 136), 85, 6.3, (0, -20, 130), 0),
             (CUT[1], orbit((4, -18, 130), -2, 11, 1460), (4, -18, 130), 85, 6.3, (0, -20, 126), 0)],
    # 2 · high angle into the open zip: they glide in one by one
    lambda: [(CUT[1], orbit((0, 2, 118), -20, 47, 880), (0, 2, 118), 85, 9, (0, 0, 121), 0),
             (CUT[2], orbit((0, 2, 118), -8, 50, 780), (0, 2, 118), 85, 9, (0, 0, 121), 0)],
    # 3 · the zip closes (macro, tracking the slider)
    zip_close_keys,
    # 4 · the flap lifts and the cards slide into the front pocket
    lambda: [(CUT[3], orbit((6, -30, 104), -24, 15, 800), (6, -30, 104), 85, 8, (4, -36, 90), 0),
             (CUT[4], orbit((6, -30, 98), -16, 13, 730), (6, -30, 98), 85, 8, (4, -36, 86), 0)],
    # 5 · 360° orbit of the closed bag
    orbit_keys,
    # 6 · the stamped mark, a soft light moving across it
    lambda: [(CUT[5], orbit(LOGO_W, 14, 8, 255), LOGO_W, 85, 11, LOGO_W, 0),
             (CUT[6], orbit(LOGO_W + Vector((2, 0, 0)), 4, 6, 222), LOGO_W + Vector((2, 0, 0)), 85, 11, LOGO_W, 0)],
    # 7 · end card: the bag on the left, room for the mark on the right
    lambda: [(CUT[6], orbit((-24, -14, 55), -24, 12, 1180), (-24, -14, 55), 85, 8, (-14, -25, 55), .2),
             (DUR + .5, orbit((-24, -14, 55), 6, 10, 1100), (-24, -14, 55), 85, 8, (-14, -25, 55), .2)],
]
def shot_at(t):
    for k in range(len(CUT) - 1):
        if CUT[k] - 1e-9 <= t < CUT[k + 1]: return k
    return len(CUT) - 2
def cam_state(t, k):
    keys = SHOTS[k]()
    eye, tg = _cr(keys, t, 1), _cr(keys, t, 2)
    lens, fst, foc, sh = _cr(keys, t, 3), _cr(keys, t, 4), _cr(keys, t, 5), _cr(keys, t, 6)
    fwd = (Vector(tg) - eye).normalized(); q = fwd.to_track_quat('-Z', 'Y')
    return dict(eye=eye, q=q, lens=lens, f=fst, fd=max(5., (Vector(foc) - eye).dot(fwd)), shift=sh)

# ---------------------------------------------------------------- labels: (id, text, spec, 3D anchor, window)
FEAT = [
    ('pocket', 'جيب أمامي للبطاقات', 'يتّسع لبطاقتين وأكثر', Vector((74, -39.2, 92)), (b(18.6), b(21.6))),
    ('strap', 'حزام يد بمشابك ذهبية', 'معدن عتيق اللون يدوم', Vector((S.HWX, -1.0, 66.0)), (b(23.2), b(25.6))),
    ('leather', 'جلد طبيعي فاخر', 'عنّابي داكن، ملمس ناعم', Vector((10, 25.4, 66)), (b(26.4), b(28.8))),
    ('zip', 'سحّاب معدني ذهبي', 'ينزلق بنعومة على طول الفتحة', Vector((S.SL_PARK, 0, 125.5)), (b(29.4), b(31.8))),
    ('stitch', 'خياطة بارزة متينة', 'غرز مائلة على كل الحواف', Vector((-60, -25.4, 4.6)), (b(32.0), b(33.8))),
]

def main():
    S.build(); R = S.R; sc = bpy.context.scene; M = R['M']
    IR = IT.build(M); R['items'] = IR
    item_extents(IR)
    S.render_settings()
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    sc.frame_start, sc.frame_end = 1, NF; sc.render.fps = FPS
    sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = .5
    for o in (sc.cycles, sc.render):
        if hasattr(o, 'motion_blur_position'): o.motion_blur_position = 'START'
    # a tall soft strip that sweeps across the stamped mark in shot 6
    Ls = bpy.data.lights.new('sweep', 'AREA'); Ls.shape = 'RECTANGLE'; Ls.size, Ls.size_y = 26, 420; Ls.color = (1, .9, .8)
    sw = bpy.data.objects.new('sweep', Ls); sc.collection.objects.link(sw); sw.visible_camera = False
    # the phone's glass: no studio light reflects in it (a black flag, as on a real set) — it only mirrors the room
    flag = bpy.data.collections.new('screen_flag')
    for ob in IR['phone'].children_recursive:
        if ob.name.startswith('phone_screen'): flag.objects.link(ob)
    for L in [o for o in sc.objects if o.type == 'LIGHT']:
        if L.light_linking.receiver_collection is None:
            L.light_linking.receiver_collection = flag
    for co in flag.collection_objects: co.light_linking.link_state = 'EXCLUDE'
    R['glint'].data.energy = 0
    G = R['G']; teeth = R['teeth']; flap, fst = R['flap'], R['flap_st']
    sl, piv, cam = R['slider'], R['tab_pivot'], R['cam']
    cam.rotation_mode = 'QUATERNION'; cam.data.dof.focus_object = None
    for ob in IR.values(): ob.rotation_mode = 'QUATERNION'
    bend = {}
    for nm, side in (('strip_0', -1), ('strip_1', 1), ('tape_0', -1), ('tape_1', 1), ('strip_st_0', -1), ('strip_st_1', 1)):
        ob = R[nm][0] if isinstance(R[nm], tuple) else R[nm]
        bend[nm] = (ob, side, [v.co.copy() for v in ob.data.vertices], {})
    teethV, flapV, flapS = {}, {}, {}; prev_q = None
    for f in range(1, NF + 1):
        t = tof(f)
        sx = slider_x(t); sl.location.x = sx; kf(sl, 'location', f, 0)
        g = gape(t)
        if abs(sx - S.SL_PARK) > 1e-3 or g > 0: teethV[f] = S.teeth_verts(sx, g)
        if g > 0:
            for nm, (ob, side, V0, store) in bend.items(): store[f] = [S.gape_point(v, side, g) for v in V0]
        fk = flap_k(t)
        if fk > 1e-4: flapV[f], flapS[f] = flap_verts(fk)
        piv.rotation_euler.y = tab_beta(t, sx, piv.location.z); kf(piv, 'rotation_euler', f, 1)
        R['ring'].rotation_euler.z = .10 * math.sin(2 * math.pi * t / 5.3); kf(R['ring'], 'rotation_euler', f, 2)
        for k, ob in IR.items():
            p, q = item_pose(k, t); ob.location = p; ob.rotation_quaternion = q
            kf(ob, 'location', f); kf(ob, 'rotation_quaternion', f)
        u = seg(t, *T['sweep']); sw.location = (lerp(-90, 190, ss(u)), -230, 40); sw.rotation_euler = (math.radians(90 - 8), 0, math.radians(-10))
        Ls.energy = 2.0e6 * math.sin(math.pi * u) ** 1.2 if 0 < u < 1 else 0.
        kf(sw, 'location', f); Ls.keyframe_insert('energy', frame=f)
        for ff, tt in ((f, t), (f + .5, t + .5 / FPS)):
            st = cam_state(tt, shot_at(t)); q = st['q']
            if prev_q is not None and q.dot(prev_q) < 0: q.negate()
            prev_q = q.copy()
            cam.location = st['eye']; cam.rotation_quaternion = q
            cam.data.lens = st['lens']; cam.data.shift_x = st['shift']; cam.data.dof.aperture_fstop = st['f'] * 1e-3; cam.data.dof.focus_distance = st['fd']
            kf(cam, 'location', ff); kf(cam, 'rotation_quaternion', ff)
            for p in ('lens', 'shift_x', 'dof.focus_distance', 'dof.aperture_fstop'): cam.data.keyframe_insert(p, frame=ff)
    bake_shapes(teeth, teethV, 'zp'); bake_shapes(flap, flapV, 'fl'); bake_shapes(fst, flapS, 'fs')
    for nm, (ob, side, V0, store) in bend.items(): bake_shapes(ob, store, 'gp')
    bpy.ops.wm.save_as_mainfile(filepath=ROOT + '/film2.blend')
    # label anchors: items (bbox bottom) in the hook, feature points in their windows
    out = {}
    for f in range(1, NF + 1):
        t = tof(f); A = {}
        need_items = T['lblItems'][0] - .1 <= t <= T['lblItems'][1] + .1
        feats = [F for F in FEAT if F[4][0] - .1 <= t <= F[4][1] + .1]
        if not need_items and not feats: continue
        sc.frame_set(f)
        if need_items:
            for k in LBL_ITEMS:
                xs, ys, zs = [], [], []
                for ob in IR[k].children_recursive:
                    if ob.type != 'MESH': continue
                    for c in ob.bound_box:
                        v = world_to_camera_view(sc, cam, ob.matrix_world @ Vector(c)); xs.append(v.x * W_); ys.append((1 - v.y) * H_); zs.append(v.z)
                A[k] = [round((min(xs) + max(xs)) / 2, 1), round(max(ys), 1), round(min(zs), 1), round(min(ys), 1)]
        for F in feats:
            v = world_to_camera_view(sc, cam, F[3]); A[F[0]] = [round(v.x * W_, 1), round((1 - v.y) * H_, 1), round(v.z, 1)]
        xs, ys = [], []
        for ob in R['bag_coll'].objects:
            if ob.type != 'MESH': continue
            for c in ob.bound_box:
                v = world_to_camera_view(sc, cam, ob.matrix_world @ Vector(c))
                if v.z > 0: xs.append(v.x * W_); ys.append((1 - v.y) * H_)
        A['bag'] = [round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))]
        out[f] = A
    json.dump(dict(T=T, CUT=CUT, FPS=FPS, NF=NF, feat=[[F[0], F[1], F[2], F[4][0], F[4][1]] for F in FEAT],
                   items=LBL_ITEMS, anchors=out), open(ROOT + '/anchors2.json', 'w'), ensure_ascii=False)
    # sound cues on the same clock
    ev = [dict(t=.05, type='creak', g=.5), dict(t=.2, type='hiss', d=3.4)]
    for k, t2 in INTO.items(): ev.append(dict(t=round(t2, 3), type='swooshR', g=.45)); ev.append(dict(t=round(t2 + T_DROP - .05, 3), type='tick'))
    ev += [dict(t=T['gapeClose'][1], type='creak', g=.8), dict(t=T['zipClose'][0], type='ringtick'),
           dict(t=T['zipClose'][0], type='zip', d=round(T['zipClose'][1] - T['zipClose'][0], 3)), dict(t=T['zipClose'][1], type='thock', g=.45),
           dict(t=T['flapUp'][0], type='creak', g=.7)]
    for k, (t0, t1, t2, home) in CARDS.items(): ev.append(dict(t=t0 + .1, type='swoosh', g=.4)); ev.append(dict(t=t2 - .05, type='slide', g=.6))
    ev += [dict(t=T['flapDown'][1], type='thock', g=.7), dict(t=CUT[4] + .05, type='dive', d=1.6)]
    ev += [dict(t=F[4][0] + .05, type='tick') for F in FEAT]
    ev += [dict(t=T['sweep'][0], type='hiss', d=round(T['sweep'][1] - T['sweep'][0], 3)), dict(t=T['card'], type='card')]
    json.dump(dict(dur=DUR, ev=sorted(ev, key=lambda e: e['t'])), open(ROOT + '/audio/events2.json', 'w'), indent=0)
    print('BAKED', NF, 'frames;', len(teethV), 'zip;', len(flapV), 'flap;', len(out), 'anchor frames')

if __name__ == '__main__':
    main()
