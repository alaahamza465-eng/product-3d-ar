# Still photo v2 (the English brief): matte textured dark stone, casually scattered EDC, side window key + rim on the
# gold hardware, 85 mm f/2.0, 8K. Base: the desk shot: the bag in the middle of a wooden desk with a dark black stone top, its
# strap resting beside it; phone and papers on the left, keys, two cards and neat banknotes on the right;
# soft window light from the left, shallow depth of field. python desk_photo.py <out.png> <w> <h> <spp>
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy, sys, math, os
from mathutils import Vector, Quaternion, Euler, Matrix
sys.path.insert(0, ROOT)
import scene as S, items as IT, mats as MT
from geo import slab, rrect_pts

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
OUT = a[0] if a else ROOT + '/desk2.png'
RW, RH, SPP = (int(a[1]), int(a[2]), int(a[3])) if len(a) > 3 else (7680, 4320, 512)
MT.MICRO = True
B = ROOT

R = S.build(); M = R['M']; sc = bpy.context.scene
IR = IT.build(M)
S.render_settings(RW, RH, SPP, thr=.02)

# ---------------------------------------------------------------- the desk: black stone slab on a dark wood frame
def stone():
    """honed dark basalt: matte, a fine mineral grain you can feel, soft cloudy variation"""
    m, nt, b = MT._new('dark_stone')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    def noise(scale, detail=2, rough=.5):
        n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough; nt.links.new(tc.outputs['Object'], n.inputs['Vector']); return n
    cloud, grain, fine = noise(.004, 4, .55), noise(.55, 6, .65), noise(2.4, 3, .5)
    v = nt.nodes.new('ShaderNodeTexVoronoi'); v.inputs['Scale'].default_value = 1.3; nt.links.new(tc.outputs['Object'], v.inputs['Vector'])
    sp = nt.nodes.new('ShaderNodeMapRange'); sp.inputs['From Min'].default_value = .0; sp.inputs['From Max'].default_value = .12
    sp.inputs['To Min'].default_value = 1; sp.inputs['To Max'].default_value = 0; nt.links.new(v.outputs['Distance'], sp.inputs['Value'])
    cr = nt.nodes.new('ShaderNodeMapRange'); cr.inputs['From Min'].default_value = .35; cr.inputs['From Max'].default_value = .65
    cr.inputs['To Min'].default_value = .0065; cr.inputs['To Max'].default_value = .013; nt.links.new(cloud.outputs['Fac'], cr.inputs['Value'])
    gr = nt.nodes.new('ShaderNodeMapRange'); gr.inputs['From Min'].default_value = .4; gr.inputs['From Max'].default_value = .7
    gr.inputs['To Min'].default_value = .78; gr.inputs['To Max'].default_value = 1.25; nt.links.new(grain.outputs['Fac'], gr.inputs['Value'])
    base = nt.nodes.new('ShaderNodeMath'); base.operation = 'MULTIPLY'; nt.links.new(cr.outputs[0], base.inputs[0]); nt.links.new(gr.outputs[0], base.inputs[1])
    fl = nt.nodes.new('ShaderNodeMath'); fl.operation = 'MULTIPLY_ADD'; fl.inputs[1].default_value = .018
    nt.links.new(sp.outputs[0], fl.inputs[0]); nt.links.new(base.outputs[0], fl.inputs[2])
    tint = nt.nodes.new('ShaderNodeCombineColor'); [nt.links.new(fl.outputs[0], tint.inputs[i]) for i in range(3)]
    tm = nt.nodes.new('ShaderNodeVectorMath'); tm.operation = 'MULTIPLY'; tm.inputs[1].default_value = (1.0, 1.0, 1.03)
    nt.links.new(tint.outputs[0], tm.inputs[0]); nt.links.new(tm.outputs[0], b.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = .70; rr.inputs['To Max'].default_value = .86
    nt.links.new(cloud.outputs['Fac'], rr.inputs['Value']); nt.links.new(rr.outputs[0], b.inputs['Roughness'])
    hm = nt.nodes.new('ShaderNodeMath'); hm.operation = 'MULTIPLY_ADD'; hm.inputs[1].default_value = .35
    nt.links.new(fine.outputs['Fac'], hm.inputs[0]); nt.links.new(grain.outputs['Fac'], hm.inputs[2])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .22; bp.inputs['Distance'].default_value = .25
    nt.links.new(hm.outputs[0], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = .16
    return m

def wood():
    m, nt, b = MT._new('dark_wood')
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1 / 2000,) * 3
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    def tex(f, nc):
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = MT._img(f'{B}/tex/wood/{f}', nc); t.projection = 'BOX'; t.projection_blend = .2
        nt.links.new(mp.outputs[0], t.inputs['Vector']); return t
    c, r, n = tex('diff.jpg', False), tex('rough.jpg', True), tex('nor_gl.jpg', True)
    tn = nt.nodes.new('ShaderNodeVectorMath'); tn.operation = 'MULTIPLY'; tn.inputs[1].default_value = (.55, .48, .45)
    nt.links.new(c.outputs[0], tn.inputs[0]); nt.links.new(tn.outputs[0], b.inputs['Base Color'])
    nt.links.new(r.outputs[0], b.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(n.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], b.inputs['Normal'])
    b.inputs['Coat Weight'].default_value = .4; b.inputs['Coat Roughness'].default_value = .2
    return m

def box(name, size, loc, mat, bevel=2.0):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=4, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); ob.location = loc; me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    return ob

