# Geometry helpers for the leather clutch (Blender, 1 unit = 1 mm). Bag front faces -Y, floor is z = 0.
import bpy, bmesh, math
from mathutils import Vector, Matrix

def rrect_pts(w, h, r, n=14, cx=0.0, cy=0.0, rt=None):
    """closed rounded-rect outline (counter-clockwise), bottom corners radius r, top corners rt"""
    rt = r if rt is None else rt
    pts = []
    def arc(cxx, cyy, rr, a0, a1):
        if rr <= 1e-6: pts.append((cxx, cyy)); return
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append((cxx + rr * math.cos(a), cyy + rr * math.sin(a)))
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    arc(x1 - r, y0 + r, r, -math.pi / 2, 0)
    arc(x1 - rt, y1 - rt, rt, 0, math.pi / 2)
    arc(x0 + rt, y1 - rt, rt, math.pi / 2, math.pi)
    arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi)
    return pts

def resample(pts, step, closed=True):
    """even spacing along a polyline → list of (point, tangent)"""
    P = [Vector((p[0], p[1], 0)) if len(p) == 2 else Vector(p) for p in pts]
    if closed: P = P + [P[0]]
    seg = [(P[i + 1] - P[i]).length for i in range(len(P) - 1)]
    L = sum(seg); n = max(2, int(L / step)); out = []
    for k in range(n + (0 if closed else 1)):
        s = k * L / n; i = 0
        while i < len(seg) - 1 and s > seg[i]: s -= seg[i]; i += 1
        t = (P[i + 1] - P[i]).normalized() if seg[i] > 0 else Vector((1, 0, 0))
        out.append((P[i] + t * min(s, seg[i]), t))
    return out, L

def mesh_obj(name, me, mats=(), parent=None, smooth=True):
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    for m in mats: me.materials.append(m)
    if smooth:
        for p in me.polygons: p.use_smooth = True
    if parent: ob.parent = parent
    return ob

def slab(name, outline, t, r_edge, mats, parent=None, res=4):
    """2D outline (in a local XY plane) → slab of thickness t with fully rounded edges (radius r_edge ≤ t/2).
    Returned mesh lies in XZ (outline x → X, outline y → Z), thickness along Y: front face at y = -t/2."""
    cu = bpy.data.curves.new(name + '_cu', 'CURVE'); cu.dimensions = '2D'; cu.fill_mode = 'BOTH'
    sp = cu.splines.new('POLY'); sp.points.add(len(outline) - 1)
    # inset the outline by the edge radius: the curve bevel grows it back
    inset = offset_poly(outline, -r_edge)
    for i, (x, y) in enumerate(inset): sp.points[i].co = (x, y, 0, 1)
    sp.use_cyclic_u = True
    cu.extrude = max(0.0, t / 2 - r_edge); cu.bevel_depth = r_edge; cu.bevel_resolution = res
    tmp = bpy.data.objects.new(name + '_tmp', cu); bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg)); me.name = name
    bpy.data.objects.remove(tmp); bpy.data.curves.remove(cu)
    me.transform(Matrix.Rotation(math.radians(90), 4, 'X'))      # outline y → Z, thickness → -Y
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    while me.uv_layers: me.uv_layers.remove(me.uv_layers[0])
    uv = me.uv_layers.new(name='mm')
    for lp in me.loops:
        co = me.vertices[lp.vertex_index].co; uv.data[lp.index].uv = (co.x, co.z)
    ob = mesh_obj(name, me, mats, parent)
    assign_by_normal(ob)
    return ob

def offset_poly(pts, d):
    """offset a closed CCW polygon by d (negative = inwards) using averaged normals"""
    n = len(pts); out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e1 = (p1 - p0); e2 = (p2 - p1)
        if e1.length < 1e-9: e1 = e2
        if e2.length < 1e-9: e2 = e1
        n1 = Vector((e1.y, -e1.x)).normalized(); n2 = Vector((e2.y, -e2.x)).normalized()
        nn = (n1 + n2); nn = nn.normalized() if nn.length > 1e-9 else n1
        cosh = max(.3, nn.dot(n1))
        q = p1 + nn * (-d / cosh) * -1   # outward normal for CCW is (y,-x); d<0 moves inwards
        out.append((q.x, q.y))
    return out

