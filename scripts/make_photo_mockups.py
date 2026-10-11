"""官網與社群用照片的後製：把 Gemini 生成的空白樣品照疊上星樂創意官方 Logo，並排 FB／LINE 1:1 貼文。
輸入：site/photos/_raw/*.jpg（Gemini 生成，不含任何文字）　輸出：site/photos/*.jpg、brand/social/post-*.jpg（1080×1080）
執行：python scripts/make_photo_mockups.py（需要 Playwright、Pillow、zxing-cpp）"""
import asyncio, base64, io, os, shutil, warnings
from PIL import Image
warnings.filterwarnings('ignore')
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'site', 'photos', '_raw'); OUT = os.path.join(ROOT, 'site', 'photos')
LOGO = os.path.join(ROOT, 'brand', 'official'); SOCIAL = os.path.join(ROOT, 'brand', 'social'); os.makedirs(SOCIAL, exist_ok=True)
SITE_URL = 'https://034588229a-max.github.io/starfundea/'


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]
                M[r] = [x - f * y for x, y in zip(M[r], M[i])]
    return [M[i][n] / M[i][i] for i in range(n)]


def warp(flat, quad, size):
    """把平面圖 flat 貼到底圖的四邊形 quad（TL,TR,BR,BL）；回傳與底圖同大小的 RGBA。"""
    w, h = flat.size
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, b = [], []
    for (x, y), (u, v) in zip(quad, src):   # 由輸出座標 (x,y) 找回來源 (u,v)
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    co = solve(A, b)
    return flat.transform(size, Image.PERSPECTIVE, co, Image.BICUBIC)


def b64(path):
    return 'data:%s;base64,%s' % ('image/svg+xml' if path.endswith('.svg') else 'image/jpeg', base64.b64encode(open(path, 'rb').read()).decode())


async def shot(pg, html, w, h):
    await pg.set_viewport_size({'width': w, 'height': h})
    await pg.set_content(html, wait_until='networkidle'); await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(300)
    return await pg.screenshot(omit_background=True)


async def main():
    for f in os.listdir(RAW):
        if f.endswith('.jpg') and not f.startswith(('brand-cover', 'post-', 'service-brand')):
            shutil.copy(os.path.join(RAW, f), os.path.join(OUT, f))
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        font = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Noto+Sans+TC:wght@500;700;900&display=swap">'

        # 1) 品牌手冊：封面貼上官方直式 Logo（透視貼合）
        cover = Image.open(os.path.join(RAW, 'brand-cover-blank.jpg')).convert('RGB')
        png = await shot(pg, f'{font}<body style="margin:0;background:transparent"><div style="width:500px;height:700px;display:grid;place-items:center"><img src="{b64(os.path.join(LOGO, "logo-vertical-dark-pad.svg"))}" style="width:330px"></div>', 500, 700)
        flat = Image.open(io.BytesIO(png)).convert('RGBA')
        layer = warp(flat, [(536, 103), (796, 158), (708, 485), (412, 405)], cover.size)
        base = cover.convert('RGBA'); base.alpha_composite(layer)
        base.convert('RGB').save(os.path.join(OUT, 'service-brand.jpg'), quality=90)

        # 2) 桌號立牌：貼上 Logo 與真正可掃的 QR（手指在上層，只用卡片左半與下半）
        import zxingcpp
        qr = zxingcpp.write_barcode_to_svg(zxingcpp.create_barcode(SITE_URL, zxingcpp.BarcodeFormat.QRCode))
        qr_b64 = 'data:image/svg+xml;base64,' + base64.b64encode(qr.encode()).decode()
        png = await shot(pg, f'{font}<body style="margin:0;background:transparent"><div style="width:480px;height:480px;background:#F5F3EE;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px"><img src="{b64(os.path.join(LOGO, "logo-horizontal-light-nozh.svg"))}" style="width:300px"><img src="{qr_b64}" style="width:250px;height:250px"></div>', 480, 480)
        card = Image.open(io.BytesIO(png)).convert('RGBA')
        qrph = Image.open(os.path.join(RAW, 'post-qr.jpg')).convert('RGB')
        layer = warp(card, [(389, 586), (628, 586), (628, 828), (388, 828)], qrph.size)
        # 只在「原圖是卡片顏色」的像素上貼內容；手指（膚色、較暗）保持原樣
        mask = Image.new('L', qrph.size, 0); px = qrph.load(); mp = mask.load()
        for y in range(580, 835):
            for x in range(385, 632):
                r, g, bl = px[x, y]
                card_col = r > 200 and g > 195 and bl > 185 and abs(r - bl) < 28
                if card_col or not (x >= 566 and y <= 740): mp[x, y] = 255   # 只有右上手指區才依顏色保留原圖
        base = qrph.convert('RGBA'); comp = Image.composite(layer, Image.new('RGBA', qrph.size, (0, 0, 0, 0)), mask)
        base.alpha_composite(comp); base.convert('RGB').save(os.path.join(OUT, 'post-qr-brand.jpg'), quality=92)

        # 3) FB／LINE 1:1 貼文：照片＋品牌色塊＋標語＋Logo
        posts = [
            ('post-price', '改一次價格', '菜單、海報、QR 一起更新', 'post-price.jpg', 45),
            ('post-qr', '桌上一個 QR', '顧客掃到的永遠是最新菜單', 'post-qr-brand.jpg', 78),
            ('post-team', '打卡、排班', '員工手機一點就搞定', 'post-team.jpg', 35),
        ]
        for name, h1, sub, img, pos in posts:
            src = os.path.join(OUT if img == 'post-qr-brand.jpg' else RAW, img)
            html = f'''{font}<body style="margin:0"><div style="position:relative;width:1080px;height:1080px;overflow:hidden;background:#0E1623;font-family:'Noto Sans TC',sans-serif">
<img src="{b64(src)}" style="position:absolute;left:0;top:0;width:1080px;height:760px;object-fit:cover;object-position:50% {pos}%">
<div style="position:absolute;left:0;right:0;top:0;height:200px;background:linear-gradient(180deg,rgba(14,22,35,.62),rgba(14,22,35,0))"></div>
<div style="position:absolute;left:0;right:0;top:640px;height:120px;background:linear-gradient(180deg,rgba(14,22,35,0),#0E1623)"></div>
<img src="{b64(os.path.join(LOGO, "logo-horizontal-dark-nozh.svg"))}" style="position:absolute;left:64px;top:60px;height:44px;filter:drop-shadow(0 2px 6px rgba(0,0,0,.35))">
<div style="position:absolute;left:64px;right:64px;bottom:60px;color:#fff">
 <div style="width:72px;height:8px;background:#FFB534;margin-bottom:22px"></div>
 <div style="font-weight:900;font-size:84px;line-height:1.1;letter-spacing:.02em">{h1}</div>
 <div style="font-weight:700;font-size:42px;color:#FFB534;margin-top:10px">{sub}</div>
 <div style="font-family:'Barlow Condensed';font-weight:600;font-size:28px;letter-spacing:.2em;color:#8FA0B8;margin-top:26px">FROM IDEA TO SPARK.　把點子，走成亮點。</div>
</div></div>'''
            png = await shot(pg, html, 1080, 1080)
            Image.open(io.BytesIO(png)).convert('RGB').save(os.path.join(SOCIAL, name + '.jpg'), quality=92)
        await b.close()
    print('完成：', sorted(os.listdir(OUT)), sorted(os.listdir(SOCIAL)))

if __name__ == '__main__':
    asyncio.run(main())