R['floor'].hide_render = True
ST, WD = stone(), wood()
TOP_T = 30.0
box('desk_top', (1600, 1000, TOP_T), (-60, 285, -TOP_T / 2 - .05), ST, bevel=3.0)          # front edge at y = -215
box('desk_apron', (1560, 40, 90), (-60, -195, -TOP_T - 45), WD, bevel=2.0)
box('desk_frame', (1640, 1040, 22), (-60, 285, -TOP_T - 11 - .2), WD, bevel=4.0)            # wooden rim under the stone

# ---------------------------------------------------------------- the things, laid on the desk
def place(k, loc, q):
    ob = IR[k]; ob.rotation_mode = 'QUATERNION'; ob.location = loc; ob.rotation_quaternion = q
def qe(x=0, y=0, z=0): return Euler((math.radians(x), math.radians(y), math.radians(z)), 'XYZ').to_quaternion()
# phone, back up (matte, camera showing), long side toward the camera, at the left front
place('phone', Vector((-196, -104, 3.95)), qe(z=-31) @ qe(x=90))
# papers: two flat A5 sheets with the memo, under and behind the phone
from geo import frames_for, sweep2, support, rr_profile
PAPER = IT._img_mat('paper', IT._load_rgb('letter_flat', -74.25, 74.25, 0., 212.), .78, sheen=.3)
pb = [n for n in PAPER.node_tree.nodes if n.type == 'BUMP'][0]; pb.inputs['Strength'].default_value = .35
def sheet(name, crease=1.4, curl=2.6, seed=0):
    P = []
    for k in range(213):
        s_ = float(k); z = crease * math.exp(-((s_ - 106) / 9.0) ** 2) + curl * max(0, (s_ - 170) / 42) ** 2 + .35 * math.sin(s_ * .05 + seed)
        P.append(Vector((s_ - 106, 0, z)))
    fr = frames_for(P, fixedW=(0, 1, 0)); prof = support(rr_profile(148.5, .1, .04, n=1))
    return sweep2(name, fr, lambda i: prof, mats=[PAPER], parent=None)
for i, (x, y, rz, sd) in enumerate(((-226, 54, 96, 0), (-200, 34, 79, 2))):
    sh = sheet('paper%d' % i, seed=sd); sh.location = (x, y, .08 + .16 * i); sh.rotation_euler = (0, 0, math.radians(rz))
for ob in [IR['letter']] + list(IR['letter'].children_recursive): ob.hide_render = True
# right: keys flat in front, the two cards fanned, neat banknotes behind
place('keys', Vector((172, -112, 2.0)), qe(z=41) @ qe(x=90))
place('card1', Vector((188, 4, 1.25)), qe(z=-17) @ qe(x=-90))          # face up: the chip shows
place('card2', Vector((222, 30, .42)), qe(z=11) @ qe(x=-90))
place('cash', Vector((236, 132, .2)), qe(z=-64))
for k, piv in enumerate(o for o in IR['cash'].children if o.name.startswith('note_piv')): piv.rotation_euler.z += math.radians((-14, 3, 19)[k])
for c in ('card1', 'card2'):
    for ob in IR[c].children_recursive:
        if ob.type == 'MESH' and not ob.name.endswith('_chip'):
            ob.material_slots[0].material = M['card_black']; ob.material_slots[-1].material = M['card_black']
