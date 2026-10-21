# Quick low-quality stills of chosen frames + one contact sheet, to check a change before the long render.
#   blender -b film2.blend -P preview.py -- <out_dir> <scale%> <samples> f1 f2 f3 ...
#   e.g.  blender -b film2.blend -P preview.py -- pv 30 8 120 150 180 210 240
import bpy, sys, os, time
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out, pct, spp, frames = a[0], int(a[1]), int(a[2]), [int(x) for x in a[3:]]
sc = bpy.context.scene; sc.render.resolution_percentage = pct; sc.cycles.samples = spp; sc.cycles.adaptive_threshold = .05
im = sc.render.image_settings; im.file_format = 'PNG'; im.color_mode = 'RGB'
os.makedirs(out, exist_ok=True)
for f in frames:
    t = time.time(); sc.frame_set(f); sc.render.filepath = os.path.abspath(f'{out}/f{f:04d}.png'); bpy.ops.render.render(write_still=True)
    print('PV', f, round(time.time() - t, 1), flush=True)
try:                                             # one sheet with every frame, numbered, to look at in one go
    from PIL import Image, ImageDraw
    ims = [Image.open(f'{out}/f{f:04d}.png') for f in frames]; W, H = ims[0].size; C = min(4, len(ims)); R = (len(ims) + C - 1) // C
    S = Image.new('RGB', (W * C, H * R))
    for i, (f, m) in enumerate(zip(frames, ims)):
        ImageDraw.Draw(m).text((8, 6), str(f), fill=(255, 220, 0)); S.paste(m, ((i % C) * W, (i // C) * H))
    S.save(f'{out}/sheet.jpg', quality=88); print('SHEET', f'{out}/sheet.jpg')
except Exception as e:
    print('no sheet:', e)
