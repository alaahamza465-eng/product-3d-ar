# Runs inside Blender: renders every frame of film2.blend that is not in the output folder yet (so a stopped
# session just continues), on the GPU when there is one.
#   blender -b film2.blend -P render_frames.py
# env: FRAMES=<folder>  QUALITY=full|preview  F0/F1=<first/last frame>  ALLOW_CPU=1 (no GPU: slow, for tests)
import bpy, os, time, shutil

OUT = os.environ.get('FRAMES') or os.path.join(os.path.dirname(bpy.data.filepath), 'frames'); os.makedirs(OUT, exist_ok=True)
Q = os.environ.get('QUALITY', 'full')
sc = bpy.context.scene; prefs = bpy.context.preferences.addons['cycles'].preferences
for dev in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
    try:
        prefs.compute_device_type = dev; prefs.get_devices()
        if any(d.type == dev for d in prefs.devices): break
    except Exception: pass
for d in prefs.devices: d.use = d.type != 'CPU'
gpus = [(d.name, d.type) for d in prefs.devices if d.use]; print('DEVICES', gpus, flush=True)
if gpus:
    sc.cycles.device = 'GPU'
    try: sc.cycles.denoising_use_gpu = True
    except Exception: pass
elif not os.environ.get('ALLOW_CPU'):
    raise SystemExit('NO GPU — on Colab: Runtime > Change runtime type > T4 GPU, then run again')
if Q == 'preview':                                   # half size, fewer samples: ~6× faster, post2 scales it back up
    sc.render.resolution_percentage = 50; sc.cycles.samples = 64; sc.cycles.adaptive_threshold = .06
sc.render.use_persistent_data = True
im = sc.render.image_settings; im.file_format = 'PNG'; im.color_mode = 'RGB'; im.color_depth = '8'; im.compression = 15
F0 = int(os.environ.get('F0', sc.frame_start)); F1 = int(os.environ.get('F1', sc.frame_end))
todo = [f for f in range(F0, F1 + 1) if not os.path.exists(f'{OUT}/f{f:04d}.png')]
print('TODO', len(todo), 'frames', flush=True); t0 = time.time(); tmpd = os.environ.get('TMPDIR', '/tmp')
for i, f in enumerate(todo):
    sc.frame_set(f); tmp = f'{tmpd}/p3d_f{f:04d}.png'; sc.render.filepath = tmp; t = time.time()
    bpy.ops.render.render(write_still=True)
    shutil.copy(tmp, f'{OUT}/f{f:04d}.part'); os.replace(f'{OUT}/f{f:04d}.part', f'{OUT}/f{f:04d}.png'); os.remove(tmp)
    per = (time.time() - t0) / (i + 1); left = (len(todo) - i - 1) * per
    print(f'FRAME {f}  {time.time() - t:.1f}s   {i + 1}/{len(todo)}   left ~{left / 60:.0f} min', flush=True)
print('ALL FRAMES DONE', flush=True)
