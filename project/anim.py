# «HAMZA» — the bag film: the leather, the stamped mark, the bag opening and everything it carries floating out,
# then back in. Bakes all motion (keyframes + shape keys) into film.blend and the label anchors into anchors.json.
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy, sys, math, json
from mathutils import Vector, Quaternion, Matrix, Euler
sys.path.insert(0, ROOT)
import scene as S, items as IT
from bpy_extras.object_utils import world_to_camera_view

FPS, DUR = 24, 32.0
NF = int(DUR * FPS)
tof = lambda f: (f - 1) / FPS
clamp = lambda x, a=0., b=1.: max(a, min(b, x))
lerp = lambda a, b, t: a + (b - a) * t
seg = lambda t, a, b: clamp((t - a) / (b - a))
ss = lambda t: (lambda u: u * u * (3 - 2 * u))(clamp(t))
eio = lambda t: (lambda u: 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2)(clamp(t))
eo = lambda t: 1 - (1 - clamp(t)) ** 3
ei = lambda t: clamp(t) ** 3
BEAT = 2 / 3; b = lambda n: round(n * BEAT, 4); BAR = 4 * BEAT

# ---------------------------------------------------------------- timeline (90 BPM, 12 bars)
T = dict(
    zipOpen=(b(12.5), b(14.5)), tabOpen=(b(12.5), b(13.0)), gapeOpen=(b(14.4), b(15.6)),
    gapeClose=(b(31.0), b(31.9)), zipClose=(b(32.1), b(33.6)), tabClose=(b(32.1), b(32.6)),
    sweep=(b(4.4), b(7.8)), glint=(b(36.2), b(39.6)), card=b(40), final=b(44),
    lblHero=(b(9.0), b(12.0) - .05), itemLblOut=b(28) - .05,
)
ITEMS = [   # key, leaves the bag, settles, starts back, home
    ('phone',  b(16.2), b(18.0), b(29.2), b(30.6)),
    ('letter', b(17.0), b(18.9), b(28.9), b(30.3)),
    ('keys',   b(17.8), b(19.6), b(28.6), b(30.0)),
    ('card1',  b(18.6), b(20.4), b(28.3), b(29.7)),
    ('card2',  b(19.0), b(20.8), b(28.15), b(29.55)),
    ('cash',   b(19.6), b(21.4), b(28.0), b(29.4)),
]
LBL_ITEMS = {'phone': 'جوال', 'letter': 'أوراق', 'keys': 'مفاتيح', 'card1': 'بطاقات', 'cash': 'نقود'}

def Q(rx=0, ry=0, rz=0, pre=None):
    m = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), 'XYZ').to_matrix()
    if pre is not None: m = m @ pre
    return m.to_quaternion()
RZ90 = Matrix.Rotation(math.pi / 2, 3, 'Z')
INSIDE = {
    'phone':  (Vector((0, -9.5, 62)),   Q(0, 90, 0)),
    'letter': (Vector((0, 3.0, 60)),    Q(90, 0, 0, RZ90)),
    'keys':   (Vector((56, 14, 26)),    Q(0, 0, 0)),
    'card1':  (Vector((-30, 13.5, 36)), Q(0, 0, 0)),
    'card2':  (Vector((-24, 15.2, 38)), Q(0, 4, 0)),
    'cash':   (Vector((10, 17.0, 48)),  Q(90, 0, 0)),
}
SHOW = {
    'phone':  (Vector((-188, -46, 168)), Q(-6, -14, 196)),
    'letter': (Vector((-84, -30, 236)),  Q(80, -6, 6, RZ90)),
    'keys':   (Vector((38, -70, 236)),   Q(4, 14, -8)),
    'card1':  (Vector((150, -60, 200)),  Q(-6, -16, -8)),
    'card2':  (Vector((168, -50, 210)),  Q(-6, 8, -14)),
    'cash':   (Vector((196, -44, 86)),   Q(82, 4, -8)),
}
LIFT = 175.0          # every item leaves the bag straight up through the opening before it flies to its place

