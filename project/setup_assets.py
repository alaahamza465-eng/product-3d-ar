# Downloads the free (CC0 / OFL) textures, HDRIs and fonts the scene uses, then builds two derived files:
# a cleaned leather colour map and the logo depth mask. Safe to run again: it skips what is already there.
#   python3 setup_assets.py
import os, json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.environ.get('P3D_ROOT') or os.path.dirname(os.path.abspath(__file__))
PH = 'https://dl.polyhaven.org/file/ph-assets'                   # Poly Haven, CC0
GF = 'https://raw.githubusercontent.com/google/fonts/main/ofl'    # Google Fonts, OFL

GET = [(f'{PH}/Textures/jpg/4k/leather_red_03/leather_red_03_{m}_4k.jpg', f'tex/lr3/{m}.jpg') for m in ('coll1', 'rough', 'nor_gl')]
GET += [(f'{PH}/Textures/jpg/2k/smooth_concrete_floor/smooth_concrete_floor_{m}_2k.jpg', f'tex/conc/{m}.jpg') for m in ('diff', 'nor_gl', 'rough')]
GET += [(f'{PH}/Textures/jpg/2k/dark_wood/dark_wood_{m}_2k.jpg', f'tex/wood/{m}.jpg') for m in ('diff', 'rough', 'nor_gl')]
GET += [(f'{PH}/HDRIs/hdr/2k/photo_studio_loft_hall_2k.hdr', 'hdri/photo_studio_loft_hall_2k.hdr'),
        (f'{PH}/HDRIs/hdr/2k/hotel_room_2k.hdr', 'hdri/hotel_room_2k.hdr')]
GET += [(f'{GF}/ibmplexsansarabic/IBMPlexSansArabic-{w}.ttf', f'fonts/IBMPlexSansArabic-{w}.ttf') for w in ('Medium', 'Regular', 'SemiBold')]
GET += [(f'{GF}/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf', 'fonts/JetBrainsMono.ttf')]

def main():
    for url, rel in GET:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p) and os.path.getsize(p) > 1000: continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        print('downloading', rel, flush=True)
        subprocess.run(['curl', '-sSL', '--retry', '4', '-o', p, url], check=True)
    for d in ('maps', 'audio/out', 'tex/printed'): os.makedirs(os.path.join(ROOT, d), exist_ok=True)
    # the leather scan has a few bright specks: replace them with the local median
    clean = os.path.join(ROOT, 'tex/lr3/coll1_clean.jpg')
    if not os.path.exists(clean):
        im = Image.open(os.path.join(ROOT, 'tex/lr3/coll1.jpg')).convert('RGB'); a = np.asarray(im, dtype=np.float32)
        med = np.asarray(im.filter(ImageFilter.MedianFilter(7)), dtype=np.float32)
        bad = (a.mean(2) - med.mean(2)) > 26
        bad = np.asarray(Image.fromarray((bad * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
        Image.fromarray(np.where(bad[..., None], med, a).astype(np.uint8)).save(clean, quality=95)
    # the stamped logo: vector outline (logo/logo.json) → soft depth mask the leather shader presses in
    D = json.load(open(os.path.join(ROOT, 'logo/logo.json'))); g = D['plate']; ppu = 46 * 24 / g['w']
    m = Image.new('L', (int(round(g['w'] * ppu)), int(round(g['h'] * ppu))), 0); d = ImageDraw.Draw(m)
    for p in sorted(g['polys'], key=lambda p: p['hole']):
        d.polygon([(x * ppu, y * ppu) for x, y in p['pts']], fill=0 if p['hole'] else 255)
    np.save(os.path.join(ROOT, 'logo/plate_mask.npy'), np.asarray(m.filter(ImageFilter.GaussianBlur(24 * .1)), dtype=np.float32) / 255.)
    print('ASSETS OK', flush=True)

if __name__ == '__main__':
    main()
