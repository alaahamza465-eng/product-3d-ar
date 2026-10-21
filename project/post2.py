# v2 finishing: big, readable Arabic labels (RTL) with short leaders, item names in the hook, feature callouts in the
# orbit, an end card with the mark, the line and a call to action; bloom, vignette, lens CA, grain; 30 fps to ffmpeg.
# python post2.py <frames_dir> <out.mp4> [first] [last] [still]
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import sys, os, json, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FR, OUT = sys.argv[1], sys.argv[2]
J = json.load(open(ROOT + '/anchors2.json')); T = J['T']; FPS = J['FPS']; NF = J['NF']
ANC = {int(k): v for k, v in J['anchors'].items()}
F0 = int(sys.argv[3]) if len(sys.argv) > 3 else 1; F1 = int(sys.argv[4]) if len(sys.argv) > 4 else NF
W, H, SS = 1920, 1080, 2
FD = ROOT + '/fonts/'
LAY = ImageFont.Layout.RAQM
def font(name, px): return ImageFont.truetype(FD + name, int(px * SS), layout_engine=LAY)
AR_M = lambda px: font('IBMPlexSansArabic-Medium.ttf', px)
AR_R = lambda px: font('IBMPlexSansArabic-Regular.ttf', px)
AR_S = lambda px: font('IBMPlexSansArabic-SemiBold.ttf', px)
F_NAME, F_SPEC, F_ITEM, F_TAG, F_CTA = AR_S(56), AR_R(33), AR_M(46), AR_R(44), AR_S(38)
INK = (246, 240, 231); ACC = (217, 178, 111); SHADE = (0, 0, 0)
LOGO = json.load(open(ROOT + '/logo/logo.json'))
ITEM_ORDER = ['phone', 'letter', 'keys', 'card1', 'cash']; ITEMS = J['items']
FEAT = J['feat']           # [id, name, spec, t0, t1]
FEAT = [[f[0], f[1], f[2], (13.35 if f[0] == 'pocket' else f[3]), f[4]] for f in FEAT]

clamp = lambda x, a=0., b=1.: max(a, min(b, x))
seg = lambda t, a, b: clamp((t - a) / (b - a))
ss = lambda x: (lambda u: u * u * (3 - 2 * u))(clamp(x))
eo = lambda x: 1 - (1 - clamp(x)) ** 3
fade = lambda t, a, d=.3: ss(seg(t, a, a + d))
def tw(txt, f): return f.getlength(txt, direction='rtl') / SS

def text(d, xy, s, f, col, a, anchor, shadow=True):
    x, y = xy
    if shadow:   # a soft dark under-layer keeps the words readable over leather and floor alike
        d.text(((x + 1.5) * SS, (y + 2) * SS), s, font=f, fill=SHADE + (int(a * 110),), anchor=anchor, direction='rtl')
    d.text((x * SS, y * SS), s, font=f, fill=col + (int(a * 255),), anchor=anchor, direction='rtl')

# ---- feature callouts: the box is placed once per callout (from the anchor at mid-window), the dot follows the anchor
BOX = {}
for fid, name, spec, t0, t1 in FEAT:
    fm = int(round(((t0 + t1) / 2) * FPS)) + 1
    a = ANC.get(fm, {}).get(fid); bag = ANC.get(fm, {}).get('bag')
    if a is None: continue
    wmax = max(tw(name, F_NAME), tw(spec, F_SPEC))
    bx0, by0, bx1, by1 = bag if bag else (a[0] - 10, a[1] - 10, a[0] + 10, a[1] + 10)
    room_r, room_l, room_t = (W - 110) - (bx1 + 50), (bx0 - 50) - 110, by0 - 60
    if room_r >= wmax and room_r >= room_l:
        B = dict(rx=W - 110, ly=min(max(a[1] - 60, 190), 840), right=True)
    elif room_l >= wmax:
        B = dict(rx=110 + wmax, ly=min(max(a[1] - 60, 190), 840), right=False)
    else:   # no room beside the bag: above it, on the side of the anchor
        right = a[0] > W / 2
        rx = min(max(a[0] + (wmax * .25 if right else wmax * .75), 110 + wmax), W - 110)
        B = dict(rx=rx, ly=max(by0 - 92, 120), right=right, top=True)
    B['w'] = wmax; BOX[fid] = B

