# What goes in the bag: a phone, two cards, folded cash, a folded letter, keys. All generic (no real brand, no real
# currency, no numbers or readable text); sizes are real-world so the bag's capacity reads honestly. 1 unit = 1 mm.
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector, Matrix
from geo import *
import mats as MT

TEX = ROOT + '/maps'
PRINT_SIDE = (0, 2)          # (b>0 face, b<0 face): which profile face carries the print (0) and which is blank (2)

def _bsdf(name, col, rough, metal=0., coat=0., coat_r=.1, spec=.5):
    m, nt, b = MT._new(name)
    b.inputs['Base Color'].default_value = col; b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = coat_r; b.inputs['Specular IOR Level'].default_value = spec
    return m, nt, b

def _img_mat(name, img, rough, sheen=0., bumpk=0.):
    m, nt, b = MT._new(name)
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'mm'
    mp = nt.nodes.new('ShaderNodeMapping'); nt.links.new(uvn.outputs[0], mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (1 / img['du'], 1 / img['dv'], 1); mp.inputs['Location'].default_value = (-img['u0'] / img['du'], -img['v0'] / img['dv'], 0)
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img['img']; tx.extension = 'EXTEND'; nt.links.new(mp.outputs[0], tx.inputs['Vector'])
    nt.links.new(tx.outputs[0], b.inputs['Base Color']); b.inputs['Roughness'].default_value = rough
    b.inputs['Sheen Weight'].default_value = sheen
    # paper fibre: a whisper of bump
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.2; nz.inputs['Detail'].default_value = 3
    nt.links.new(uvn.outputs[0], nz.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .25; bp.inputs['Distance'].default_value = .03
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

PRINTED = ROOT + '/tex/printed'
def _load_rgb(name, u0, u1, v0, v1):
    """a PNG from printed.py, laid out so the image spans (u0..u1) x (v0..v1); PNG top = v1"""
    img = bpy.data.images.load(f'{PRINTED}/{name}.png', check_existing=True); img.colorspace_settings.name = 'sRGB'
    return dict(img=img, u0=u0, v0=v0, du=u1 - u0, dv=v1 - v0)

def _save_rgb(name, A, u0, u1, v0, v1):
    """A: (h, w, 3) float sRGB-ish 0..1, row 0 = v0 (bottom)"""
    os.makedirs(TEX, exist_ok=True); h, w, _ = A.shape
    img = bpy.data.images.new(name, w, h, alpha=False)
    px = np.ones((h, w, 4), np.float32); px[..., :3] = A; img.pixels.foreach_set(px.ravel())
    p = f'{TEX}/{name}.png'; img.filepath_raw = p; img.file_format = 'PNG'; img.save()
    img.source = 'FILE'; img.filepath = p; img.reload()
    return dict(img=img, u0=u0, v0=v0, du=u1 - u0, dv=v1 - v0)

# ---------------------------------------------------------------- printed surfaces (generic, unreadable)
def note_texture():
    """a generic banknote: tinted paper, guilloche rosettes, a frame, a blank watermark oval — no text, no numbers"""
    u0, u1, v0, v1, ppm = -35., 35., 0., 152., 8
    w, h = int((u1 - u0) * ppm), int((v1 - v0) * ppm)
    a = (np.arange(w) + .5) / ppm + u0; s = (np.arange(h) + .5) / ppm + v0; A, S = np.meshgrid(a, s)
    base = np.stack([.70 + 0 * A, .74 + 0 * A, .62 + 0 * A], -1)
    def ros(cx, cy, r0, k):
        dx, dy = S - cx, A - cy; r = np.hypot(dx, dy); th = np.arctan2(dy, dx)
        g = np.cos(k * th + r * .9) * np.cos(r * 1.7 - 3 * np.sin(5 * th))
        return np.exp(-((r - r0) / (r0 * .55)) ** 2) * (g * .5 + .5)
    ink = .55 * ros(38, 0, 16, 11) + .55 * ros(114, 0, 16, 13)
    lines = (np.sin(S * 2.2 + 4 * np.sin(A * .21)) * .5 + .5) * .12
    fr = ((np.abs(A) > 30.5) & (np.abs(A) < 32)) | (((S % 76) > 2.5) & ((S % 76) < 3.6)) | (((S % 76) > 72.4) & ((S % 76) < 73.5))
    oval = np.exp(-(((S - 114) / 12) ** 2 + (A / 15) ** 2) * 2)
    t = np.clip(ink + lines + fr * .35, 0, 1)[..., None]
    col = base * (1 - .45 * t) + np.array([.18, .30, .26]) * .0
    col = col * (1 - .25 * t) + oval[..., None] * .06
    return _save_rgb('note', np.clip(col, 0, 1), u0, u1, v0, v1)

def letter_texture():
    """a folded letter: off-white paper with grey bars that read as type from a distance (no real words)"""
    u0, u1, v0, v1, ppm = -74.25, 74.25, 0., 212., 6
    w, h = int((u1 - u0) * ppm), int((v1 - v0) * ppm)
    a = (np.arange(w) + .5) / ppm + u0; s = (np.arange(h) + .5) / ppm + v0; A, S = np.meshgrid(a, s)
    col = np.ones((h, w, 3), np.float32) * np.array([.74, .73, .69], np.float32)
    rng = np.random.default_rng(3); ink = np.zeros((h, w), np.float32)
    def bar(a0, a1, s0, s1, k=1.):
        m = (A > a0) & (A < a1) & (S > s0) & (S < s1); ink[m] = np.maximum(ink[m], k)
    bar(-60, -20, 186, 192, .8)                               # header block
    y = 170.
    while y > 25:
        x = -60.
        while x < 58:
            wl = rng.uniform(4, 14)
            if x + wl > 60: break
            bar(x, x + wl, y, y + 2.2, .55); x += wl + 2.2
        y -= 5.2
        if rng.random() < .12: y -= 5.2
    sig = (np.abs(S - (18 + 4 * np.sin(A * .35))) < .5) & (A > 20) & (A < 55); ink[sig] = .7
    col = col * (1 - .75 * ink[..., None])
    return _save_rgb('letter', np.clip(col, 0, 1), u0, u1, v0, v1)

# ---------------------------------------------------------------- objects
def slab_holes(name, outline, t, r, mats, parent, holes=()):
    """slab in the local XZ plane (thickness along Y) with round through-holes [(x, z, radius)]"""
    ob = slab(name, outline, t, r, mats, parent=parent, res=3)
    for (hx, hy, hr) in holes:
        cut = bpy.data.meshes.new('cut'); bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=hr, radius2=hr, depth=t * 4)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.translate(bm, vec=(hx, 0, hy), verts=bm.verts); bm.to_mesh(cut); bm.free()
        co = bpy.data.objects.new('cut', cut); bpy.context.scene.collection.objects.link(co)
        md = ob.modifiers.new('hole', 'BOOLEAN'); md.object = co; md.operation = 'DIFFERENCE'; md.solver = 'EXACT'
        dg = bpy.context.evaluated_depsgraph_get(); me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.remove(md); old = ob.data; ob.data = me2; bpy.data.meshes.remove(old); bpy.data.objects.remove(co)
    return ob

def phone(M, parent):
    root = empty('it_phone', parent=parent)
    W_, H_, T_ = 71.5, 147.0, 7.8
    out = rrect_pts(W_, H_, 11.0, n=14)
    fr = slab('phone_frame', out, T_, 2.6, [M['ph_frame']], parent=root, res=5); weighted(fr)
    sc = slab('phone_screen', [(x * .965, y * .978) for x, y in out], .3, .12, [M['ph_screen']], parent=root, res=2); sc.location.y = -T_ / 2 + .12
    bk = slab('phone_back', [(x * .97, y * .98) for x, y in out], .3, .12, [M['ph_back']], parent=root, res=2); bk.location.y = T_ / 2 - .12
    bump = slab('phone_bump', rrect_pts(33, 33, 9, n=10), 1.8, .7, [M['ph_back']], parent=root, res=3); weighted(bump)
    bump.location = (17.0, T_ / 2 + .7, 47.0)
    for (x, z, r) in ((24.5, 55.0, 5.6), (24.5, 39.0, 5.6), (9.5, 47.0, 5.6)):
        ring = [Vector((x + r * math.cos(a), T_ / 2 + 2.0, z + r * math.sin(a))) for a in [2 * math.pi * k / 40 for k in range(40)]]
        tube('lens_ring', ring, .55, True, [M['ph_frame']], root, n=10, fixedW=(0, 1, 0))
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=r - .3, radius2=r - .3, depth=1.4)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.translate(bm, vec=(x, T_ / 2 + 1.8, z), verts=bm.verts)
        me = bpy.data.meshes.new('lens'); bm.to_mesh(me); bm.free(); mesh_obj('lens', me, [M['ph_lens']], root)
    for z in (40.0, 53.0):     # side buttons
        b = slab('phone_btn', rrect_pts(2.2, 10.0, 1.0, n=4), 3.0, .6, [M['ph_frame']], parent=root, res=2)
        b.location = (-W_ / 2 + .3, 0, z)
    return root