def assign_by_normal(ob, face_axis='Y'):
    """material 0 on the broad faces (normal ≈ ±Y), material 1 on the cut edges; material 2 (if present) on the inner face (+Y)"""
    me = ob.data; nm = len(me.materials)
    for p in me.polygons:
        ny = p.normal.y
        if abs(ny) > .8: p.material_index = 0 if (ny < 0 or nm < 3) else 2
        else: p.material_index = 1 if nm > 1 else 0

def sweep(name, pts, profile, fixedW=None, faceF=None, closed=False, mats=(), parent=None, cap=True, mat_fn=None):
    """sweep a closed 2D profile [(a, b)] along a 3D polyline. a runs along W (width dir), b along NF (face normal).
    Frames: W = fixedW(p) or derived from a preferred face normal faceF(p) (W = T × F)."""
    P = [Vector(p) for p in pts]; N = len(P)
    bm = bmesh.new(); rings = []
    for i, p in enumerate(P):
        if closed: t = (P[(i + 1) % N] - P[i - 1]).normalized()
        else: t = (P[min(i + 1, N - 1)] - P[max(i - 1, 0)]).normalized()
        if fixedW is not None: W = Vector(fixedW(p)).normalized(); NF = W.cross(t).normalized(); W = t.cross(NF).normalized()
        else:
            F = Vector(faceF(p)).normalized(); W = t.cross(F).normalized(); NF = W.cross(t).normalized()
        rings.append([bm.verts.new(p + W * a + NF * b) for a, b in profile])
    m = len(profile)
    for i in range(N if closed else N - 1):
        r0, r1 = rings[i], rings[(i + 1) % N]
        for j in range(m):
            f = bm.faces.new((r0[j], r0[(j + 1) % m], r1[(j + 1) % m], r1[j]))
            if mat_fn: f.material_index = mat_fn(j)
    if cap and not closed:
        bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return mesh_obj(name, me, mats, parent)

def rr_profile(w, h, r, n=4):
    """closed rounded-rect profile centred at 0: w along a, h along b"""
    return rrect_pts(w, h, min(r, w / 2 - 1e-3, h / 2 - 1e-3), n)

def _capsule_template(length=3.0, radius=.46, seg=10, rings=6):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1)
    V = [Vector((v.co.x * length / 2, v.co.y * radius, v.co.z * radius)) for v in bm.verts]
    F = [[v.index for v in f.verts] for f in bm.faces]; bm.free(); return V, F

def _jit(k):
    # deterministic per-stitch irregularity: slant, sink, length (saddle stitching by hand is never exact)
    h = (k * 2654435761) % 4294967296 / 4294967296.0; h2 = (k * 40503 + 12345) % 65536 / 65536.0
    return (h - .5) * .10, (h2 - .5) * .06, 1 + (h - .5) * .06

def stitch_frame(p, t, n, k, length, radius, slant, sink):
    ds, dk, dl = _jit(k)
    t = Vector(t).normalized(); n = Vector(n).normalized(); t = (t - n * t.dot(n)).normalized()
    Rm = Matrix.Rotation(slant + ds, 3, n) @ Matrix((t, n.cross(t), n)).transposed()
    return Vector(p) - n * (sink + dk), Rm, dl

def _stitch_uv(V0):
    out = []
    for v in V0:
        out.append((v.x, math.atan2(v.z, v.y)))
    return out