def callout(d, t, fid, name, spec, t0, t1, a):
    if a is None or a[2] <= 0 or fid not in BOX: return
    B = BOX[fid]; dl, tx, out = eo(seg(t, t0, t0 + .45)), fade(t, t0 + .25, .35), 1 - fade(t, t1 - .3, .3)
    if dl <= 0 or out <= 0: return
    A = lambda al: int(255 * al * out); s = SS
    ax, ay = a[0], a[1]
    if B.get('top'):
        ex = B['rx'] - B['w'] * (.85 if B['right'] else .15); ky = B['ly'] + 72
    else:
        ex = (B['rx'] - B['w'] - 28) if B['right'] else (B['rx'] + 28)      # where the leader meets the text block
        ky = B['ly'] - 14
    d.ellipse([(ax - 5) * s, (ay - 5) * s, (ax + 5) * s, (ay + 5) * s], fill=INK + (A(1),))
    r = 5 + 9 * dl; d.ellipse([(ax - r) * s, (ay - r) * s, (ax + r) * s, (ay + r) * s], outline=INK + (A(.4),), width=int(1.6 * s))
    kx = ex if B.get('top') else ex + (-40 if B['right'] else 40)
    s1, s2 = math.hypot(kx - ax, ky - ay), abs(ex - kx); ln = (s1 + s2) * dl
    pts = [(ax, ay)]
    if ln <= s1: pts.append((ax + (kx - ax) * ln / s1, ay + (ky - ay) * ln / s1))
    else: pts += [(kx, ky), (kx + (ex - kx) * (ln - s1) / max(s2, 1e-3), ky)]
    d.line([(x * s, y * s) for x, y in pts], fill=INK + (A(.85),), width=int(2.2 * s), joint='curve')
    if tx <= 0: return
    dx = (1 - tx) * (-14 if B['right'] else 14)
    text(d, (B['rx'] + dx, B['ly']), name, F_NAME, INK, tx * out, 'rs')
    text(d, (B['rx'] + dx, B['ly'] + 50), spec, F_SPEC, INK, tx * out * .88, 'rs')

ITEM_SIDE = {}
def _side(k):
    if k not in ITEM_SIDE:
        fm = int(round(((T['lblItems'][0] + T['lblItems'][1]) / 2) * FPS)) + 1
        a, bag = ANC.get(fm, {}).get(k), ANC.get(fm, {}).get('bag')
        ITEM_SIDE[k] = bool(a and bag and bag[0] - 20 < a[0] < bag[2] + 20 and a[1] + 64 > bag[1] + 22)
    return ITEM_SIDE[k]
def item_label(d, t, k, a, i, bag):
    if a is None or a[2] <= 0: return
    t0 = T['lblItems'][0] + .18 * i; t1 = T['lblItems'][1]
    kk = fade(t, t0, .4) * (1 - fade(t, t1 - .3, .3))
    if kk <= 0: return
    s = SS; x, y = a[0], a[1] + 64
    if _side(k): y = a[3] - 18      # would sit on the bag: above the item (decided once per item, so it never jumps)
    y = min(max(y, 62), H - 40) + (1 - kk) * 10
    d.rounded_rectangle([(x - 16) * s, (y - 48) * s, (x + 16) * s, (y - 45.5) * s], radius=2 * s, fill=ACC + (int(255 * kk),))
    text(d, (x, y), ITEMS[k], F_ITEM, INK, kk, 'ms')

def draw_logo(d, cx, cy, width, alpha):
    g = LOGO['plate']; sc = width / g['w']; x0 = cx - width / 2; y0 = cy - g['h'] * sc / 2; s = SS
    for p in sorted(g['polys'], key=lambda p: p['hole']):
        d.polygon([((x0 + x * sc) * s, (y0 + y * sc) * s) for x, y in p['pts']], fill=(0, 0, 0, 0) if p['hole'] else INK + (int(255 * alpha),))