def card_texture(name, c0, c1, line):
    """card face: diagonal gradient, fine guilloche lines, a thin metallic rule, a contactless mark — no text, no numbers"""
    u0, u1, v0, v1, ppm = -42.8, 42.8, -27.0, 27.0, 12
    w, h = int((u1 - u0) * ppm), int((v1 - v0) * ppm)
    x = (np.arange(w) + .5) / ppm + u0; y = (np.arange(h) + .5) / ppm + v0; X, Y = np.meshgrid(x, y)
    k = np.clip((X + Y * .8 + 40) / 80, 0, 1)[..., None]
    col = np.array(c0) * (1 - k) + np.array(c1) * k
    g = (np.sin((X * .9 + Y * .4) * 1.6 + 2.5 * np.sin(Y * .21 + X * .05)) * .5 + .5) ** 8
    col = col * (1 + .10 * g[..., None])
    rule = (np.abs(Y + 14.5) < .22) & (X > -36) & (X < 36)
    col[rule] = np.array(line)
    cx, cy = 30.0, 8.0; r = np.hypot(X - cx, Y - cy); th = np.arctan2(Y - cy, X - cx)
    arcs = np.zeros_like(r, bool)
    for rr in (2.2, 3.6, 5.0, 6.4): arcs |= (np.abs(r - rr) < .32) & (np.abs(th) < .75)
    col[arcs] = np.array(line) * .9
    return _save_rgb(name, np.clip(col, 0, 1), u0, u1, v0, v1)