def item_pose(k, t):
    _, t0, t1, t2, t3 = next(i for i in ITEMS if i[0] == k)
    p_in, q_in = INSIDE[k]; p_sh, q_sh = SHOW[k]
    p_mid = Vector((p_in.x, 0, p_in.z)); p_up = Vector((p_in.x * .85, 0, LIFT))
    def path(u):       # 0 inside → 1 shown
        if u < .38:
            v = u / .38; a = p_in.lerp(p_mid, ss(v * 2.2)); return a.lerp(p_up, eio(v)), q_in
        v = (u - .38) / .62; w = eio(v); c = p_up + Vector((0, 0, 40))
        p = (1 - w) ** 2 * p_up + 2 * (1 - w) * w * c + w * w * p_sh
        return p, q_in.slerp(q_sh, ss(v * 1.15))
    if t <= t0: u = 0.
    elif t < t1: u = clamp((t - t0) / (t1 - t0))
    elif t < t2: u = 1.
    elif t < t3: u = 1 - clamp((t - t2) / (t3 - t2))
    else: u = 0.
    p, q = path(u)
    if t1 <= t <= t2:
        h = (sum(map(ord, k)) % 97) / 97.0                       # gentle float while shown
        fl = ss(seg(t, t1, t1 + .6)) * (1 - ss(seg(t, t2 - .3, t2)))
        p = p + Vector((0, 0, 2.2 * math.sin(2 * math.pi * (t * .42 + h)))) * fl
        q = Quaternion((0, 0, 1), .025 * math.sin(2 * math.pi * (t * .31 + h)) * fl) @ q
    return p, q

def slider_x(t):
    o, c = eio(seg(t, *T['zipOpen'])), eio(seg(t, *T['zipClose']))
    return lerp(lerp(S.SL_PARK, -S.SL_PARK, o), S.SL_PARK, c)
def gape(t):
    return eio(seg(t, *T['gapeOpen'])) * (1 - eio(seg(t, *T['gapeClose'])))
def tab_beta(t, sx, pz):
    right = S.tab_angle(sx, pz); left = -math.pi - S.tab_angle(-sx, pz)
    k = ss(seg(t, *T['tabOpen'])) * (1 - ss(seg(t, *T['tabClose'])))
    return lerp(right, left, k)
SEAM = None
def glint_state(t):
    gk = seg(t, *T['glint'])
    if gk <= 0 or gk >= 1: return None, 0.
    pts, L = SEAM; u = (.12 + gk) % 1.0; p = pts[int(u * len(pts)) % len(pts)][0]
    return Vector((p.x, -S.BD / 2 - 3.2, p.y + S.BH / 2)), 1.2e4 * math.sin(math.pi * gk) ** 1.5

# ---------------------------------------------------------------- camera
def orbit(tgt, az, el, d):
    a, e = math.radians(az), math.radians(el); t = Vector(tgt)
    return t + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * d
