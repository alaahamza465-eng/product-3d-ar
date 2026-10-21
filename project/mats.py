# Materials: scanned leather (ambientCG Leather037, CC0) tinted to burgundy, painted edges, flesh side, waxed thread,
# antique brass, zipper tape, studio floor. All texture lookups use object coordinates (box projection), 1 unit = 1 mm.
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy
T = ROOT + '/tex/L037/Leather037_2K-JPG_'

def _img(path, nc=False):
    im = bpy.data.images.load(path, check_existing=True)
    if nc: im.colorspace_settings.name = 'Non-Color'
    return im

def _new(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    return m, nt, b

def _coords(nt, scale):
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); return mp.outputs[0], tc

def _box(nt, vec, img, blend=.25):
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img; tx.projection = 'BOX'; tx.projection_blend = blend
    nt.links.new(vec, tx.inputs['Vector']); return tx

def _mix(nt, a, b, fac, mode='MIX'):
    m = nt.nodes.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = mode
    if isinstance(fac, float): m.inputs['Factor'].default_value = fac
    else: nt.links.new(fac, m.inputs['Factor'])
    for slot, v in (('A', a), ('B', b)):
        inp = m.inputs[6] if slot == 'A' else m.inputs[7]
        if isinstance(v, tuple): inp.default_value = v
        else: nt.links.new(v, inp)
    return m.outputs[2]

