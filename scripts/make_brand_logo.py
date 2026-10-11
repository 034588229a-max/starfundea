"""StarFunDea 品牌標誌產生器（向量字母＋Playwright 轉 PNG）。
輸出到 brand/：直式（深色底、淺色底）、橫式、App 圖示、品牌規範圖。
字母用自己畫的幾何線條字（STARFUNDEA 共 9 種），不依賴字型，SVG 在任何裝置看起來都一樣；
中文「星樂創意」用文字（顯示時需要微軟正黑體／蘋方／思源黑體，PNG 已用正黑體轉好）。
改顏色或字距：修改下面的常數後重跑 python scripts/make_brand_logo.py"""
import asyncio, os
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'brand')
os.makedirs(OUT, exist_ok=True)

NAVY = '#0E1623'; AMBER = '#FFB534'; AMBER_L = '#F29A00'; WHITE = '#FFFFFF'; MUTE = '#8FA0B8'
SW = 1.45       # 線條粗細（字母單位）
ADV = 6.9       # 字母寬 5＋間距 1.9（字距寬一點，更像科技品牌）
CJK = "'Microsoft JhengHei','PingFang TC','Noto Sans TC','Heiti TC',sans-serif"

# 字母：座標範圍 x 0..5、y 0..8（單位），線條置中
G = {
 'S': ['M4.3 2.5 V1.72 Q4.3 0.72 3.3 0.72 H1.7 Q0.7 0.72 0.7 1.72 V3 Q0.7 4 1.7 4 H3.3 Q4.3 4 4.3 5 V6.28 Q4.3 7.28 3.3 7.28 H1.7 Q0.7 7.28 0.7 6.28 V5.5'],
 'T': ['M0 0.72 H5', 'M2.5 0.72 V8'],
 'A': ['M0.7 8 V1.72 Q0.7 0.72 1.7 0.72 H3.3 Q4.3 0.72 4.3 1.72 V8', 'M0.7 4.9 H4.3'],
 'R': ['M0.7 8 V0.72 H3.3 Q4.3 0.72 4.3 1.72 V3.1 Q4.3 4.1 3.3 4.1 H0.7', 'M2.9 4.1 L4.3 8'],
 'F': ['M4.5 0.72 H0.7 V8', 'M0.7 4.1 H3.8'],
 'U': ['M0.7 0 V6.28 Q0.7 7.28 1.7 7.28 H3.3 Q4.3 7.28 4.3 6.28 V0'],
 'N': ['M0.7 8 V0.72 L4.3 7.28 V0'],
 'D': ['M0.7 0.72 H2.9 Q4.3 0.72 4.3 2.1 V5.9 Q4.3 7.28 2.9 7.28 H0.7', 'M0.7 0 V8'],
 'E': ['M4.5 0.72 H0.7 V7.28 H4.5', 'M0.7 4 H3.9'],
}

def word(text, x, y, u, color):
    """回傳 (svg, 寬度)：一行字母，左上角在 (x, y)，一個單位 u 像素"""
    g = []
    for i, ch in enumerate(text):
        paths = ''.join(f'<path d="{d}"/>' for d in G[ch])
        g.append(f'<g transform="translate({x + i * ADV * u:.2f} {y:.2f}) scale({u})">{paths}</g>')
    w = (len(text) * ADV - (ADV - 5)) * u
    return f'<g fill="none" stroke="{color}" stroke-width="{SW}" stroke-linejoin="miter" stroke-linecap="butt">' + ''.join(g) + '</g>', w

def icon(x, y, size, ink, accent):
    """小圖示：空心圓 → 虛線軌跡 → 實心星芒（像路線圖，起點到亮點）"""
    k = size / 100
    return (f'<g transform="translate({x} {y}) scale({k})">'
            f'<circle cx="13" cy="85" r="9" fill="none" stroke="{ink}" stroke-width="5.5"/>'
            f'<path d="M28 76 C44 70 38 48 55 40" fill="none" stroke="{accent}" stroke-width="5.5" stroke-linecap="round" stroke-dasharray="0.1 11"/>'
            f'<path d="M76 2 L82.5 19.5 L100 26 L82.5 32.5 L76 50 L69.5 32.5 L52 26 L69.5 19.5 Z" fill="{accent}"/>'
            f'</g>')

ZH_TRACK = 9      # 中文字距（像 JOTO 那樣疏一點但不拉到和英文同寬）

