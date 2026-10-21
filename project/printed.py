# Printed surfaces for the items, drawn with PIL (runs in plain python3, not inside Blender):
# a real Arabic memo on the folded A5 sheet, and three fictional banknotes (no real currency, no real bank).
# Output PNGs in tex/printed/, laid out to match the items' UV (u across the sheet, v along it; PNG top = v max).
import os as _os; ROOT = _os.environ.get('P3D_ROOT') or _os.path.dirname(_os.path.abspath(__file__))   # the project folder
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

B = ROOT; OUT = f'{B}/tex/printed'; FD = ROOT + '/fonts/'
LAY = ImageFont.Layout.RAQM
def F(w, px): return ImageFont.truetype(FD + f'IBMPlexSansArabic-{w}.ttf', int(px), layout_engine=LAY)

def wrap(d, text, font, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font, direction='rtl') <= width: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def letter(ppm=10):
    W, H = int(148.5 * ppm), int(212 * ppm); mm = lambda v: int(round(v * ppm))
    paper = np.array([197, 195, 186], np.float32)
    rng = np.random.default_rng(5)
    a = np.ones((H, W, 3), np.float32) * paper
    a += (rng.standard_normal((H // 8 + 1, W // 8 + 1)).repeat(8, 0).repeat(8, 1)[:H, :W, None] * 1.6)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im)
    ink = (34, 36, 44); soft = (92, 94, 100); acc = (120, 34, 40)
    R = W - mm(14); L = mm(14); y = mm(16)
    d.text((R, y), 'مذكّرة', font=F('SemiBold', mm(7.2)), fill=ink, anchor='ra', direction='rtl')
    d.text((L, y + mm(1.6)), 'الأحد، ٤ تشرين الأول', font=F('Regular', mm(3.4)), fill=soft, anchor='la', direction='rtl')
    y += mm(12); d.rectangle([L, y, R, y + max(1, mm(.3))], fill=acc); y += mm(6)
    body = F('Regular', mm(3.9)); lh = mm(6.6)
    paras = [
        'مراجعة عرض السعر مع المورّد قبل الظهر، والتأكد من الكميات والمقاسات قبل التوقيع.',
        'استلام العيّنات الجديدة من المشغل وفحص الخياطة والحواف قطعة قطعة.',
        'تأكيد موعد التصوير يوم الخميس، وتجهيز الإضاءة والخلفية من مساء الأربعاء.',
        'تحويل الدفعة الثانية بعد الاستلام، وإرسال صورة الإيصال للمحاسبة.',
        'الاتصال بالعميل لتأكيد طلبه وموعد التوصيل.',
        'طلب كرتون التغليف الجديد وورق الحرير بلون العلامة.',
        'تجديد اشتراك المستودع قبل نهاية الشهر.',
        'تجهيز قائمة الأسعار المحدّثة وإرسالها للموزّعين.',
        'ترتيب لقاء مع المصمم لمراجعة ألوان المجموعة القادمة.',
        'متابعة الشحنة المتأخرة مع شركة النقل وتحديد موعد جديد.',
    ]
    for i, p in enumerate(paras):
        for j, ln in enumerate(wrap(d, p, body, R - L - mm(6))):
            d.text((R - (mm(6) if j else 0), y), ('•  ' if j == 0 else '') + ln, font=body, fill=ink, anchor='ra', direction='rtl'); y += lh
        y += mm(2.6)
    y = H - mm(34)
    d.text((R, y), 'مع التحية،', font=F('Regular', mm(3.9)), fill=ink, anchor='ra', direction='rtl')
    # a hand signature: a loose scribble
    pts = [(R - mm(6) - mm(30) * k / 80 + mm(2.4) * math.sin(k * .55), y + mm(12) + mm(2.6) * math.sin(k * .31) - mm(1.5) * math.cos(k * .9)) for k in range(81)]
    d.line(pts, fill=(28, 40, 86), width=max(2, mm(.35)), joint='curve')
    im = im.filter(ImageFilter.GaussianBlur(.5)); os.makedirs(OUT, exist_ok=True)
    im.save(f'{OUT}/letter_flat.png')                                       # for flat sheets (desk photo)
    im = im.rotate(180); im.save(f'{OUT}/letter.png')   # the folded sheet's UV runs the other way round; return im.size

def rosette(X, Y, cx, cy, r0, k):
    dx, dy = X - cx, Y - cy; r = np.hypot(dx, dy); th = np.arctan2(dy, dx)
    g = np.cos(k * th + r * .9) * np.cos(r * 1.7 - 3 * np.sin(5 * th))
    return np.exp(-((r - r0) / (r0 * .6)) ** 2) * (g * .5 + .5)

def note(name, base, ink, deep, ppm=10, seed=0):
    """landscape note 151 × 70 mm drawn flat, then turned to the item's UV layout (long side along v)"""
    W, H = int(151 * ppm), int(70 * ppm); mm = lambda v: int(round(v * ppm))
    x = (np.arange(W) + .5) / ppm; y = (np.arange(H) + .5) / ppm; X, Y = np.meshgrid(x, y)
    base, ink, deep = (np.array(c, np.float32) for c in (base, ink, deep))
    k = np.clip(X / 151, 0, 1)[..., None]
    col = base * (1 - .12 * k)
    t = .85 * rosette(X, Y, 40, 35, 17, 11) + .55 * rosette(X, Y, 123, 30, 10, 7)
    t += (np.sin(Y * 2.6 + 4 * np.sin(X * .19)) * .5 + .5) ** 3 * .45 * ((Y < 9) | (Y > 61) | (X < 8) | (X > 143))
    t += (np.sin(X * 3.1 + 3 * np.sin(Y * .23)) * .5 + .5) ** 6 * .25
    fr = ((np.abs(X - 4) < .45) | (np.abs(X - 147) < .45) | (np.abs(Y - 4) < .45) | (np.abs(Y - 66) < .45)) & (X > 3.5) & (X < 147.5) & (Y > 3.5) & (Y < 66.5)
    t = np.clip(t + fr * .9, 0, 1)[..., None]
    col = col * (1 - t) + ink * t
    strip = (np.abs(X - 98) < 2.2)[..., None]                       # a security thread
    col = np.where(strip, col * .55 + np.array([200, 200, 205], np.float32) * .45, col)
    oval = np.exp(-(((X - 123) / 15) ** 2 + ((Y - 33) / 20) ** 2) * 2.2)[..., None]
    col = col * (1 - .35 * oval) + base * 1.08 * .35 * oval        # the watermark window, paler
    im = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im)
    num = F('SemiBold', mm(15)); d.text((mm(144), mm(7)), '100', font=num, fill=tuple(int(c) for c in deep), anchor='ra')
    d.text((mm(9), mm(64)), '100', font=F('SemiBold', mm(8)), fill=tuple(int(c) for c in deep), anchor='ls')
    d.text((mm(84), mm(52)), 'مئة', font=F('SemiBold', mm(9)), fill=tuple(int(c) for c in deep), anchor='rs', direction='rtl')
    rng = np.random.default_rng(seed)
    d.text((mm(84), mm(60)), 'ورقة نقدية · ' * 3, font=F('Regular', mm(2.2)), fill=tuple(int(c) for c in ink), anchor='rs', direction='rtl')
    serial = 'HZ ' + ''.join(str(rng.integers(0, 10)) for _ in range(7))
    d.text((mm(9), mm(12)), serial, font=F('Medium', mm(3.6)), fill=(150, 36, 30), anchor='la')
    for i in range(7):                                             # a geometric emblem in the rosette
        a0 = 2 * math.pi * i / 7; r1, r2 = mm(6), mm(13)
        d.line([(mm(40) + r1 * math.cos(a0), mm(35) + r1 * math.sin(a0)), (mm(40) + r2 * math.cos(a0 + .45), mm(35) + r2 * math.sin(a0 + .45))], fill=tuple(int(c) for c in deep), width=mm(.5))
    d.ellipse([mm(40) - mm(5), mm(35) - mm(5), mm(40) + mm(5), mm(35) + mm(5)], outline=tuple(int(c) for c in deep), width=mm(.6))
    im = im.filter(ImageFilter.GaussianBlur(.6)).rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
    im.save(f'{OUT}/{name}.png'); return im.size

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    print('letter', letter())
    print('note0', note('note0', (176, 196, 168), (36, 92, 66), (18, 58, 40), seed=1))
    print('note1', note('note1', (170, 188, 206), (30, 66, 112), (16, 38, 74), seed=2))
    print('note2', note('note2', (214, 182, 150), (120, 56, 34), (82, 34, 20), seed=3))
    print('PRINTED OK')