def stitch_row(name, items, mats, parent=None, length=3.8, radius=.5, slant=.42, sink=.2):
    """items: [(point, tangent, normal)] → one mesh of slanted thread capsules sunk into the surface"""
    V0, F0 = _capsule_template(length, radius); UV0 = _stitch_uv(V0)
    verts, faces, uvs = [], [], []
    for k, (p, t, n) in enumerate(items):
        o, R, dl = stitch_frame(p, t, n, k, length, radius, slant, sink); base = len(verts)
        verts += [o + R @ Vector((v.x * dl, v.y, v.z)) for v in V0]
        faces += [[base + i for i in f] for f in F0]; uvs += [(u + k * 7.0, w) for u, w in UV0]
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    uv = me.uv_layers.new(name='mm')
    for lp in me.loops: uv.data[lp.index].uv = uvs[lp.vertex_index]
    return mesh_obj(name, me, mats, parent)

def frames_for(pts, faceF=None, fixedW=None, closed=False):
    if fixedW is not None and not callable(fixedW): _w = tuple(fixedW); fixedW = lambda p: _w
    if faceF is not None and not callable(faceF): _f = tuple(faceF); faceF = lambda p: _f
    P = [Vector(p) for p in pts]; N = len(P); out = []
    for i, p in enumerate(P):
        if closed: t = (P[(i + 1) % N] - P[i - 1]).normalized()
        else: t = (P[min(i + 1, N - 1)] - P[max(i - 1, 0)]).normalized()
        if fixedW is not None: W = Vector(fixedW(p)).normalized(); NF = W.cross(t).normalized(); W = t.cross(NF).normalized()
        else: F = Vector(faceF(p)).normalized(); W = t.cross(F).normalized(); NF = W.cross(t).normalized()
        out.append((p, t, W, NF))
    return out

def polyline_even(pts, step):
    """resample a 3D polyline (open) to ~even spacing"""
    P = [Vector(p) for p in pts]; out = [P[0]]; acc = 0.0
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]; L = (b - a).length; d = step - acc
        while d <= L: out.append(a + (b - a) * (d / L)); d += step
        acc = L - (d - step)
    if (out[-1] - P[-1]).length > 1e-6: out.append(P[-1])
    return out

def catmull(pts, n=8):
    """smooth an open 3D polyline with Catmull-Rom (n samples per segment)"""
    P = [Vector(p) for p in pts]; out = []
    for i in range(len(P) - 1):
        p0 = P[max(i - 1, 0)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(i + 2, len(P) - 1)]
        for k in range(n):
            t = k / n; t2 = t * t; t3 = t2 * t
            out.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1]); return out

def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(e)
    e.location = loc; e.empty_display_size = 10
    if parent: e.parent = parent
    return e

# ---------- additions: frame-based sweeps with per-ring profiles (constant topology → shape keys) ----------
def support(profile, d=.12):
    """insert points d from both ends of every long profile segment so flat faces keep flat normals"""
    out = []; n = len(profile)
    for i in range(n):
        a = Vector(profile[i]); b = Vector(profile[(i + 1) % n]); out.append(tuple(a))
        L = (b - a).length
        if L > 4 * d:
            u = (b - a) / L; out.append(tuple(a + u * d)); out.append(tuple(b - u * d))
    return out

def sweep_verts(frames, prof_fn):
    V = []
    for i, (p, t, W, NF) in enumerate(frames):
        for a, b in prof_fn(i): V.append(p + W * a + NF * b)
    return V

def sweep2(name, frames, prof_fn, closed=False, mats=(), parent=None, mat_fn=None, cap_mat=None, wn=True):
    """sweep with explicit frames [(p, t, W, NF)] and a per-ring profile prof_fn(i) → [(a, b)] (same length every ring)"""
    V = sweep_verts(frames, prof_fn); N = len(frames); m = len(prof_fn(0))
    F, FM = [], []
    for i in range(N if closed else N - 1):
        r0, r1 = i * m, ((i + 1) % N) * m
        for j in range(m):
            F.append((r0 + j, r0 + (j + 1) % m, r1 + (j + 1) % m, r1 + j)); FM.append(mat_fn(j) if mat_fn else 0)
    if not closed:
        F.append(tuple(reversed(range(0, m)))); FM.append(cap_mat or 0)
        F.append(tuple(range((N - 1) * m, N * m))); FM.append(cap_mat or 0)
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in V], [], F); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    for k, p in enumerate(me.polygons): p.material_index = FM[k]
    S = [0.0]
    for i in range(1, N): S.append(S[-1] + (frames[i][0] - frames[i - 1][0]).length)
    UVv = []
    for i in range(N):
        for a, b in prof_fn(i): UVv.append((a, S[i]))
    uv = me.uv_layers.new(name='mm')
    for lp in me.loops: uv.data[lp.index].uv = UVv[lp.vertex_index]
    ob = mesh_obj(name, me, mats, parent)
    if wn: weighted(ob)
    return ob