cb = [n for n in M['card_black'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
cb.inputs['Coat Weight'].default_value = 0.; cb.inputs['Roughness'].default_value = .66; cb.inputs['Specular IOR Level'].default_value = .1
cnt = M['card_black'].node_tree; tx = [n for n in cnt.nodes if n.type == 'TEX_IMAGE'][0]
dk = cnt.nodes.new('ShaderNodeVectorMath'); dk.operation = 'SCALE'; dk.inputs['Scale'].default_value = .4
cnt.links.new(tx.outputs[0], dk.inputs[0]); cnt.links.new(dk.outputs[0], cb.inputs['Base Color'])
fb = [n for n in M['fob'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]; fb.inputs['Base Color'].default_value = (.66, .65, .62, 1); fb.inputs['Roughness'].default_value = .24
for i in range(3):
    nb = [n for n in M['note%d' % i].node_tree.nodes if n.type == 'BUMP'][0]; nb.inputs['Strength'].default_value = .7; nb.inputs['Distance'].default_value = .05

# ---------------------------------------------------------------- light: a window on the left, the room behind
for n in ('key', 'rim', 'rim_bag', 'top', 'fill', 'gapL'): R[n].data.energy *= 0
w = sc.world; nt = w.node_tree
env = [n for n in nt.nodes if n.type == 'TEX_ENVIRONMENT'][0]; env.image = bpy.data.images.load(f'{B}/hdri/hotel_room_2k.hdr')
mp = [n for n in nt.nodes if n.type == 'MAPPING'][0]; mp.inputs['Rotation'].default_value = (0, 0, math.radians(200))
R['world_bg'].inputs['Strength'].default_value = .42
mix = [n for n in nt.nodes if n.type == 'MIX_SHADER'][0]
for l in list(mix.inputs[2].links): nt.links.remove(l)
nt.links.new(R['world_bg'].outputs[0], mix.inputs[2])          # the room is seen behind the desk (blurred)
def area(name, size, loc, aim, power, col):
    L = bpy.data.lights.new(name, 'AREA'); L.shape = 'RECTANGLE'; L.size, L.size_y = size; L.energy = power; L.color = col
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc; o.visible_camera = False
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
area('window', (1400, 1800), (-2200, -520, 1150), (0, 0, 40), 4.4e7, (1.0, .96, .90))
area('bounce', (1600, 900), (1500, -1300, 450), (0, 0, 60), 3.0e6, (1.0, .93, .84))
area('rim_gold', (420, 90), (420, 760, 420), (0, 0, 110), 3.2e6, (1.0, .86, .66))
# window mullions between the window and the desk: soft bars of shade across the scene
import bmesh
def bar(name, size, loc):
    o = box(name, size, loc, MT._new('mullion')[0], bevel=.5); o.visible_camera = False; return o
for z in (900, 1350): bar('mull_h%d' % z, (40, 1800, 30), (-1480, -340, z))
bar('mull_v', (40, 30, 1300), (-1480, -340, 1120))

# ---------------------------------------------------------------- camera: 85 mm, low and close, focus on the bag
cam = R['cam']; cd = cam.data; cd.lens = 85; cd.dof.focus_object = None
tgt = Vector((-6, 4, 54)); AZ, EL = -10, 15
eye = tgt + Vector((math.sin(math.radians(AZ)) * math.cos(math.radians(EL)), -math.cos(math.radians(AZ)) * math.cos(math.radians(EL)), math.sin(math.radians(EL)))) * 1400
cam.location = eye; cam.rotation_euler = (tgt - eye).to_track_quat('-Z', 'Y').to_euler()
cd.dof.focus_distance = (Vector((10, -40, 50)) - eye).length; cd.dof.aperture_fstop = 2.0 * 1e-3
def use_gpu():
    try:
        p = bpy.context.preferences.addons['cycles'].preferences
        for dev in ('OPTIX', 'CUDA'):
            p.compute_device_type = dev; p.get_devices()
            if any(d.type == dev for d in p.devices):
                for d in p.devices: d.use = d.type == dev
                sc.cycles.device = 'GPU'; print('DEVICE', dev); return
    except Exception as e: print('no gpu', e)
    sc.cycles.device = 'CPU'
use_gpu()
sc.render.filepath = OUT
im = sc.render.image_settings; im.file_format = 'PNG'; im.color_mode = 'RGB'
bpy.ops.render.render(write_still=True)
print('DESK', OUT)