def card(M, parent, name, mat):
    root = empty('it_' + name, parent=parent)
    c = slab(name, rrect_pts(85.6, 53.98, 3.18, n=8), .76, .3, [mat, M['card_edge'], mat], parent=root, res=2)
    chip = slab(name + '_chip', rrect_pts(11.5, 9.0, 1.6, n=6), .12, .05, [M['chip']], parent=root, res=1)
    chip.location = (-27.0, -.40, 2.0)
    return root

def note_texture(name, tint, ink):
    """a generic banknote: tinted paper, guilloche rosettes, a frame, a blank watermark oval — no text, no numbers"""
    u0, u1, v0, v1, ppm = -35., 35., 0., 151., 8
    w, h = int((u1 - u0) * ppm), int((v1 - v0) * ppm)
    a = (np.arange(w) + .5) / ppm + u0; s = (np.arange(h) + .5) / ppm + v0; A, S = np.meshgrid(a, s)
    def ros(cx, cy, r0, k):
        dx, dy = S - cx, A - cy; r = np.hypot(dx, dy); th = np.arctan2(dy, dx)
        g = np.cos(k * th + r * .9) * np.cos(r * 1.7 - 3 * np.sin(5 * th))
        return np.exp(-((r - r0) / (r0 * .55)) ** 2) * (g * .5 + .5)
    t = .75 * ros(40, -4, 15, 11) + .45 * ros(118, 8, 9, 7)
    t += (np.sin(S * 2.4 + 4 * np.sin(A * .21)) * .5 + .5) ** 3 * .35 * ((np.abs(A) > 24) | (S < 12) | (S > 139))
    fr = ((np.abs(np.abs(A) - 31.5) < .5) & (S > 3) & (S < 148)) | ((np.abs(S - 3.5) < .5) | (np.abs(S - 147.5) < .5)) & (np.abs(A) < 32)
    t += fr * .8
    band = (S > 70) & (S < 74) & (np.abs(A) < 31); t += band * .35
    oval = np.exp(-(((S - 118) / 13) ** 2 + (A / 16) ** 2) * 2.5)
    t = np.clip(t, 0, 1)[..., None]
    col = np.array(tint) * (1 - t) + np.array(ink) * t
    col = col + oval[..., None] * .05
    return _save_rgb(name, np.clip(col, 0, 1), u0, u1, v0, v1)