def vertical(dark=True, panel=True):
    """直式（仿 JOTO MOTO 側欄）：圖示、STAR／FUN／DEA、星樂創意、✕ 標語、小字"""
    ink, acc, sub = (WHITE, AMBER, MUTE) if dark else (NAVY, AMBER_L, '#5A6577')
    W, u = 560, 10.2
    x = 78; y = 236
    yb = y + 27 * u
    H = int(yb + 64 + 62 + 40 + 60)
    parts = []
    if dark and panel: parts.append(f'<rect width="{W}" height="{H}" rx="32" fill="{NAVY}"/>')
    parts.append(icon(x, 76, 88, ink, acc))
    s1, _ = word('STAR', x, y, u, ink); s2, _ = word('FUN', x, y + 9.5 * u, u, acc); s3, _ = word('DEA', x, y + 19 * u, u, ink)
    parts += [s1, s2, s3]
    parts.append(f'<text x="{x}" y="{yb + 62:.0f}" font-family="{CJK}" font-weight="700" font-size="25" letter-spacing="{ZH_TRACK}" fill="{ink}">星樂創意</text>')
    parts.append(f'<text x="{x}" y="{yb + 118:.0f}" font-family="{CJK}" font-weight="700" font-size="21" letter-spacing="3" fill="{ink}">把點子 <tspan fill="{acc}">✕</tspan> 走成亮點</text>')
    parts.append(f'<text x="{x}" y="{yb + 150:.0f}" font-family="{CJK}" font-weight="500" font-size="14" letter-spacing="3" fill="{sub}">餐飲店的數位好幫手</text>')
    return W, H, ''.join(parts)

def horizontal(dark=True):
    ink, acc = (WHITE, AMBER) if dark else (NAVY, AMBER_L)
    u = 6.4; g = 2.6 * u; x = 136
    a, wa = word('STAR', x, 48, u, ink); b, wb = word('FUN', x + wa + g, 48, u, acc); c, wc = word('DEA', x + wa + wb + 2 * g, 48, u, ink)
    tw = wa + wb + wc + 2 * g
    W = int(x + tw + 70); H = 150
    body = (icon(36, 30, 78, ink, acc) + a + b + c +
            f'<text x="{x}" y="{48 + 8 * u + 32:.0f}" font-family="{CJK}" font-weight="700" font-size="17" letter-spacing="8" fill="{ink}" opacity=".92">星樂創意</text>')
    if dark: body = f'<rect width="{W}" height="{H}" rx="24" fill="{NAVY}"/>' + body
    return W, H, body

def square(dark=True):
    """1:1 主標誌：四周大量留白，整組置中；中文自然字距、靠左對齊英文"""
    ink, acc, sub = (WHITE, AMBER, MUTE) if dark else (NAVY, AMBER_L, '#5A6577')
    W, u = 1024, 11.0
    wm = (4 * ADV - (ADV - 5)) * u
    x0 = (W - wm) / 2
    total = 100 + 50 + 27 * u + 70 + 20
    top = (W - total) / 2
    bg = f'<rect width="{W}" height="{W}" fill="{NAVY if dark else WHITE}"/>'
    y0 = top + 100 + 50
    s1, _ = word('STAR', x0, y0, u, ink); s2, _ = word('FUN', x0, y0 + 9.5 * u, u, acc); s3, _ = word('DEA', x0, y0 + 19 * u, u, ink)
    yb = y0 + 27 * u
    body = (bg + icon(x0, top, 100, ink, acc) + s1 + s2 + s3 +
            f'<text x="{x0:.0f}" y="{yb + 70:.0f}" font-family="{CJK}" font-weight="700" font-size="28" letter-spacing="{ZH_TRACK + 2}" fill="{ink}">星樂創意</text>')
    return W, W, body

def appicon():
    W = 512
    body = f'<rect width="{W}" height="{W}" rx="112" fill="{NAVY}"/>' + icon(96, 96, 320, WHITE, AMBER)
    return W, W, body

def svg(w, h, body): return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>'

FILES = {
    'starfundea-vertical-dark': vertical(True), 'starfundea-vertical-light': vertical(False),
    'starfundea-horizontal-dark': horizontal(True), 'starfundea-horizontal-light': horizontal(False),
    'starfundea-appicon': appicon(), 'starfundea-square-dark': square(True), 'starfundea-square-light': square(False),
}