LOGO_W = Vector((42.0, -39.15, 33.0))
SHOTS = [
    # 1 · the leather: a slow slide along the stitched bottom corner, raking light
    (0.0, BAR, lambda: [
        (0.0, orbit((-74, -25, 14), -30, 7, 250), (-74, -25, 14), 100, 11, (-74, -25.5, 10), 0),
        (BAR, orbit((-34, -25, 12), -18, 6, 236), (-34, -25, 12), 100, 11, (-34, -25.5, 8), 0)]),
    # 2 · the stamped mark, a light sweeps across it
    (BAR, 2 * BAR, lambda: [
        (BAR, orbit(LOGO_W, 14, 8, 300), LOGO_W, 100, 11, LOGO_W, 0),
        (2 * BAR, orbit(LOGO_W + Vector((2, 0, 0)), 4, 6, 262), LOGO_W + Vector((2, 0, 0)), 100, 11, LOGO_W, 0)]),
    # 3 · the whole bag
    (2 * BAR, 3 * BAR, lambda: [
        (2 * BAR, orbit((-12, -14, 56), -34, 14, 720), (-12, -14, 56), 70, 11, (-6, -25, 56), .13),
        (3 * BAR, orbit((-12, -14, 56), -20, 13, 680), (-12, -14, 56), 70, 11, (-6, -25, 56), .13)]),
    # 4 · the zip runs, the mouth opens
    (3 * BAR, 4 * BAR, None),
    # 5 · everything it holds floats out and settles around it
    (4 * BAR, b(28), lambda: [
        (4 * BAR, orbit((0, -6, 118), -12, 15, 700), (0, -6, 118), 42, 16, (0, -30, 120), 0),
        (b(21), orbit((0, -10, 120), -4, 11, 790), (0, -10, 120), 42, 16, (0, -45, 140), 0),
        (b(28), orbit((0, -10, 120), 6, 10, 770), (0, -10, 120), 42, 16, (0, -45, 140), 0)]),
    # 6 · back in
    (b(28), b(32), lambda: [
        (b(28), orbit((0, -8, 110), 18, 17, 760), (0, -8, 110), 45, 16, (0, -20, 110), 0),
        (b(32), orbit((0, -6, 96), 10, 19, 640), (0, -6, 96), 45, 16, (0, -15, 100), 0)]),
    # 7 · the zip closes
    (b(32), b(36), None),
    # 8 · the bag, the thread, the mark
    (b(36), DUR + .5, lambda: [
        (b(36), orbit((-24, -14, 55), -22, 12, 960), (-24, -14, 55), 70, 11, (-14, -25, 55), .2),
        (DUR + .5, orbit((-24, -14, 55), 10, 10, 900), (-24, -14, 55), 70, 11, (-14, -25, 55), .2)]),
]
def zip_keys(opening):
    K = []
    if opening:
        for tt in [3 * BAR, 8.4, 8.8, 9.2, 9.6, 10.0, 4 * BAR]:
            sx = slider_x(tt); tx = lerp(74, -10, eio(seg(tt, 8.2, 9.9)))
            tg = Vector((tx, -4, 121)); fx = lerp(sx, 0, ss(seg(tt, 9.6, 10.2)))
            K.append((tt, orbit(tg, -20, 58, 400 + 40 * seg(tt, 9.6, 10.7)), tg, 85, 11, Vector((fx, -4, 121)), 0))
    else:
        for tt in [b(32), 21.6, 22.0, 22.4, 22.8, b(36)]:
            sx = slider_x(tt); tx = lerp(-60, 70, eio(seg(tt, 21.3, 22.6)))
            tg = Vector((tx, -2, 120)); K.append((tt, orbit(tg, 22, 54, 420), tg, 85, 11, Vector((sx, 0, 121)), 0))
    return K

def _cr(keys, t, j):
    ts = [k[0] for k in keys]; vs = [k[j] for k in keys]
    vs = [Vector(v) if isinstance(v, (tuple, Vector)) else v for v in vs]
    if t <= ts[0]: i = 0
    elif t >= ts[-1]: i = len(ts) - 2
    else: i = max(k for k in range(len(ts) - 1) if ts[k] <= t)
    t0, t1 = ts[i], ts[i + 1]; u = (t - t0) / (t1 - t0)
    p1, p2 = vs[i], vs[i + 1]
    p0 = vs[i - 1] if i > 0 else p1 - (p2 - p1)
    p3 = vs[i + 2] if i + 2 < len(vs) else p2 + (p2 - p1)
    d0 = (t1 - (ts[i - 1] if i > 0 else t0 - (t1 - t0))); d1 = ((ts[i + 2] if i + 2 < len(ts) else t1 + (t1 - t0)) - t0)
    m1 = (p2 - p0) * ((t1 - t0) / d0); m2 = (p3 - p1) * ((t1 - t0) / d1)
    h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return p1 * h00 + m1 * h10 + p2 * h01 + m2 * h11
