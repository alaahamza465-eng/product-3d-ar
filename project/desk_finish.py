# Photo finishing for the desk still: a gentle cinematic grade (cool shadows, warm highlights, soft S), a little
# bloom on the brass, lens vignette and a hair of lateral CA, fine film grain sized to the resolution.
# python3 desk_finish.py <in.png> <out.png> [out.jpg]
import sys
import numpy as np
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]; jpg = sys.argv[3] if len(sys.argv) > 3 else None
im = Image.open(src).convert('RGB'); W, H = im.size; k = W / 1920.
a = np.asarray(im, dtype=np.float32) / 255.
# bloom: only the brightest specks (brass, the zip), blurred at quarter size
lum = a.max(axis=2); hi = (np.clip((lum - .8) / .2, 0, 1)[..., None] * a * 255).astype(np.uint8)
sm = Image.fromarray(hi).resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6 * k / 4 * 4))
a = a + .16 * np.asarray(sm.resize((W, H), Image.BILINEAR), dtype=np.float32) / 255.
# grade: split-tone and a soft S-curve
L = a.mean(axis=2, keepdims=True)
sh = np.clip(1 - L / .45, 0, 1); hl = np.clip((L - .55) / .45, 0, 1)
a = a + sh * np.array([-.006, .002, .010]) + hl * np.array([.016, .006, -.012])
a = np.clip(a, 0, 1); a = a + .06 * (a - .5) * (1 - np.abs(2 * a - 1))        # gentle contrast in the mids
# vignette
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
v = 1 - .2 * np.clip(((xx - W / 2) / (W * .62)) ** 2 + ((yy - H / 2) / (H * .72)) ** 2, 0, 1.6) ** 1.4
a = a * v[..., None]; del xx, yy, v
# lateral CA (red a hair larger, blue a hair smaller)
img = Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)); r, g, b = img.split()
def scale(ch, s):
    w2, h2 = int(round(W * s)), int(round(H * s)); c = ch.resize((w2, h2), Image.BICUBIC); x0, y0 = (w2 - W) // 2, (h2 - H) // 2
    if s >= 1: return c.crop((x0, y0, x0 + W, y0 + H))
    o = Image.new('L', (W, H)); o.paste(c, (-x0, -y0)); return o
img = Image.merge('RGB', (scale(r, 1.0005), g, scale(b, .9996)))
# film grain: luminance only, grain about 1.6 px at 1080p scaled up with the frame
a = np.asarray(img, dtype=np.float32) / 255.
gs = max(1, int(round(1.6 * k)))
n = np.random.default_rng(3).standard_normal((H // gs + 1, W // gs + 1)).astype(np.float32)
n = np.asarray(Image.fromarray(n).resize((W // gs * gs + gs, H // gs * gs + gs), Image.BILINEAR))[:H, :W]
a = a + (.022 * n * (.55 + .45 * (1 - a.mean(axis=2))))[..., None]
res = Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8))
res.save(out, optimize=False)
if jpg: res.save(jpg, quality=95, subsampling=0)
print('FINISHED', out, W, H)