LR3 = ROOT + '/tex/lr3/'
MICRO = False               # stills only: fine scuffs and roughness breakup on the grain
TINT = (.55, .36, 1.55)     # dark burgundy (عنّابي داكن); v1 was (.62, .50, 1.6)
def leather(name='leather', detail=None, scale=1 / 140, nstr=.85, coat=.25, tint=None, bump=.06):
    """Poly Haven leather_red_03 scan (CC0) on the part's own UV (mm), regraded to burgundy; optional height detail map"""
    tint = TINT if tint is None else tint
    m, nt, b = _new(name)
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'mm'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, 1); nt.links.new(uvn.outputs[0], mp.inputs['Vector'])
    def tex(f, nc):
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = _img(LR3 + f, nc); t.interpolation = 'Linear'; nt.links.new(mp.outputs[0], t.inputs['Vector']); return t
    col, rough, nor = tex('coll1_clean.jpg', False), tex('rough.jpg', True), tex('nor_gl.jpg', True)
    tn = nt.nodes.new('ShaderNodeVectorMath'); tn.operation = 'MULTIPLY'; tn.inputs[1].default_value = tint
    nt.links.new(col.outputs[0], tn.inputs[0])
    # slow pull-up variation, large soft patches a little lighter / darker
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = .012; nz.inputs['Detail'].default_value = 2
    nt.links.new(uvn.outputs[0], nz.inputs['Vector'])
    vr = nt.nodes.new('ShaderNodeMapRange'); vr.inputs['From Min'].default_value = .35; vr.inputs['From Max'].default_value = .65
    vr.inputs['To Min'].default_value = .86; vr.inputs['To Max'].default_value = 1.14; nt.links.new(nz.outputs['Fac'], vr.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeVectorMath'); mul.operation = 'SCALE'; nt.links.new(tn.outputs[0], mul.inputs[0]); nt.links.new(vr.outputs[0], mul.inputs['Scale'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr; nt.links.new(nor.outputs[0], nm.inputs['Color'])
    bp = nt.nodes.new('ShaderNodeBump'); nt.links.new(nm.outputs[0], bp.inputs['Normal'])
    colour = mul.outputs[0]
    if detail:
        m2 = nt.nodes.new('ShaderNodeMapping'); du, dv = detail['u1'] - detail['u0'], detail['v1'] - detail['v0']
        m2.inputs['Scale'].default_value = (1 / du, 1 / dv, 1); m2.inputs['Location'].default_value = (-detail['u0'] / du, -detail['v0'] / dv, 0)
        nt.links.new(uvn.outputs[0], m2.inputs['Vector'])
        dt = nt.nodes.new('ShaderNodeTexImage'); dt.image = detail['img']; dt.interpolation = 'Cubic'; dt.extension = 'EXTEND'
        nt.links.new(m2.outputs[0], dt.inputs['Vector'])
        sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(dt.outputs[0], sep.inputs[0])
        bp.inputs['Strength'].default_value = 1.0; bp.inputs['Distance'].default_value = 1.0
        nt.links.new(sep.outputs[0], bp.inputs['Height'])
        cv = nt.nodes.new('ShaderNodeMapRange'); cv.inputs['From Min'].default_value = -.38; cv.inputs['From Max'].default_value = 0.0
        cv.inputs['To Min'].default_value = .62; cv.inputs['To Max'].default_value = 1.0; nt.links.new(sep.outputs[0], cv.inputs['Value'])
        dk = nt.nodes.new('ShaderNodeVectorMath'); dk.operation = 'SCALE'; nt.links.new(mul.outputs[0], dk.inputs[0]); nt.links.new(cv.outputs[0], dk.inputs['Scale'])
        colour = dk.outputs[0]
    else:
        bz = nt.nodes.new('ShaderNodeTexNoise'); bz.inputs['Scale'].default_value = .02; bz.inputs['Detail'].default_value = 2
        nt.links.new(uvn.outputs[0], bz.inputs['Vector'])
        bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 1.5; nt.links.new(bz.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(colour, b.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = .30; rr.inputs['To Max'].default_value = .58
    nt.links.new(rough.outputs[0], rr.inputs['Value'])
    if MICRO:
        # micro-imperfections: sub-millimetre roughness breakup and a few faint hairline scuffs
        mn = nt.nodes.new('ShaderNodeTexNoise'); mn.inputs['Scale'].default_value = 1.8; mn.inputs['Detail'].default_value = 6
        nt.links.new(uvn.outputs[0], mn.inputs['Vector'])
        sw = nt.nodes.new('ShaderNodeTexWave'); sw.wave_type = 'BANDS'; sw.inputs['Scale'].default_value = .035
        sw.inputs['Distortion'].default_value = 9.0; sw.inputs['Detail'].default_value = 3; nt.links.new(uvn.outputs[0], sw.inputs['Vector'])
        sl = nt.nodes.new('ShaderNodeMapRange'); sl.inputs['From Min'].default_value = .965; sl.inputs['From Max'].default_value = 1.0
        sl.inputs['To Min'].default_value = 0; sl.inputs['To Max'].default_value = 1; nt.links.new(sw.outputs['Fac'], sl.inputs['Value'])
        rv = nt.nodes.new('ShaderNodeMath'); rv.operation = 'MULTIPLY_ADD'; rv.inputs[1].default_value = .10
        nt.links.new(mn.outputs['Fac'], rv.inputs[0]); nt.links.new(rr.outputs[0], rv.inputs[2])
        rs = nt.nodes.new('ShaderNodeMath'); rs.operation = 'MULTIPLY_ADD'; rs.inputs[1].default_value = .14
        nt.links.new(sl.outputs[0], rs.inputs[0]); nt.links.new(rv.outputs[0], rs.inputs[2])
        rr = rs
    if detail:
        # inside holes and pressed marks the wax coat is thinner, so they don't throw white glints
        nt.links.new(rr.outputs[0], b.inputs['Roughness'])
        cw = nt.nodes.new('ShaderNodeMapRange'); cw.inputs['From Min'].default_value = -.28; cw.inputs['From Max'].default_value = -.04
        cw.inputs['To Min'].default_value = coat * .2; cw.inputs['To Max'].default_value = coat; nt.links.new(sep.outputs[0], cw.inputs['Value'])
        nt.links.new(cw.outputs[0], b.inputs['Coat Weight'])
    else:
        nt.links.new(rr.outputs[0], b.inputs['Roughness'])
    nt.links.new(bp.outputs[0], b.inputs['Normal'])
    if not detail: b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = .30
    nt.links.new(bp.outputs[0], b.inputs['Coat Normal'])
    b.inputs['Sheen Weight'].default_value = .08; b.inputs['Sheen Roughness'].default_value = .5
    b.inputs['Specular IOR Level'].default_value = .5
    return m

def edge():
    m, nt, b = _new('edge_paint')
    b.inputs['Base Color'].default_value = (0.035, 0.005, 0.009, 1); b.inputs['Roughness'].default_value = .34
    b.inputs['Coat Weight'].default_value = .35; b.inputs['Coat Roughness'].default_value = .25
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = .9; nz.inputs['Detail'].default_value = 3
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .12; bp.inputs['Distance'].default_value = .3
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

def flesh():
    m, nt, b = _new('flesh')
    b.inputs['Base Color'].default_value = (0.052, 0.009, 0.015, 1); b.inputs['Roughness'].default_value = .95
    b.inputs['Sheen Weight'].default_value = .22; b.inputs['Sheen Roughness'].default_value = .4; b.inputs['Specular IOR Level'].default_value = .2
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 4
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .35; bp.inputs['Distance'].default_value = .2
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

def thread():
    m, nt, b = _new('thread')
    b.inputs['Base Color'].default_value = (0.060, 0.0085, 0.013, 1); b.inputs['Roughness'].default_value = .45
    b.inputs['Sheen Weight'].default_value = .12; b.inputs['Sheen Tint'].default_value = (.6, .25, .28, 1); b.inputs['Coat Weight'].default_value = .2
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'mm'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (0, 0, .9); nt.links.new(uvn.outputs[0], mp.inputs['Vector'])
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = .55; wv.inputs['Distortion'].default_value = .6; wv.wave_profile = 'SIN'
    nt.links.new(mp.outputs[0], wv.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .45; bp.inputs['Distance'].default_value = .06
    nt.links.new(wv.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

def brass(name='brass', col=(0.70, 0.50, 0.24, 1), r0=.18, r1=.36):
    m, nt, b = _new(name)
    b.inputs['Base Color'].default_value = col; b.inputs['Metallic'].default_value = 1
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = .5; nz.inputs['Detail'].default_value = 3
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = r0; mr.inputs['To Max'].default_value = r1
    nt.links.new(nz.outputs['Fac'], mr.inputs['Value']); nt.links.new(mr.outputs[0], b.inputs['Roughness'])
    sc = nt.nodes.new('ShaderNodeTexNoise'); sc.inputs['Scale'].default_value = 3.0; sc.inputs['Detail'].default_value = 4
    nt.links.new(tc.outputs['Object'], sc.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .05; bp.inputs['Distance'].default_value = .05
    nt.links.new(sc.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

def tape():
    m, nt, b = _new('zip_tape')
    b.inputs['Base Color'].default_value = (0.030, 0.0045, 0.007, 1); b.inputs['Roughness'].default_value = .85
    b.inputs['Sheen Weight'].default_value = .25; b.inputs['Sheen Tint'].default_value = (.5, .2, .22, 1)
    tc = nt.nodes.new('ShaderNodeTexCoord'); wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.inputs['Scale'].default_value = 2.5
    nt.links.new(tc.outputs['Object'], wv.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .4; bp.inputs['Distance'].default_value = .05
    nt.links.new(wv.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

def void():
    m, nt, b = _new('void')
    b.inputs['Base Color'].default_value = (0.01, 0.004, 0.005, 1); b.inputs['Roughness'].default_value = 1; b.inputs['Specular IOR Level'].default_value = 0
    return m

def floor():
    m, nt, b = _new('floor')
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1 / 900, 1 / 900, 1 / 900)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    def tex(f, nc):
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = _img(ROOT + '/tex/conc/' + f, nc); nt.links.new(mp.outputs[0], t.inputs['Vector']); return t
    c, r, n = tex('diff.jpg', False), tex('rough.jpg', True), tex('nor_gl.jpg', True)
    tn = nt.nodes.new('ShaderNodeVectorMath'); tn.operation = 'MULTIPLY'; tn.inputs[1].default_value = (.20, .34, .66)
    nt.links.new(c.outputs[0], tn.inputs[0]); nt.links.new(tn.outputs[0], b.inputs['Base Color'])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = .42; mr.inputs['To Max'].default_value = .78
    nt.links.new(r.outputs[0], mr.inputs['Value']); nt.links.new(mr.outputs[0], b.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = .35; nt.links.new(n.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = .3
    return m

def glow():
    m, nt, b = _new('glint')
    b.inputs['Base Color'].default_value = (0, 0, 0, 1); b.inputs['Emission Color'].default_value = (1, .78, .5, 1)
    b.inputs['Emission Strength'].default_value = 0
    return m