def shot_at(t):
    for k, (t0, t1, kf) in enumerate(SHOTS):
        if t0 - 1e-9 <= t < t1 or k == len(SHOTS) - 1: return k
def cam_state(t, k=None):
    k = shot_at(t) if k is None else k
    t0, t1, kf = SHOTS[k]; keys = zip_keys(k == 3) if kf is None else kf()
    eye, tg = _cr(keys, t, 1), _cr(keys, t, 2)
    lens, fst, foc, sh = _cr(keys, t, 3), _cr(keys, t, 4), _cr(keys, t, 5), _cr(keys, t, 6)
    fwd = (tg - eye).normalized(); q = fwd.to_track_quat('-Z', 'Y')
    return dict(eye=eye, q=q, lens=lens, f=fst, fd=max(5., (Vector(foc) - eye).dot(fwd)), shift=sh, shot=k)

# ---------------------------------------------------------------- baking helpers
def kf(ob, path, f, idx=-1): ob.keyframe_insert(data_path=path, frame=f, index=idx)
def bake_shapes(ob, frame_verts, tag):
    if not frame_verts: return
    if not ob.data.shape_keys: ob.shape_key_add(name='basis', from_mix=False)
    keys, use = {}, {}
    for f in sorted(frame_verts):
        V = frame_verts[f]; h = hash(tuple(round(c, 3) for v in V[::5] for c in v))
        if h not in keys:
            sk = ob.shape_key_add(name='%s%03d' % (tag, f), from_mix=False)
            sk.data.foreach_set('co', [c for v in V for c in v]); keys[h] = sk
        use.setdefault(h, []).append(f)
    for h, fs in use.items():
        sk = keys[h]; runs = []; a = fs[0]; p = fs[0]
        for f in fs[1:]:
            if f != p + 1: runs.append((a, p)); a = f
            p = f
        runs.append((a, p))
        for a, z in runs:
            for f, v in ((a - 1, 0.), (a, 1.), (z, 1.), (z + 1, 0.)):
                sk.value = v; sk.keyframe_insert('value', frame=f)