SHEET = """<!doctype html><meta charset=utf-8><style>
body{margin:0;background:#EEF1F6;font-family:'Microsoft JhengHei','PingFang TC','Noto Sans TC',sans-serif;color:#0E1623;width:1600px}
.w{padding:56px 64px}
h1{margin:0;font-size:34px;letter-spacing:.04em}.sub{color:#5A6577;margin:6px 0 30px;font-size:17px}
.row{display:flex;gap:28px;align-items:stretch;margin-bottom:28px}
.c{background:#fff;border-radius:22px;padding:28px;box-shadow:0 2px 0 #DDE3EC;display:flex;flex-direction:column;gap:14px}
.c h2{margin:0;font-size:15px;letter-spacing:.14em;color:#5A6577}
.lt{background:#fff}.chips{display:flex;gap:14px}.chip{width:150px;height:96px;border-radius:14px;padding:12px;font-size:13px;display:flex;flex-direction:column;justify-content:flex-end;box-sizing:border-box}
.card{width:540px;height:324px;border-radius:6px;display:flex;overflow:hidden;box-shadow:0 8px 28px rgba(14,22,35,.25);font-size:14px}
.card .l{width:36%;background:#0E1623;padding:22px 20px;box-sizing:border-box}
.card .r{flex:1;background:#F4F7FB;padding:26px 28px;box-sizing:border-box;display:flex;flex-direction:column}
.card .nm{font-size:27px;font-weight:900;letter-spacing:.1em}.card .tt{color:#E58A00;font-weight:800;margin-top:4px}.card .ln{width:34px;height:4px;background:#FFB534;margin:12px 0 auto}
.card .ct{line-height:2.1;font-size:14.5px;font-weight:500}
</style><div class=w><h1>StarFunDea 品牌標誌</h1><div class=sub>星樂創意　·　一條虛線從起點走到亮點：把店裡的點子，變成每天用得到的工具</div>
<div class=row><div class=c><h2>直式（深色）</h2>{v1}</div><div class="c lt"><h2>直式（淺色）</h2>{v2}</div>
<div class=c style="flex:1"><h2>橫式</h2><div>{h1}</div><div>{h2}</div><h2 style="margin-top:8px">APP 圖示</h2><div style="display:flex;gap:20px;align-items:center"><div style="width:160px">{ap}</div><div style="width:96px">{ap}</div><div style="width:48px">{ap}</div></div></div></div>
<div class=row><div class=c><h2>色彩</h2><div class=chips>
<div class=chip style="background:#0E1623;color:#fff"><b>夜空藍</b>#0E1623</div><div class=chip style="background:#FFB534;color:#0E1623"><b>星光黃</b>#FFB534</div><div class=chip style="background:#F29A00;color:#fff"><b>淺底用黃</b>#F29A00</div><div class=chip style="background:#8FA0B8;color:#0E1623"><b>輔助灰藍</b>#8FA0B8</div><div class=chip style="background:#fff;color:#0E1623;box-shadow:inset 0 0 0 1px #DDE3EC"><b>白</b>#FFFFFF</div></div></div>
<div class=c style="flex:1"><h2>名片示意（正面）</h2><div class=card><div class=l>{mini}</div><div class=r><div class=nm>林星樂</div><div class=tt>創辦人 ｜ Founder</div><div class=ln></div><div class=ct>0912-345-678<br>LINE @starfundea<br>hello@starfundea.com<br>starfundea.com</div></div></div></div></div></div>"""

async def main():
    paths = {}
    for name, (w, h, body) in FILES.items():
        s = svg(w, h, body); paths[name] = s
        open(os.path.join(OUT, name + '.svg'), 'w', encoding='utf-8').write(s)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(device_scale_factor=2)
        for name, (w, h, body) in FILES.items():
            await pg.set_viewport_size({'width': w, 'height': h})
            await pg.set_content(f'<body style="margin:0;background:transparent">{paths[name]}</body>')
            await pg.screenshot(path=os.path.join(OUT, name + '.png'), omit_background=True, clip={'x': 0, 'y': 0, 'width': w, 'height': h})
        # 方形 1024 App 圖示
        await pg.set_viewport_size({'width': 512, 'height': 512})
        await pg.set_content(f'<body style="margin:0;background:transparent">{paths["starfundea-appicon"]}</body>')
        await pg.screenshot(path=os.path.join(OUT, 'starfundea-appicon-1024.png'), omit_background=True, clip={'x': 0, 'y': 0, 'width': 512, 'height': 512})
        # 品牌規範圖
        def fit(k, wpx): w, h, body = FILES[k]; return f'<div style="width:{wpx}px">{svg(w, h, body).replace("<svg ", "<svg style=\'width:100%;height:auto\' ", 1)}</div>'
        mw, mh, mbody = vertical(True, panel=False)
        mini = f'<div style="width:100%">{svg(mw, mh, mbody).replace("<svg ", "<svg style=\'width:100%;height:auto\' ", 1)}</div>'
        html = SHEET.replace('{v1}', fit('starfundea-vertical-dark', 380)).replace('{v2}', fit('starfundea-vertical-light', 380)) \
            .replace('{h1}', fit('starfundea-horizontal-dark', 520)).replace('{h2}', fit('starfundea-horizontal-light', 520)) \
            .replace('{ap}', fit('starfundea-appicon', 160).replace('<div style="width:160px">', '<div style="width:100%">', 1)).replace('{mini}', mini)
        await pg.set_viewport_size({'width': 1600, 'height': 1000})
        await pg.set_content(html)
        await pg.screenshot(path=os.path.join(OUT, 'starfundea-brand-sheet.png'), full_page=True)
        await b.close()
    print('已輸出：', sorted(os.listdir(OUT)))

if __name__ == '__main__':
    asyncio.run(main())
