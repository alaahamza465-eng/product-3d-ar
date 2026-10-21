# Still photo (the brief's desk shot): the bag in the middle of a wooden desk with a dark black stone top, its
# strap resting beside it; phone and papers on the left, keys, two cards and neat banknotes on the right;
# soft window light from the left, shallow depth of field. python desk_photo.py <out.png> <w> <h> <spp>
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import bpy, sys, math, os
from mathutils import Vector, Quaternion, Euler, Matrix
sys.path.insert(0, ROOT)
import scene as S, items as IT, mats as MT
from geo import slab, rrect_pts

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
OUT = a[0] if a else ROOT + '/desk.png'
RW, RH, SPP = (int(a[1]), int(a[2]), int(a[3])) if len(a) > 3 else (3000, 2000, 512)
B = ROOT

R = S.build(); M = R['M']; sc = bpy.context.scene
IR = IT.build(M)
S.render_settings(RW, RH, SPP)

# ---------------------------------------------------------------- the desk: black stone slab on a dark wood frame
def stone():
    m, nt, b = MT._new('black_stone')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    def noise(scale, detail=2, rough=.5):
        n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough; nt.links.new(tc.outputs['Object'], n.inputs['Vector']); return n
    big, grain = noise(.0022, 3), noise(.9, 4, .6)
    v = nt.nodes.new('ShaderNodeTexVoronoi'); v.inputs['Scale'].default_value = 1.6; nt.links.new(tc.outputs['Object'], v.inputs['Vector'])
    sp = nt.nodes.new('ShaderNodeMapRange'); sp.inputs['From Min'].default_value = .0; sp.inputs['From Max'].default_value = .16
    sp.inputs['To Min'].default_value = 1; sp.inputs['To Max'].default_value = 0; nt.links.new(v.outputs['Distance'], sp.inputs['Value'])
    gm = nt.nodes.new('ShaderNodeMapRange'); gm.inputs['From Min'].default_value = .45; gm.inputs['From Max'].default_value = .75
    gm.inputs['To Min'].default_value = 0; gm.inputs['To Max'].default_value = 1; nt.links.new(grain.outputs['Fac'], gm.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; nt.links.new(sp.outputs[0], mul.inputs[0]); nt.links.new(gm.outputs[0], mul.inputs[1])
    col = nt.nodes.new('ShaderNodeMix'); col.data_type = 'RGBA'; nt.links.new(mul.outputs[0], col.inputs['Factor'])
    col.inputs[6].default_value = (.010, .010, .011, 1); col.inputs[7].default_value = (.36, .35, .33, 1)
    bm = nt.nodes.new('ShaderNodeMix'); bm.data_type = 'RGBA'; bm.blend_type = 'MULTIPLY'; bm.inputs['Factor'].default_value = .35
    nt.links.new(col.outputs[2], bm.inputs[6]); nt.links.new(big.outputs['Color'], bm.inputs[7])
    nt.links.new(bm.outputs[2], b.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = .26; rr.inputs['To Max'].default_value = .42
    nt.links.new(big.outputs['Fac'], rr.inputs['Value']); nt.links.new(rr.outputs[0], b.inputs['Roughness'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = .08; bp.inputs['Distance'].default_value = .2
    nt.links.new(grain.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = .55
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
place('phone', Vector((-214, -92, 3.95)), qe(z=-24) @ qe(x=90))
# papers: two flat A5 sheets with the memo, under and behind the phone
PAPER = IT._img_mat('paper', IT._load_rgb('letter_flat', -74.25, 74.25, 0., 212.), .82, sheen=.3)
for i, (x, y, rz) in enumerate(((-214, 58, 9), (-196, 44, -4))):
    sh = slab('paper%d' % i, [(px, pz + 106.0) for px, pz in rrect_pts(148.5, 210.0, .8, n=2)], .12, .04, [PAPER], parent=None, res=1)
    sh.location = (x, y - 106.0, .1 + .14 * i); sh.rotation_euler = (math.radians(90), 0, math.radians(rz + 180))
for ob in [IR['letter']] + list(IR['letter'].children_recursive): ob.hide_render = True
# right: keys flat in front, the two cards fanned, neat banknotes behind
place('keys', Vector((168, -104, 2.0)), qe(z=28) @ qe(x=90))
place('card1', Vector((196, 0, 1.25)), qe(z=-12) @ qe(x=90))
place('card2', Vector((214, 20, .42)), qe(z=6) @ qe(x=90))
place('cash', Vector((224, 136, .2)), qe(z=-78))

# ---------------------------------------------------------------- light: a window on the left, the room behind
for n in ('key', 'rim', 'rim_bag', 'top', 'fill', 'gapL'): R[n].data.energy *= 0
w = sc.world; nt = w.node_tree
env = [n for n in nt.nodes if n.type == 'TEX_ENVIRONMENT'][0]; env.image = bpy.data.images.load(f'{B}/hdri/hotel_room_2k.hdr')
mp = [n for n in nt.nodes if n.type == 'MAPPING'][0]; mp.inputs['Rotation'].default_value = (0, 0, math.radians(200))
R['world_bg'].inputs['Strength'].default_value = .55
mix = [n for n in nt.nodes if n.type == 'MIX_SHADER'][0]
for l in list(mix.inputs[2].links): nt.links.remove(l)
nt.links.new(R['world_bg'].outputs[0], mix.inputs[2])          # the room is seen behind the desk (blurred)
def area(name, size, loc, aim, power, col):
    L = bpy.data.lights.new(name, 'AREA'); L.shape = 'RECTANGLE'; L.size, L.size_y = size; L.energy = power; L.color = col
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc; o.visible_camera = False
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
area('window', (1400, 1800), (-2200, -520, 1150), (0, 0, 40), 5.5e7, (1.0, .96, .90))
area('bounce', (1600, 900), (1500, -1300, 450), (0, 0, 60), 4.5e6, (1.0, .93, .84))
# window mullions between the window and the desk: soft bars of shade across the scene
import bmesh
def bar(name, size, loc):
    o = box(name, size, loc, MT._new('mullion')[0], bevel=.5); o.visible_camera = False; return o
for z in (900, 1350): bar('mull_h%d' % z, (40, 1800, 30), (-1480, -340, z))
bar('mull_v', (40, 30, 1300), (-1480, -340, 1120))

# ---------------------------------------------------------------- camera: 85 mm, low and close, focus on the bag
cam = R['cam']; cd = cam.data; cd.lens = 85; cd.dof.focus_object = None
tgt = Vector((-10, 0, 52)); eye = tgt + Vector((math.sin(math.radians(-14)) * math.cos(math.radians(17)), -math.cos(math.radians(-14)) * math.cos(math.radians(17)), math.sin(math.radians(17)))) * 1380
cam.location = eye; cam.rotation_euler = (tgt - eye).to_track_quat('-Z', 'Y').to_euler()
cd.dof.focus_distance = (Vector((-6, -40, 52)) - eye).length; cd.dof.aperture_fstop = 4.0 * 1e-3
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