def end_card(d, t):
    k = fade(t, T['card'], .7)
    if k <= 0: return
    dy = (1 - k) * 16; cx = 1530; s = SS
    draw_logo(d, cx, 420 + dy, 420, k)
    k2 = fade(t, T['tag'], .5)
    d.rectangle([(cx - 36) * s, (566 + dy) * s, (cx + 36) * s, (568.5 + dy) * s], fill=ACC + (int(255 * k2),))
    text(d, (cx, 634 + dy), 'تتّسع ليومك كلّه', F_TAG, INK, k2 * .92, 'ms')
    k3 = fade(t, T['cta'], .5)
    if k3 > 0:
        lbl = 'اطلبها الآن'; wv = tw(lbl, F_CTA) + 76; hv = 70; y0 = 690 + (1 - k3) * 12
        d.rounded_rectangle([(cx - wv / 2) * s, y0 * s, (cx + wv / 2) * s, (y0 + hv) * s], radius=hv / 2 * s,
                            fill=ACC + (int(255 * k3),))
        d.text((cx * s, (y0 + hv / 2 + 1) * s), lbl, font=F_CTA, fill=(28, 16, 14, int(255 * k3)), anchor='mm', direction='rtl')

def overlay(f):
    t = (f - 1) / FPS; A = ANC.get(f, {})
    if not A and t < T['card']: return None
    im = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, k in enumerate(ITEM_ORDER): item_label(d, t, k, A.get(k), i, A.get('bag'))
    for fid, name, spec, t0, t1 in FEAT: callout(d, t, fid, name, spec, t0, t1, A.get(fid))
    end_card(d, t)
    return im.resize((W, H), Image.LANCZOS)

# ---- vignette, bloom, lens CA, grain
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = 1 - .22 * np.clip(((xx - W / 2) / (W * .62)) ** 2 + ((yy - H / 2) / (H * .72)) ** 2, 0, 1.6) ** 1.4
RNG = np.random.default_rng(7)
def finish(im):
    a = np.asarray(im, dtype=np.float32) / 255.
    lum = a.max(axis=2); hi = np.clip((lum - .78) / .22, 0, 1)[..., None] * a
    small = Image.fromarray((hi * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR)
    bl = np.asarray(small.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR), dtype=np.float32) / 255.
    a = (a + .2 * bl) * VIG[..., None]
    img = Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)); r, g, b = img.split()
    def scale(ch, k):
        w2, h2 = int(round(W * k)), int(round(H * k)); c = ch.resize((w2, h2), Image.BICUBIC)
        x0, y0 = (w2 - W) // 2, (h2 - H) // 2
        if k >= 1: return c.crop((x0, y0, x0 + W, y0 + H))
        out = Image.new('L', (W, H)); out.paste(c, (-x0, -y0)); return out
    img = Image.merge('RGB', (scale(r, 1.0007), g, scale(b, .9994)))
    a = np.asarray(img, dtype=np.float32) / 255.
    n = RNG.standard_normal((H // 2, W // 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n).resize((W, H), Image.BILINEAR))
    a = a + (.014 * n * (.6 + .4 * (1 - a.mean(axis=2))))[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8))

def frame(f):
    im = Image.open(f'{FR}/f{f:04d}.png').convert('RGB')
    if im.size != (W, H): im = im.resize((W, H), Image.LANCZOS)
    im = finish(im); ov = overlay(f)
    return Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB') if ov is not None else im

def main():
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
           '-color_trc', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE); last = None
    for f in range(F0, F1 + 1):
        if os.path.exists(f'{FR}/f{f:04d}.png'): last = frame(f)
        p.stdin.write(last.tobytes())
    p.stdin.close(); p.wait(); print('POST', OUT, F0, F1)

if __name__ == '__main__':
    if len(sys.argv) > 5 and sys.argv[5] == 'still':
        frame(F0).save(OUT, quality=92); print('STILL', OUT)
    else: main()
