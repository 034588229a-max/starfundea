"""產生 App 外殼（pwa/）的圖示：員工打卡、店主管理、菜單 各一組（192、512、可遮罩 512），加 apple-touch-icon 與 favicon。
執行：python scripts/make_pwa_icons.py
想換圖示：改下面的顏色或 draw_* 函式，再執行一次，把 pwa/icons 一起上傳到 GitHub。"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'pwa', 'icons')
os.makedirs(OUT, exist_ok=True)
S = 1024   # 先用大圖畫，再縮小，邊緣才平滑

def rounded(bg, size=S, radius=0.22, full=False):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if full: d.rectangle([0, 0, size, size], fill=bg)
    else: d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius), fill=bg)
    return im, d

def draw_clock(d, k, off, white=(255, 255, 255)):
    c = S / 2; r = 300 * k
    d.ellipse([c - r, c - r, c + r, c + r], outline=white, width=int(48 * k))
    d.line([c, c, c, c - 170 * k], fill=white, width=int(48 * k))
    d.line([c, c, c + 130 * k, c + 70 * k], fill=white, width=int(48 * k))
    d.ellipse([c - 30 * k, c - 30 * k, c + 30 * k, c + 30 * k], fill=white)

def draw_owner(d, k, off, white=(255, 255, 255)):
    c = S / 2; w = 560 * k; top = c - 270 * k
    # 屋頂（遮陽棚）
    d.polygon([(c - w / 2 - 40 * k, top + 150 * k), (c - w / 2 + 70 * k, top), (c + w / 2 - 70 * k, top), (c + w / 2 + 40 * k, top + 150 * k)], fill=white)
    for i in range(5):
        x0 = c - w / 2 - 40 * k + i * (w + 80 * k) / 5
        d.rectangle([x0 + 8 * k, top + 150 * k, x0 + (w + 80 * k) / 5 - 8 * k, top + 215 * k], fill=white)
    # 店面
    d.rectangle([c - w / 2, top + 250 * k, c + w / 2, top + 540 * k], outline=white, width=int(40 * k))
    d.rectangle([c - 70 * k, top + 350 * k, c + 70 * k, top + 540 * k], fill=white)

def draw_menu(d, k, off, white=(255, 255, 255)):
    c = S / 2; w = 420 * k; h = 560 * k
    d.rounded_rectangle([c - w / 2, c - h / 2, c + w / 2, c + h / 2], radius=int(50 * k), outline=white, width=int(44 * k))
    for i, ln in enumerate([0.62, 0.62, 0.42]):
        y = c - h / 2 + 150 * k + i * 120 * k
        d.line([c - w / 2 + 90 * k, y, c - w / 2 + 90 * k + (w - 180 * k) * ln / 0.62, y], fill=white, width=int(40 * k))

ENTRIES = {'clock': ((27, 79, 138), draw_clock), 'owner': ((22, 35, 58), draw_owner), 'menu': ((232, 118, 42), draw_menu)}

def save(im, name, px):
    im.resize((px, px), Image.LANCZOS).save(os.path.join(OUT, name))

for key, (bg, fn) in ENTRIES.items():
    im, d = rounded(bg + (255,)); fn(d, 1.0, 0); save(im, f'{key}-512.png', 512); save(im, f'{key}-192.png', 192)
    mk, d2 = rounded(bg + (255,), full=True); fn(d2, 0.74, 0); save(mk, f'{key}-maskable-512.png', 512)   # 可遮罩圖示：圖案縮在中間 80% 安全區內
    ap, d3 = rounded(bg + (255,), full=True); fn(d3, 0.86, 0); save(ap, f'{key}-apple-180.png', 180)       # iOS 會自己切圓角
    save(im, f'{key}-32.png', 32)
print('已產生圖示：', sorted(os.listdir(OUT)))