def weighted(ob):
    m = ob.modifiers.new('wn', 'WEIGHTED_NORMAL'); m.mode = 'FACE_AREA'; m.weight = 50; m.keep_sharp = False
    return m

def prof_mat(w, r, edge=1, front=0, back=2):
    """material for profile segment midpoints: ends of the width → edge paint, b>0 → grain, b<0 → flesh"""
    def f(prof):
        n = len(prof)
        def g(j):
            a = (prof[j][0] + prof[(j + 1) % n][0]) / 2; b = (prof[j][1] + prof[(j + 1) % n][1]) / 2
            if abs(a) > w / 2 - r - 1e-3: return edge
            return front if b > 0 else back
        return g
    return f

def u_path(w, h, r, cx=0., cz=0., n=12, top_arcs=True, y=0.):
    """open rounded-rect path in the XZ plane, CCW seen from the front (-Y), open along the top edge"""
    x0, z0, x1, z1 = cx - w / 2, cz - h / 2, cx + w / 2, cz + h / 2; P = []
    def arc(ccx, ccz, a0, a1, first=False):
        for i in range(0 if first else 1, n + 1):
            a = a0 + (a1 - a0) * i / n; P.append(Vector((ccx + r * math.cos(a), y, ccz + r * math.sin(a))))
    if top_arcs:
        arc(x0 + r, z1 - r, math.pi / 2, math.pi, True)
    else:
        P.append(Vector((x0, y, z1)))
    arc(x0 + r, z0 + r, math.pi, 1.5 * math.pi, not P)
    arc(x1 - r, z0 + r, 1.5 * math.pi, 2 * math.pi)
    if top_arcs: arc(x1 - r, z1 - r, 0, math.pi / 2)
    else: P.append(Vector((x1, y, z1)))
    return P

def densify(P, step):
    """split long straight segments so sweeps and stitches have enough rings"""
    out = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        L = (b - a).length; k = max(1, int(math.ceil(L / step)))
        for i in range(1, k + 1): out.append(a + (b - a) * (i / k))
    return out

def even(P, step, closed=False):
    """resample a 3D polyline to exactly even spacing (≈ step); returns points and the spacing used"""
    Q = list(P) + ([P[0]] if closed else [])
    seg = [(Q[i + 1] - Q[i]).length for i in range(len(Q) - 1)]; L = sum(seg)
    n = max(2, int(round(L / step))); ds = L / n; out = []
    for k in range(n + (0 if closed else 1)):
        s = k * ds; i = 0
        while i < len(seg) - 1 and s > seg[i]: s -= seg[i]; i += 1
        u = min(1.0, s / seg[i]) if seg[i] > 0 else 0
        out.append(Q[i] + (Q[i + 1] - Q[i]) * u)
    return out, ds

def sd_rrect(x, z, w, h, r, cx=0., cz=0.):
    qx = abs(x - cx) - (w / 2 - r); qz = abs(z - cz) - (h / 2 - r)
    return math.hypot(max(qx, 0), max(qz, 0)) + min(max(qx, qz), 0) - r

def circle_prof(r, n=12):
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def tube(name, pts, r, closed, mats, parent=None, n=12, fixedW=None, faceF=None):
    fr = frames_for(pts, faceF=faceF, fixedW=fixedW, closed=closed)
    prof = circle_prof(r, n)
    return sweep2(name, fr, lambda i: prof, closed=closed, mats=mats, parent=parent, wn=False)