def note(name, mat, parent, curl=3.0):
    P = [Vector((-75.5 + 151 * k / 60, 0, curl * math.sin(math.pi * k / 60))) for k in range(61)]
    fr = frames_for(P, fixedW=(0, 1, 0))
    prof = support(rr_profile(70, .14, .06, n=1))
    return sweep2(name, fr, lambda i: prof, mats=[mat], parent=parent)

def cash(M, parent):
    root = empty('it_cash', parent=parent)
    for k, (ang, dz) in enumerate(((-5, 0.0), (0, .35), (5, .7))):
        piv = empty('note_piv%d' % k, (-60, 0, dz), root); piv.rotation_euler.z = math.radians(ang)
        n = note('note%d' % k, M['note%d' % k], piv); n.location = (60, 0, 0)
    return root

def folded(name, length, width, t, gap, mats, parent, open_deg=6.0, step=.8, mat_fn=None):
    """a sheet folded in half: bottom leaf, a round fold, top leaf slightly open; UV (a, s) runs across the whole sheet"""
    rf = gap / 2 + t / 2; P = []
    for k in range(int(length / step) + 1): P.append(Vector((-length / 2 + k * step, 0, -rf)))
    for k in range(1, 12):
        a = -math.pi / 2 + math.pi * k / 12; P.append(Vector((length / 2 + rf * math.cos(a) * .0 + rf * math.cos(a), 0, rf * math.sin(a))))
    oa = math.radians(open_deg)
    for k in range(int(length / step) + 1):
        d = k * step; P.append(Vector((length / 2 - d * math.cos(oa), 0, rf + d * math.sin(oa))))
    fr = frames_for(P, fixedW=(0, 1, 0))
    prof = support(rr_profile(width, t, t * .45, n=2))
    return sweep2(name, fr, lambda i: prof, mats=mats, parent=parent, mat_fn=mat_fn(prof) if mat_fn else None)

def key_outline(kind):
    """CCW outline in (x, y), blade pointing down (-y); returns outline and the bow hole (x, y, r)"""
    if kind == 0:   # house key: round bow, straight blade with cuts on one side
        bow = [(13 * math.cos(a), 15 + 13 * math.sin(a)) for a in [math.radians(-60 + 300 * k / 40) for k in range(41)]]
        cuts = [(4.4, -38), (4.4, -34), (2.2, -31.5), (4.4, -29), (4.4, -25), (2.0, -22.5), (4.4, -20), (4.4, -15.5), (2.4, -13), (4.4, -10.5)]
        return [(4.4, 4.0)] + bow + [(-4.4, 4.0), (-4.4, -36), (-1.5, -41)] + cuts, (0., 19.5, 3.4)
    def se(a):
        c, s_ = math.cos(a), math.sin(a)
        return (10 * math.copysign(abs(c) ** .45, c), 12 + 8 * math.copysign(abs(s_) ** .45, s_))
    bow = [se(math.radians(-48 + 276 * k / 40)) for k in range(41)]
    cuts = [(3.6, -27.5), (3.6, -24), (1.8, -21.5), (3.6, -19), (3.6, -15), (1.6, -12.5), (3.6, -10)]
    return [(3.6, 4.4)] + bow + [(-3.6, 4.4), (-3.6, -26), (-1.0, -30)] + cuts, (0., 14.0, 3.0)

def keys(M, parent):
    root = empty('it_keys', parent=parent)
    ring = [Vector((13 * math.cos(a), 0, 13 * math.sin(a))) for a in [2 * math.pi * k / 64 for k in range(64)]]
    tube('key_ring', ring, .85, True, [M['steel']], root, n=10, fixedW=(0, 1, 0))
    for kind, mat, dl, yo in ((0, M['nickel'], -16.0, -.9), (1, M['brass_key'], 21.0, 1.2)):
        o, (hx, hy, hr) = key_outline(kind)
        k = slab_holes('key%d' % kind, o, 2.2 if kind == 0 else 2.0, .45, [mat], root, holes=[(hx, hy, hr)])
        d = math.radians(dl); beta = -d
        rp = Vector((13 * math.sin(d), yo, -13 * math.cos(d)))          # where the ring wire passes through the hole
        k.rotation_euler = (0, beta, 0)
        k.location = rp - Matrix.Rotation(beta, 3, 'Y') @ Vector((hx, 0, hy - hr + .85))
    # the fob: a brushed metal tag on its own little link
    fo = [(x, y - 17.0) for x, y in rrect_pts(19.0, 34.0, 5.0, n=8)]
    tag = slab_holes('key_fob', fo, 2.4, .6, [M['fob']], root, holes=[(0., -4.5, 2.4)])
    d = math.radians(-58); beta = -d; rp = Vector((13 * math.sin(d), 2.1, -13 * math.cos(d)))
    tag.rotation_euler = (0, beta, 0)
    tag.location = rp - Matrix.Rotation(beta, 3, "Y") @ Vector((0., 0, -4.5 + 2.4 - .85))
    return root