def main():
    global SEAM
    S.build(); R = S.R; sc = bpy.context.scene; M = R['M']
    IR = IT.build(M); R['items'] = IR
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    sc.frame_start, sc.frame_end = 1, NF; sc.render.fps = FPS
    sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = .5
    for o in (sc.cycles, sc.render):
        if hasattr(o, 'motion_blur_position'): o.motion_blur_position = 'START'
    SEAM = S.resample(S.offset_poly(S.rrect_pts(S.BW, S.BH, S.BR, n=16), -4.4), 2.0, closed=True)
    # a tall soft strip that sweeps across the stamped mark in shot 2
    Ls = bpy.data.lights.new('sweep', 'AREA'); Ls.shape = 'RECTANGLE'; Ls.size, Ls.size_y = 26, 420; Ls.color = (1, .9, .8)
    sw = bpy.data.objects.new('sweep', Ls); sc.collection.objects.link(sw); sw.visible_camera = False
    G = R['G']; teeth = R['teeth']
    sl, piv, glint, cam = R['slider'], R['tab_pivot'], R['glint'], R['cam']
    cam.rotation_mode = 'QUATERNION'; cam.data.dof.focus_object = None
    for ob in IR.values(): ob.rotation_mode = 'QUATERNION'
    bend = {}
    for nm, side in (('strip_0', -1), ('strip_1', 1), ('tape_0', -1), ('tape_1', 1), ('strip_st_0', -1), ('strip_st_1', 1)):
        ob = R[nm][0] if isinstance(R[nm], tuple) else R[nm]
        bend[nm] = (ob, side, [v.co.copy() for v in ob.data.vertices], {})
    teethV = {}; prev_q = None
    for f in range(1, NF + 1):
        t = tof(f)
        sx = slider_x(t); sl.location.x = sx; kf(sl, 'location', f, 0)
        g = gape(t)
        if abs(sx - S.SL_PARK) > 1e-3 or g > 0: teethV[f] = S.teeth_verts(sx, g)
        if g > 0:
            for nm, (ob, side, V0, store) in bend.items(): store[f] = [S.gape_point(v, side, g) for v in V0]
        piv.rotation_euler.y = tab_beta(t, sx, piv.location.z); kf(piv, 'rotation_euler', f, 1)
        R['ring'].rotation_euler.z = .10 * math.sin(2 * math.pi * t / 5.3); kf(R['ring'], 'rotation_euler', f, 2)
        for k, ob in IR.items():
            p, q = item_pose(k, t); ob.location = p; ob.rotation_quaternion = q
            kf(ob, 'location', f); kf(ob, 'rotation_quaternion', f)
        gp, ge = glint_state(t)
        if gp is not None: glint.location = gp
        glint.data.energy = ge; kf(glint, 'location', f); glint.data.keyframe_insert('energy', frame=f)
        u = seg(t, *T['sweep']); sw.location = (lerp(-90, 190, ss(u)), -230, 40); sw.rotation_euler = (math.radians(90 - 8), 0, math.radians(-10))
        Ls.energy = 2.4e6 * math.sin(math.pi * u) ** 1.2 if 0 < u < 1 else 0.
        kf(sw, 'location', f); Ls.keyframe_insert('energy', frame=f)
        for ff, tt in ((f, t), (f + .5, t + .5 / FPS)):
            st = cam_state(tt, shot_at(t)); q = st['q']
            if prev_q is not None and q.dot(prev_q) < 0: q.negate()
            prev_q = q.copy()
            cam.location = st['eye']; cam.rotation_quaternion = q
            cam.data.lens = st['lens']; cam.data.shift_x = st['shift']; cam.data.dof.aperture_fstop = st['f'] * 1e-3; cam.data.dof.focus_distance = st['fd']
            kf(cam, 'location', ff); kf(cam, 'rotation_quaternion', ff)
            for p in ('lens', 'shift_x', 'dof.focus_distance', 'dof.aperture_fstop'): cam.data.keyframe_insert(p, frame=ff)
    bake_shapes(teeth, teethV, 'zp')
    for nm, (ob, side, V0, store) in bend.items(): bake_shapes(ob, store, 'gp')
    bpy.ops.wm.save_as_mainfile(filepath=ROOT + '/film.blend')
    ANCH = {'hero_leather': (G['front'], Vector((-62, -25.1, 34))), 'hero_stitch': (G['front'], Vector((92, -25.1, 4.6)))}
    out = {}
    for f in range(1, NF + 1):
        t = tof(f)
        if not ((T['lblHero'][0] - .1 <= t <= T['lblHero'][1] + .1) or (b(17) <= t <= T['itemLblOut'] + .1)): continue
        sc.frame_set(f); A = {}
        for k in LBL_ITEMS:
            xs, ys, zs = [], [], []
            for ob in IR[k].children_recursive:
                if ob.type != 'MESH': continue
                for c in ob.bound_box:
                    v = world_to_camera_view(sc, cam, ob.matrix_world @ Vector(c)); xs.append(v.x * 1920); ys.append((1 - v.y) * 1080); zs.append(v.z)
            A[k] = [round((min(xs) + max(xs)) / 2, 1), round(max(ys), 1), round(min(zs), 1)]
        for k, (ob, p) in ANCH.items():
            v = world_to_camera_view(sc, cam, ob.matrix_world @ p); A[k] = [round(v.x * 1920, 1), round((1 - v.y) * 1080, 1), round(v.z, 1)]
        out[f] = A
    json.dump(dict(T=T, items=[[i[0], i[2]] for i in ITEMS], anchors=out), open(ROOT + '/anchors.json', 'w'))
    print('BAKED', NF, 'frames;', len(teethV), 'zip frames')

if __name__ == '__main__':
    main()
