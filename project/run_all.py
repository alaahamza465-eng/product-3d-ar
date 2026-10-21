# The whole film in one command (Linux / Google Colab): assets → scene → frames on the GPU → titles, sound → MP4.
# Every step skips work that is already done, so if a session stops, run the same command again and it continues.
#   python3 run_all.py --quality preview --out ~/product-film      (quick look: half size, fewer samples)
#   python3 run_all.py --quality full    --out ~/product-film      (final 1920×1080, 512 samples)
#   add --stills for the two desk product photos (3000×2000 and 8K), --rebuild after you change the scene code
import os, sys, glob, json, shutil, argparse, subprocess, platform

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--quality', choices=['preview', 'full'], default='preview')
ap.add_argument('--out', default=os.path.join(HERE, 'out'))
ap.add_argument('--blender', default=os.environ.get('BLENDER', ''))
ap.add_argument('--stills', action='store_true')
ap.add_argument('--rebuild', action='store_true')
A = ap.parse_args()
OUT = os.path.abspath(os.path.expanduser(A.out)); FR = os.path.join(OUT, 'frames-' + A.quality); os.makedirs(FR, exist_ok=True)
COLAB = 'COLAB_RELEASE_TAG' in os.environ or os.path.isdir('/content/sample_data')

def sh(cmd, env=None, keep=None):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=HERE,
                         env={**os.environ, 'P3D_ROOT': HERE, **(env or {})})
    for line in p.stdout:
        if keep is None or any(k in line for k in keep): print(line.rstrip(), flush=True)
    if p.wait(): raise SystemExit(f'step failed: {cmd}')

def blender():
    for b in (A.blender, shutil.which('blender') or '', os.path.expanduser('~/blender-5.2.2/blender'), '/content/blender/blender'):
        if b and os.path.exists(b): return b
    if platform.system() != 'Linux': raise SystemExit('install Blender 5.2 and pass --blender /path/to/blender')
    d = '/content/blender' if COLAB else os.path.expanduser('~/blender-5.2.2'); os.makedirs(d, exist_ok=True)
    print('downloading Blender 5.2.2 …', flush=True)
    sh(f'curl -sSL https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz -o /tmp/b.tar.xz && '
       f'tar -xf /tmp/b.tar.xz -C {d} --strip-components=1 && rm /tmp/b.tar.xz')
    return d + '/blender'

if COLAB and not os.path.exists('/tmp/.p3d_deps'):
    print('installing system libraries …', flush=True)
    sh('apt-get -qq update && apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libsm6 libxkbcommon0 '
       'libraqm0 libfribidi0 libharfbuzz0b > /dev/null', keep=['E:'])
    sh('pip -q install soundfile scipy', keep=['ERROR']); open('/tmp/.p3d_deps', 'w').close()
BL = blender(); sh(f'"{BL}" --version', keep=['Blender'])
sh('python3 setup_assets.py', keep=['downloading', 'ASSETS', 'Error', 'Traceback'])
if A.rebuild or not os.path.exists(os.path.join(HERE, 'film2.blend')):
    print('building the scene …', flush=True)
    sh('python3 printed.py', keep=['Error', 'Traceback'])
    sh(f'"{BL}" -b -P anim2.py', keep=['BAKED', 'Error', 'Traceback', 'line '])
    sh('python3 audio/mix2.py', keep=['mix2', 'Error', 'Traceback'])
if A.stills:
    for script, name, w, h in (('desk_photo.py', 'desk-photo', 3000, 2000), ('desk_photo2.py', 'desk-photo-8k', 7680, 4320)):
        if os.path.exists(f'{OUT}/{name}.jpg'): continue
        sh(f'"{BL}" -b -P {script} -- /tmp/{name}.png {w} {h} 512', keep=['DEVICE', 'DESK', 'Error', 'Traceback'])
        sh(f'python3 desk_finish.py /tmp/{name}.png {OUT}/{name}.png {OUT}/{name}.jpg', keep=['FINISHED', 'Error'])
sh(f'"{BL}" -b film2.blend -P render_frames.py', env={'FRAMES': FR, 'QUALITY': A.quality},
   keep=['DEVICES', 'TODO', 'FRAME', 'DONE', 'NO GPU', 'Error'])
NF = json.load(open(os.path.join(HERE, 'anchors2.json')))['NF']
n = len(glob.glob(FR + '/f*.png')); print('frames:', n, '/', NF, flush=True)
if n < NF: raise SystemExit('not all frames are there yet — run the same command again to continue')
print('titles, light effects and grain …', flush=True)
sh(f'python3 post2.py "{FR}" /tmp/p3d_video.mp4 1 {NF}', keep=['Error', 'Traceback'])
final = os.path.join(OUT, f'product-film-{A.quality}.mp4')
sh(f'ffmpeg -y -loglevel error -i /tmp/p3d_video.mp4 -i audio/out/mix2.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k '
   f'-af loudnorm=I=-14:TP=-1.2:LRA=11 -shortest -movflags +faststart "{final}"')
print('FINAL READY:', final, flush=True)
