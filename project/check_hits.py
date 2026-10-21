# Quality check: does any item pass through another item or through the bag, frame by frame? (BVH overlap)
# blender -b film2.blend -P check_hits.py -- [step]
import bpy, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
STEP = int(a[0]) if a else 2
F0 = int(a[1]) if len(a) > 1 else None; F1 = int(a[2]) if len(a) > 2 else None
sc = bpy.context.scene
ITEMS = {k: bpy.data.objects['it_' + k] for k in ('phone', 'letter', 'keys', 'card1', 'card2', 'cash')}
BAG = [o for o in bpy.data.collections['bag_only'].objects if o.type == 'MESH' and o.name != 'floor']

def tree(objs, dg):
    V, P = [], []
    for ob in objs:
        ev = ob.evaluated_get(dg); me = ev.to_mesh(); mw = ob.matrix_world; o = len(V)
        V += [mw @ v.co for v in me.vertices]; P += [[o + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(V, P) if P else None, V

def kids(root): return [o for o in root.children_recursive if o.type == 'MESH' and not o.hide_render]
def box(V):
    if not V: return None
    xs, ys, zs = zip(*[(v.x, v.y, v.z) for v in V]); return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
def near(b1, b2, m=2.0):
    return b1 and b2 and all(b1[i] - m <= b2[i + 3] and b2[i] - m <= b1[i + 3] for i in range(3))

hits = {}
for f in range(F0 or sc.frame_start, (F1 or sc.frame_end) + 1, STEP):
    sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
    T = {k: tree(kids(r), dg) for k, r in ITEMS.items()}
    B = {k: box(v[1]) for k, v in T.items()}
    ks = list(T)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            a_, b_ = ks[i], ks[j]
            if T[a_][0] and T[b_][0] and near(B[a_], B[b_]) and T[a_][0].overlap(T[b_][0]):
                hits.setdefault((a_, b_), []).append(f)
    for ob in BAG:
        ev = ob.evaluated_get(dg); qb = box([ob.matrix_world @ Vector(c) for c in ev.bound_box])
        close = [k for k in ks if T[k][0] and near(B[k], qb)]
        if not close: continue
        bt = tree([ob], dg)
        for k in close:
            if bt[0] and T[k][0].overlap(bt[0]): hits.setdefault((k, ob.name), []).append(f)
for (x, y), fs in sorted(hits.items(), key=lambda kv: kv[1][0]):
    print(f'HIT {x} × {y}: {len(fs)} frames, {fs[0]}–{fs[-1]} (t {(fs[0] - 1) / 30:.2f}–{(fs[-1] - 1) / 30:.2f}s)')
print('CHECKED', len(hits), 'pairs with contact')