def materials(M):
    m, nt, b = _bsdf('ph_frame', (.10, .10, .105, 1), .42, metal=1.); M['ph_frame'] = m
    b.inputs['Anisotropic'].default_value = .4
    m, nt, b = _bsdf('ph_back', (.020, .021, .023, 1), .62, coat=0.); M['ph_back'] = m
    m, nt, b = _bsdf('ph_screen', (.004, .004, .005, 1), .32, coat=0., spec=.18); M['ph_screen'] = m      # matte glass: no white slabs
    m, nt, b = _bsdf('ph_lens', (.0, .0, .0, 1), .02, coat=1., coat_r=.01); M['ph_lens'] = m
    def cardmat(name, tex):
        m = _img_mat(name, tex, .32); b = m.node_tree.nodes['Principled BSDF'] if 'Principled BSDF' in m.node_tree.nodes else [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
        b.inputs['Coat Weight'].default_value = .7; b.inputs['Coat Roughness'].default_value = .08; return m
    M['card_black'] = cardmat('card_black', card_texture('card_black', (.035, .045, .085), (.006, .007, .012), (.75, .62, .38)))
    M['card_green'] = cardmat('card_grey', card_texture('card_grey', (.20, .20, .21), (.07, .07, .075), (.82, .82, .80)))
    m, nt, b = _bsdf('chip', (.80, .62, .30, 1), .22, metal=1.); M['chip'] = m
    tc = nt.nodes.new('ShaderNodeTexCoord'); bk = nt.nodes.new('ShaderNodeTexBrick'); bk.inputs['Scale'].default_value = .22
    bk.inputs['Mortar Size'].default_value = .02; nt.links.new(tc.outputs['Object'], bk.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .5; bp.inputs['Distance'].default_value = .05
    nt.links.new(bk.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    m, nt, b = _bsdf('steel', (.62, .62, .63, 1), .18, metal=1.); M['steel'] = m
    m, nt, b = _bsdf('nickel', (.70, .69, .66, 1), .2, metal=1.); M['nickel'] = m
    m, nt, b = _bsdf('brass_key', (.72, .54, .27, 1), .24, metal=1.); M['brass_key'] = m
    for i in range(3): M['note%d' % i] = _img_mat('note%d' % i, _load_rgb('note%d' % i, -35., 35., 0., 151.), .72, sheen=.2)
    M['card_edge'] = _bsdf('card_edge', (.05, .05, .055, 1), .4)[0]
    m, nt, b = _bsdf('paper_blank', (.56, .55, .50, 1), .82); b.inputs['Sheen Weight'].default_value = .3; M['paper_blank'] = m
    M['letter'] = _img_mat('letter', _load_rgb('letter', -74.25, 74.25, 0., 212.), .82, sheen=.3)
    m, nt, b = _bsdf('fob', (.70, .50, .24, 1), .2, metal=1.); M['fob'] = m
    b.inputs['Anisotropic'].default_value = .5

def build(M, parent=None):
    materials(M); R = {}
    R['phone'] = phone(M, parent)
    R['card1'] = card(M, parent, 'card1', M['card_black']); R['card2'] = card(M, parent, 'card2', M['card_green'])
    R['cash'] = cash(M, parent)
    r = empty('it_letter', parent=parent)   # printed on one side only: the back of the sheet is plain paper
    folded('letter', 105.0, 148.5, .42, .15, [M['letter'], M['paper_blank'], M['paper_blank']], r, open_deg=4, mat_fn=prof_mat(148.5, .42 * .45, edge=1, front=PRINT_SIDE[0], back=PRINT_SIDE[1])); R['letter'] = r
    R['keys'] = keys(M, parent)
    return R
