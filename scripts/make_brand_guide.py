"""StarFunDea 品牌規範（PDF，16:9 共 16 頁）。仿 JOTO MOTO 的品牌風格：深色底、粗體大寫窄字、單色強調、虛線路徑圖示。
輸出：brand/StarFunDea-品牌規範.pdf，另輸出每頁 PNG 到 brand/guide/。
執行：python scripts/make_brand_guide.py（需要網路載入 Google Fonts：Barlow Condensed、Noto Sans TC）"""
import asyncio, os, re, importlib.util
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'brand'); PG = os.path.join(OUT, 'guide'); os.makedirs(PG, exist_ok=True)
spec = importlib.util.spec_from_file_location('mbl', os.path.join(ROOT, 'scripts', 'make_brand_logo.py'))
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
ICONLIB = open(os.path.join(ROOT, 'assets', 'sfd-icons.js'), encoding='utf-8').read()

def fit(key, style='width:100%;height:auto;display:block'):
    w, h, body = L.FILES[key]
    return L.svg(w, h, body).replace('<svg ', f'<svg style="{style}" ', 1)

def cmyk(hexv):
    r, g, b = [int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    k = 1 - max(r, g, b)
    if k >= 1: return (0, 0, 0, 100)
    return tuple(round(x * 100) for x in ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k))

COLORS = [('夜空藍', 'NIGHT BLUE', '#0E1623', '主背景、主要文字（淺底）'), ('星光黃', 'STAR AMBER', '#FFB534', '強調、重點字「FUN」、星芒'),
          ('深黃', 'DEEP AMBER', '#F29A00', '淺色底上的強調（對比度夠）'), ('灰藍', 'SLATE', '#8FA0B8', '輔助文字、說明、細線'), ('白', 'WHITE', '#FFFFFF', '深色底上的主要文字、留白')]
def chip(c, big=False):
    n, e, h, use = c
    dark = h in ('#0E1623', '#8FA0B8')
    fg = '#fff' if dark and h != '#8FA0B8' else '#0E1623'
    cm = cmyk(h); rgb = tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    return (f'<div class="chip" style="background:{h};color:{fg};{"box-shadow:inset 0 0 0 1.5px #D5DCE6;" if h == "#FFFFFF" else ""}"><div class="cn">{n}<small>{e}</small></div>'
            f'<div class="cv">HEX {h}<br>RGB {rgb[0]} {rgb[1]} {rgb[2]}<br>CMYK {cm[0]} {cm[1]} {cm[2]} {cm[3]}</div><div class="cu">{use}</div></div>')

def icon_i(name, size=22, stroke=2): return f'<i data-icon="{name}" data-size="{size}" data-stroke="{stroke}"></i>'

TOTAL = 16
def page(n, title, kicker, body, dark=False):
    return (f'<section class="pg {"dk" if dark else ""}"><div class="hd"><span class="k">{kicker}</span><span class="n">{n:02d} / {TOTAL}</span></div>'
            f'<h2>{title}</h2><div class="bd">{body}</div><div class="ft">STARFUNDEA · 星樂創意　品牌規範 v1.1</div></section>')

PAGES = []
# 1 封面
mw, mh, mbody = L.square(True)
PAGES.append(f'<section class="pg cover"><div class="cvl"><div class="kk">BRAND GUIDELINES　v1.1　2026-10-11</div><h1>STAR<br><b>FUN</b><br>DEA</h1><div class="zh">星樂創意　品牌規範</div><div class="sb">標誌　·　色彩　·　字體　·　圖形　·　應用　·　語氣</div></div><div class="cvr">{fit("starfundea-square-dark", "width:100%;height:100%;display:block")}</div></section>')
# 2 品牌概念
PAGES.append(page(2, '品牌概念：把點子，走成亮點', 'BRAND IDEA', f'''
<div class="cols3">
 <div class="cd"><div class="big">STAR</div><h3>星</h3><p>方向與亮點。一顆星代表每家店都有的特色，我們幫它被看見。</p></div>
 <div class="cd"><div class="big am">FUN</div><h3>樂</h3><p>好用、好玩、不繁瑣。工具是給忙碌的店家用的，使用起來要讓人輕鬆開心。</p></div>
 <div class="cd"><div class="big">DEA</div><h3>創意</h3><p>idea 的縮寫。從一個小點子出發，做成菜單、海報、班表，每天都用得到。</p></div>
</div>
<div class="story"><div class="mk">{fit("starfundea-appicon", "width:150px;height:auto")}</div><div><h3>圖示的意思</h3><p>左下角的<b>空心圓</b>是「起點」：一個還沒成形的點子。中間的<b>虛線</b>是「過程」：一步一步做出來。右上角的<b>星芒</b>是「亮點」：做完之後，被客人看見的樣子。</p><p class="tag">標語　把點子，走成亮點。　<span>From idea to spark.</span></p></div></div>'''))
# 3 主標誌 1:1
PAGES.append(page(3, '主標誌（1:1）', 'PRIMARY LOGO', f'''
<div class="split"><div class="sq">{fit("starfundea-square-dark", "width:100%;height:100%;display:block")}</div>
<div class="txt"><h3>正方形主標誌</h3><p>由圖示、三行大寫字母 STAR / FUN / DEA、中文「星樂創意」與副標組成，置中對齊，四邊留白一致。</p>
<ul><li><b>FUN</b> 一律用星光黃，另兩行用白色（淺底用夜空藍）</li><li>中文小而細，只當輔助，不與英文搶主角</li><li>社群頭像、App 商店、印章、封面都先用這個</li><li>檔案：<code>starfundea-square-dark / -light</code>（.svg 與 .png）</li></ul></div></div>'''))
# 4 標誌版本
PAGES.append(page(4, '標誌版本', 'LOGO VERSIONS', f'''
<div class="grid4">
 <div><div class="vb dkb">{fit("starfundea-vertical-dark", "height:100%;width:auto;display:block;margin:auto")}</div><b>直式・深色</b><small>名片、海報、深色背景</small></div>
 <div><div class="vb">{fit("starfundea-vertical-light", "height:100%;width:auto;display:block;margin:auto")}</div><b>直式・淺色</b><small>文件、淺色背景</small></div>
 <div><div class="vb hz">{fit("starfundea-horizontal-dark", "width:100%;height:auto")}{fit("starfundea-horizontal-light", "width:100%;height:auto;margin-top:12px")}</div><b>橫式</b><small>網站頁首、信件、簡報</small></div>
 <div><div class="vb ap">{fit("starfundea-appicon", "width:120px;height:auto")}<div style="display:flex;gap:12px;align-items:center;margin-top:14px">{fit("starfundea-appicon", "width:60px;height:auto")}{fit("starfundea-appicon", "width:32px;height:auto")}</div></div><b>App 圖示</b><small>只用星芒圖案，手機、網站圖示</small></div>
</div>'''))
# 5 安全空間與最小尺寸
w, h, body = L.FILES['starfundea-vertical-light']
PAGES.append(page(5, '安全空間與最小尺寸', 'CLEAR SPACE & MIN SIZE', f'''
<div class="split"><div class="cs"><div class="csb"><div class="csi">{fit("starfundea-vertical-light", "height:100%;width:auto;display:block")}</div><span class="x t">x</span><span class="x b">x</span><span class="x l">x</span><span class="x r">x</span></div></div>
<div class="txt"><h3>安全空間</h3><p>標誌四周要留出 <b>x</b> 的空白，x ＝ 字母「S」的寬度。這個範圍內不放文字、圖片或其他圖形。</p>
<h3 style="margin-top:22px">最小尺寸</h3>
<table><tr><th>版本</th><th>印刷</th><th>螢幕</th></tr><tr><td>直式 / 正方形</td><td>寬 25 mm</td><td>寬 80 px</td></tr><tr><td>橫式</td><td>寬 38 mm</td><td>寬 120 px</td></tr><tr><td>圖示（星芒）</td><td>寬 8 mm</td><td>寬 24 px</td></tr></table>
<p class="note">小於最小尺寸時，只用圖示，不要縮小整個標誌。</p></div></div>'''))
# 6 色彩
bar = ''.join(f'<i style="flex:{f};background:{c}"></i>' for f, c in ((60, '#0E1623'), (25, '#FFFFFF'), (10, '#FFB534'), (5, '#8FA0B8')))
PAGES.append(page(6, '色彩', 'COLOR', f'''<div class="chips">{''.join(chip(c) for c in COLORS)}</div>
<div class="ratio"><div class="rb">{bar}</div><div class="rl"><span>夜空藍 60%</span><span>白 25%</span><span>星光黃 10%</span><span>灰藍 5%</span></div></div>
<p class="note">星光黃用量要少而準：一個畫面最多一到兩個重點。CMYK 為依 RGB 換算的參考值，印刷前請用色票校色。</p>''', dark=False))
# 7 字體
PAGES.append(page(7, '字體', 'TYPOGRAPHY', f'''
<div class="cols3 ty">
 <div class="cd"><div class="sample en">STARFUN</div><h3>英文標題・Barlow Condensed</h3><p>Bold 700／ExtraBold 800，一律大寫，字距 +6%。數字、電話、價格也用它。</p></div>
 <div class="cd"><div class="sample zh">星樂創意</div><h3>中文標題・Noto Sans TC</h3><p>Black 900／Bold 700，字距 +8%，標題不超過 12 字。</p></div>
 <div class="cd"><div class="sample bodyt">把店裡的點子，<br>變成每天用得到的工具。</div><h3>內文・Noto Sans TC</h3><p>Regular 400／Medium 500，行距 1.6，一行最多約 30 字。</p></div>
</div>
<div class="hier"><div><span class="h1">STAR FUN DEA</span><small>H1　Barlow Condensed 800・38/44</small></div><div><span class="h2">把點子，走成亮點</span><small>H2　Noto Sans TC 900・32/40</small></div><div><span class="h3t">服務內容與聯絡方式</span><small>H3　Noto Sans TC 700・20/28</small></div><div><span class="bt">這是內文範例，用來說明一般說明文字的大小與行距。</span><small>內文　Noto Sans TC 400・16/26</small></div></div>'''))
# 8 圖示與圖形
icons = ['coffee', 'utensils', 'calendar-check', 'users', 'clock', 'megaphone', 'qr-code', 'palette']
PAGES.append(page(8, '圖示與輔助圖形', 'ICONS & GRAPHICS', f'''
<div class="split"><div class="txt"><h3>星樂創意圖示庫（線條圖示）</h3><p>全部使用同一套 Lucide 線條圖示：線條粗細 <b>2</b>、圓角、單色。顏色跟著文字顏色，深底用白色或星光黃，淺底用夜空藍。</p>
<div class="icg">{''.join(f'<div>{icon_i(n, 30)}</div>' for n in icons)}</div><p class="note">不要把圖示填滿、加陰影，或混用別套圖示。</p></div>
<div class="gfx"><h3>虛線路徑</h3><svg viewBox="0 0 400 120" style="width:100%"><circle cx="30" cy="90" r="12" fill="none" stroke="#fff" stroke-width="7"/><path d="M50 82 C120 70 130 30 210 36 S330 60 370 22" fill="none" stroke="#FFB534" stroke-width="7" stroke-linecap="round" stroke-dasharray="0.1 15"/><path d="M370 0 L378 18 L396 26 L378 34 L370 52 L362 34 L344 26 L362 18 Z" fill="#FFB534" transform="translate(0 -4)"/></svg>
<p>起點（空心圓）→ 虛線（過程）→ 星芒（亮點）。用在封面、分隔線、流程圖。虛線永遠是圓點，不用斜線。</p></div></div>'''))
# 9 錯誤用法
bad = [('不要拉伸變形', 'transform:scaleX(1.45)'), ('不要旋轉', 'transform:rotate(-14deg)'), ('不要換色', 'filter:hue-rotate(150deg) saturate(1.6)'), ('不要加陰影或外框', 'filter:drop-shadow(5px 6px 0 #f55)'), ('不要放在花雜的背景', ''), ('對比不足', '')]
cells = ''
for i, (t, st) in enumerate(bad):
    bg = {4: 'background:repeating-linear-gradient(45deg,#d9a,#d9a 12px,#7ad 12px,#7ad 24px)', 5: 'background:#FFB534'}.get(i, 'background:#fff')
    logo = fit('starfundea-vertical-light', f'height:100%;width:auto;display:block;{st}') if i != 5 else fit('starfundea-vertical-dark', 'height:100%;width:auto;display:block')
    cells += f'<div><div class="bx" style="{bg}">{logo}<em>✕</em></div><b>{t}</b></div>'
PAGES.append(page(9, '錯誤用法', "DON'T", f'<div class="grid6">{cells}</div>'))
# 10 名片
def chk(name): return icon_i(name, 18, 2)
card_front = f'''<div class="cardf"><div class="cl">{fit("starfundea-vertical-dark", "width:100%;height:auto;display:block")}</div><div class="cr"><div class="nm">姓名（待補）</div><div class="en">NAME</div><div class="tt">職稱（待補）｜TITLE</div><div class="ln"></div><div class="ct"><div>{chk("phone")}電話（待補）</div><div>{chk("message-circle")}LINE（待補）</div><div>{chk("mail")}Email（待補）</div><div>{chk("link")}網址（待補）</div></div></div></div>'''
card_back = f'''<div class="cardb"><div class="cb1"><span class="eb">OUR FOCUS</span><div class="hh">把點子，走成亮點！</div><div class="rule"></div></div><div class="cb2"><div class="sv"><div class="sh">SERVICES</div><div>{chk("book-open")}餐飲菜單與海報</div><div>{chk("clock")}員工打卡與排班</div><div>{chk("megaphone")}品牌與宣傳設計</div><div>{chk("qr-code")}桌號 QR 與名片</div></div><div class="qr"><div class="qb">QR<br>待補</div><div class="qt"><b>掃描了解</b><br>連結待補<br>確認後再放</div></div></div></div>'''
PAGES.append(page(10, '應用：名片（90 × 54 mm）', 'BUSINESS CARD', f'<div class="cards">{card_front}{card_back}</div><p class="note">正面：深色側欄放標誌，右側放姓名與聯絡資訊（尚未提供，一律標「待補」，不使用假資料）。背面：淺底，用大標、編號重點、服務清單和 QR 區。印刷請含 3 mm 出血，名片產生器可直接輸出。</p>'))
# 11 社群與文具
PAGES.append(page(11, '應用：社群、信件與 App', 'APPLICATIONS', f'''
<div class="apps">
 <div><div class="av">{fit("starfundea-square-dark", "width:100%;height:auto;display:block;border-radius:50%")}</div><b>社群頭像</b><small>正方形主標誌，圓形裁切仍完整</small></div>
 <div class="wide"><div class="cover2"><div class="c2l">{fit("starfundea-horizontal-dark", "width:70%;height:auto")}</div><div class="c2t">把點子，走成亮點。</div></div><b>封面圖</b><small>橫式標誌＋標語，深色底</small></div>
 <div><div class="letter"><div class="lh">{fit("starfundea-horizontal-light", "width:100%;height:auto")}</div><div class="ll"></div><div class="ll s"></div><div class="ll"></div><div class="ll s"></div></div><b>信紙抬頭</b><small>橫式（淺色）靠左上</small></div>
 <div><div class="phone"><div class="pi">{fit("starfundea-appicon", "width:70px;height:auto")}</div><span>星樂菜單</span></div><b>App 圖示</b><small>桌面名稱用「星樂＋功能」</small></div>
</div>'''))
# 12 語氣與檔案
PAGES.append(page(12, '語氣與檔案清單', 'VOICE & FILES', f'''
<div class="split"><div class="txt"><h3>說話的方式</h3><div class="tags"><span>明亮</span><span>直接</span><span>好用</span><span>有溫度</span></div>
<ul><li>用店家聽得懂的話，不講術語（說「寄班表」，不說「推播排程」）</li><li>一句話講一件事，先講結果再講步驟</li><li>鼓勵但不誇大：「一次設好，之後都省事」</li><li>標語：<b>把點子，走成亮點。</b>　英文：From idea to spark.</li></ul>
<h3 style="margin-top:20px">範例</h3><p class="ex">✕　系統已完成排程推播作業。<br>○　班表寄出去了，3 位員工收到。<br>✕　超值優惠，全方位一站式服務！<br>○　14 天免費試用，輸出有「試用版」浮水印。</p></div>
<div class="txt"><h3>檔案清單（brand/ 資料夾）</h3><table class="files"><tr><td>starfundea-square-dark / -light</td><td>1:1 主標誌</td></tr><tr><td>starfundea-vertical-dark / -light</td><td>直式</td></tr><tr><td>starfundea-horizontal-dark / -light</td><td>橫式</td></tr><tr><td>starfundea-appicon（-1024.png）</td><td>App 圖示</td></tr><tr><td>starfundea-brand-sheet.png</td><td>一頁式總覽</td></tr><tr><td>guide/*.png</td><td>本規範每頁圖片</td></tr></table><p class="note">每個標誌都有 .svg（向量）與 .png（透明背景）。SVG 內的中文是文字，送印前請轉成外框。</p></div></div>'''))

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap');
:root{--navy:#0E1623;--amber:#FFB534;--deep:#F29A00;--slate:#8FA0B8;--bg:#EEF1F6;--line:#D5DCE6}
*{box-sizing:border-box}@page{size:1600px 900px;margin:0}
body{margin:0;font-family:'Noto Sans TC','Microsoft JhengHei',sans-serif;color:var(--navy);-webkit-print-color-adjust:exact;print-color-adjust:exact}
.pg{width:1600px;height:900px;position:relative;overflow:hidden;background:#fff;page-break-after:always;padding:76px 96px 70px}
.pg.dk{background:var(--navy);color:#fff}
.hd{position:absolute;top:40px;left:96px;right:96px;display:flex;justify-content:space-between;font-family:'Barlow Condensed';font-weight:600;letter-spacing:.2em;font-size:17px;color:var(--slate)}
.pg h2{margin:22px 0 28px;font-size:44px;font-weight:900;letter-spacing:.04em}
.ft{position:absolute;bottom:30px;left:96px;font-family:'Barlow Condensed';letter-spacing:.18em;font-size:14px;color:var(--slate)}
.bd{height:640px}
.cover{background:var(--navy);color:#fff;display:flex;padding:0}
.cvl{flex:1;padding:96px 0 0 110px;display:flex;flex-direction:column}
.kk{font-family:'Barlow Condensed';letter-spacing:.3em;font-size:20px;color:var(--slate)}
.cover h1{font-family:'Barlow Condensed';font-weight:800;font-size:104px;line-height:.94;letter-spacing:.05em;margin:56px 0 0}.cover h1 b{color:var(--amber)}
.zh{margin-top:34px;font-size:30px;font-weight:700;letter-spacing:.3em}.sb{margin-top:16px;color:var(--slate);letter-spacing:.2em;font-size:17px}
.cvr{width:900px;height:900px}
.cols3{display:flex;gap:28px}.cd{flex:1;background:var(--bg);border-radius:20px;padding:30px 32px}
.cd .big{font-family:'Barlow Condensed';font-weight:800;font-size:54px;letter-spacing:.06em;line-height:1}.cd .big.am{color:var(--deep)}
.cd h3{margin:10px 0 8px;font-size:24px}.cd p{margin:0;line-height:1.7;font-size:18px;color:#3b4658}
.story{display:flex;gap:40px;align-items:center;margin-top:34px;background:var(--navy);color:#fff;border-radius:22px;padding:34px 44px}
.story h3{margin:0 0 8px;font-size:22px;color:var(--amber)}.story p{margin:6px 0;line-height:1.8;font-size:18px}.tag{font-weight:700}.tag span{font-family:'Barlow Condensed';letter-spacing:.1em;color:var(--slate);margin-left:12px}
.split{display:flex;gap:56px;align-items:center;height:100%}.sq{width:560px;height:560px;border-radius:24px;overflow:hidden;box-shadow:0 14px 40px rgba(14,22,35,.28);flex:0 0 auto}
.txt{flex:1;font-size:19px;line-height:1.75}.txt h3{margin:0 0 8px;font-size:26px}.txt p{margin:6px 0}.txt ul{padding-left:22px;margin:10px 0}.txt li{margin:6px 0}
code{background:var(--bg);padding:2px 8px;border-radius:6px;font-size:15px}.note{color:#5a6577;font-size:16px;margin-top:14px}
.grid4{display:flex;gap:26px}.grid4>div{flex:1}.vb{height:480px;border-radius:20px;background:#fff;box-shadow:inset 0 0 0 1.5px var(--line);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:18px;margin-bottom:12px}
.vb.dkb{background:var(--navy);box-shadow:none}.vb.hz{gap:0}.grid4 b{display:block;font-size:20px}.grid4 small{color:#5a6577;font-size:15px}
.cs{flex:0 0 560px;height:560px;background:var(--bg);border-radius:20px;display:flex;align-items:center;justify-content:center}
.csb{position:relative;width:340px;height:480px;border:2px dashed var(--deep);padding:50px}.csi{width:100%;height:100%;outline:1.5px solid var(--line)}
.x{position:absolute;font-family:'Barlow Condensed';font-weight:700;color:var(--deep);font-size:22px;background:#fff;padding:0 6px}.x.t{top:10px;left:50%}.x.b{bottom:10px;left:50%}.x.l{left:14px;top:50%}.x.r{right:14px;top:50%}
table{border-collapse:collapse;width:100%;font-size:18px;margin-top:8px}th,td{text-align:left;padding:10px 14px;border-bottom:1.5px solid var(--line)}th{color:#5a6577;font-weight:500}
.chips{display:flex;gap:18px}.chip{flex:1;height:340px;border-radius:20px;padding:22px 20px;display:flex;flex-direction:column;justify-content:space-between}
.cn{font-size:26px;font-weight:900}.cn small{display:block;font-family:'Barlow Condensed';letter-spacing:.18em;font-size:14px;font-weight:600;opacity:.8}.cv{font-family:'Barlow Condensed';font-weight:500;font-size:18px;line-height:1.5;letter-spacing:.04em}.cu{font-size:14px;line-height:1.5;opacity:.9}
.ratio{margin-top:30px}.rb{display:flex;height:44px;border-radius:12px;overflow:hidden;box-shadow:inset 0 0 0 1.5px var(--line)}.rb i{display:block}.rl{display:flex;margin-top:10px;font-size:16px;color:#5a6577;gap:30px}
.ty .sample{height:150px;display:flex;align-items:center}.sample.en{font-family:'Barlow Condensed';font-weight:800;font-size:64px;letter-spacing:.06em}.sample.zh{font-weight:900;font-size:62px;letter-spacing:.08em}.sample.bodyt{font-size:24px;line-height:1.6;font-weight:500}
.hier{margin-top:26px;display:grid;grid-template-columns:1fr 1fr;gap:12px 40px}.hier small{display:block;color:#5a6577;font-size:14px;margin-top:2px}
.h1{font-family:'Barlow Condensed';font-weight:800;font-size:38px;letter-spacing:.06em}.h2{font-weight:900;font-size:32px}.h3t{font-weight:700;font-size:20px}.bt{font-size:16px;line-height:1.6}
.icg{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:16px 0}.icg div{height:84px;border-radius:16px;background:var(--bg);display:flex;align-items:center;justify-content:center}.icg svg{color:var(--navy)}
.gfx{flex:0 0 560px;background:var(--navy);color:#fff;border-radius:22px;padding:34px 38px;font-size:18px;line-height:1.7}.gfx h3{margin:0 0 12px;font-size:24px;color:var(--amber)}
.grid6{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:18px}.grid6>div{min-width:0}.bx{position:relative;height:330px;min-width:0;border-radius:16px;box-shadow:inset 0 0 0 1.5px var(--line);display:flex;align-items:center;justify-content:center;padding:26px;overflow:hidden}
.bx em{position:absolute;top:10px;right:12px;font-style:normal;color:#fff;background:#E5484D;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px}.grid6 b{display:block;margin-top:10px;font-size:17px}
.cards{display:flex;gap:36px;justify-content:center;margin-top:24px}
.cardf,.cardb{width:690px;height:414px;border-radius:8px;overflow:hidden;box-shadow:0 12px 36px rgba(14,22,35,.28);display:flex}
.cl{width:36%;background:var(--navy);padding:26px 24px}.cr{flex:1;background:#F4F7FB;padding:34px 36px;display:flex;flex-direction:column}
.nm{font-size:34px;font-weight:900;letter-spacing:.14em}.en{font-family:'Barlow Condensed';font-weight:600;letter-spacing:.12em;color:#5a6577;font-size:20px}.tt{color:var(--deep);font-weight:700;margin-top:6px;font-size:18px}.ln{width:46px;height:5px;background:var(--amber);margin:16px 0 auto}
.ct{font-family:'Barlow Condensed';font-weight:500;font-size:22px;letter-spacing:.04em;line-height:2.1}.ct div{display:flex;align-items:center;gap:12px}.ct svg{color:var(--deep)}
.cardb{background:#fff;flex-direction:column;padding:28px 34px;box-shadow:0 12px 36px rgba(14,22,35,.28),inset 0 0 0 1px #E3E8F0}
.eb{font-family:'Barlow Condensed';letter-spacing:.28em;font-weight:600;color:var(--deep);font-size:16px}.hh{font-size:30px;font-weight:900;margin-top:4px}.rule{height:2px;background:var(--line);margin:12px 0}
.cb2{display:flex;gap:22px;flex:1;align-items:stretch;margin-top:6px}.sv{flex:1;font-size:17px;font-weight:700;line-height:2.1}.sv>div{display:flex;align-items:center;gap:10px}.sv svg{color:var(--deep)}.sh{font-family:'Barlow Condensed';letter-spacing:.24em;color:#5a6577;font-size:15px;line-height:1.4;margin-bottom:4px}
.qr{width:230px;display:flex;gap:12px;align-items:flex-end}.qb{width:96px;height:96px;border:2.5px dashed #8FA0B8;border-radius:10px;display:flex;align-items:center;justify-content:center;font-family:'Barlow Condensed';font-weight:700;color:#5a6577;text-align:center;line-height:1.2}.qt{font-size:14px;line-height:1.5}.qt b{color:var(--deep);font-size:16px}
.apps{display:flex;gap:30px;align-items:flex-start}.apps>div{width:260px}.apps .wide{width:560px}.apps b{display:block;margin-top:12px;font-size:19px}.apps small{color:#5a6577;font-size:15px}
.av{width:260px;height:260px;border-radius:50%;overflow:hidden;box-shadow:0 8px 24px rgba(14,22,35,.25)}.cover2{height:260px;border-radius:16px;background:var(--navy);color:#fff;padding:32px;display:flex;flex-direction:column;justify-content:space-between}.c2t{font-weight:900;letter-spacing:.2em;font-size:24px;color:var(--amber)}
.letter{height:360px;border-radius:8px;background:#fff;box-shadow:0 8px 24px rgba(14,22,35,.2),inset 0 0 0 1px var(--line);padding:26px}.lh{width:70%}.ll{height:9px;background:var(--bg);border-radius:5px;margin-top:20px}.ll.s{width:70%}
.phone{height:260px;border-radius:28px;background:linear-gradient(160deg,#27405f,#0E1623);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:#fff;font-size:17px;font-weight:700}.pi{width:70px}
.tags{display:flex;gap:10px;margin:8px 0 14px}.tags span{background:var(--navy);color:var(--amber);border-radius:999px;padding:6px 18px;font-weight:700}.ex{background:var(--bg);border-radius:14px;padding:16px 22px;line-height:2}
.files td{font-size:16px}.files td:first-child{font-family:'Barlow Condensed';font-weight:600;letter-spacing:.04em;font-size:18px}
i[data-icon]{display:inline-flex}svg.hl-icon{vertical-align:middle}
"""


# ---- v1.1 新增頁：名稱規則、版面與元件、影像規則、聯絡資訊與授權 ----
import base64 as _b64
def _img(f): return '<img src="data:image/jpeg;base64,' + _b64.b64encode(open(os.path.join(ROOT, 'site', 'photos', f), 'rb').read()).decode() + '">'
NAMES = page(0, '名稱規則', 'NAMING', f'''
<div class="split"><div class="txt"><h3>一定這樣寫</h3>
<table><tr><td>品牌</td><td><b>星樂創意 StarFunDea</b>（簡稱 SFD）</td></tr><tr><td>產品</td><td><b>SFD 系統</b></td></tr><tr><td>使用指南</td><td><b>SFD系統使用指南</b></td></tr><tr><td>標語</td><td><b>把點子，走成亮點。</b>／From idea to spark.</td></tr></table>
<p class="note">中文名與英文名並列時，順序是「星樂創意 StarFunDea」，中間一個半形空格。</p></div>
<div class="txt"><h3>寫法規則</h3><ul><li>只用以上名稱，不自創簡稱，也不沿用舊稱或候選名稱</li><li>範例店名用「示範早午餐店」這類通用說法，不用真實店名與客戶資料</li><li>對外一律說「網頁版，可加到手機主畫面」，不說 App 上架</li><li>不做 POS、金流代收、即時庫存，文案不暗示有這些功能</li></ul></div></div>''')
LAYOUT = page(0, '版面與元件', 'LAYOUT & COMPONENTS', f'''
<div class="split" style="gap:34px"><div class="lyh"><div class="lk">FROM IDEA TO SPARK.</div><div class="lt">老闆改一次價格，<b>菜單、海報、QR</b> 一起更新</div><div class="ls">一句副標，說明這一屏要做什麼。</div><div class="lb">免費試用 14 天</div></div>
<div class="txt"><h3>首屏</h3><p>深藍底：標語小字 → 主標 → 一句副標 → <b>一個</b>主要按鈕。</p>
<h3 style="margin-top:14px">卡片與按鈕</h3><div class="lcards"><div class="lc"><b>卡片</b><small>白底、淺邊框、圓角 18–24px，不堆陰影</small></div><div class="lbtns"><span class="bp">主要：琥珀底</span><span class="bs">次要：細邊框</span></div></div>
<ul><li>按鈕高度 ≥ 48px，圓角 14px，每一屏只有一個主要按鈕</li><li>圖示用星樂創意圖示庫，琥珀或深藍單色</li><li>手機寬度 390px 不可橫向捲動；寧可少放內容，不縮小字級</li></ul></div></div>''')
IMAGERY = page(0, '影像規則', 'IMAGERY', f'''
<div class="split" style="gap:34px"><div class="ph2">{_img('store-cafe.jpg')}{_img('service-menu.jpg')}</div>
<div class="txt"><h3>情境照</h3><ul><li>寫實攝影、自然柔和光線、色調偏暖、背景簡潔</li><li><b>照片本身不含任何文字與標誌</b>，Logo 與 QR 一律事後用官方檔貼上</li><li>AI 生成的人物是虛構的，不稱為客戶或見證；客戶專屬畫面用真實拍攝</li><li>照片上放 Logo 時，先壓一層深藍漸層</li></ul>
<h3 style="margin-top:14px">樣品與檔案</h3><ul><li>空白封面的書、桌牌，透視貼上官方 Logo 與可掃的 QR，貼完要解碼驗證</li><li>JPG、長邊 ≤ 2000px、小於 400KB</li><li>商用前確認生成工具的商用條款，必要時標示 AI 生成</li></ul></div></div>''')
CONTACT = page(0, '聯絡資訊與授權', 'CONTACT & LICENSE', f'''
<div class="split"><div class="txt"><h3>聯絡資訊</h3>
<table><tr><td>公司登記名稱</td><td class="tbd">待補</td></tr><tr><td>統一編號</td><td class="tbd">待補</td></tr><tr><td>地址</td><td class="tbd">待補</td></tr><tr><td>電話</td><td class="tbd">待補</td></tr><tr><td>LINE</td><td class="tbd">待補</td></tr><tr><td>Email</td><td class="tbd">待補</td></tr><tr><td>官網</td><td>https://034588229a-max.github.io/starfundea/</td></tr></table></div>
<div class="txt"><h3>商標與授權</h3>
<table><tr><td>商標登記</td><td class="tbd">待補</td></tr><tr><td>網域</td><td class="tbd">待補</td></tr><tr><td>標誌授權範圍</td><td class="tbd">待補（依合約）</td></tr></table>
<p class="note">標示「待補」的資料尚未提供，確認後再填入，不使用假資料。對外寄送本規範前先經店主同意。</p></div></div>''')
PAGES.insert(2, NAMES)
PAGES.insert(9, LAYOUT)
PAGES.insert(10, IMAGERY)
PAGES.append(CONTACT)
import re as _re
for _i in range(len(PAGES)):
    PAGES[_i] = _re.sub(r'<span class="n">\d\d / \d\d</span>', f'<span class="n">{_i + 1:02d} / {len(PAGES)}</span>', PAGES[_i])
CSS += """
.lyh{flex:0 0 640px;height:460px;border-radius:22px;background:radial-gradient(120% 90% at 30% 10%,#1b2a45 0,#0E1623 62%);color:#fff;padding:56px 54px;display:flex;flex-direction:column;justify-content:center}
.lk{font-family:'Barlow Condensed';letter-spacing:.24em;color:var(--slate);font-size:18px;font-weight:600}.lt{font-size:40px;font-weight:900;line-height:1.3;margin-top:12px}.lt b{color:var(--amber)}.ls{color:#b8c4d6;font-size:19px;margin-top:12px}
.lb{margin-top:28px;align-self:flex-start;background:var(--amber);color:var(--navy);font-weight:900;font-size:20px;padding:14px 30px;border-radius:14px}
.lcards{display:flex;gap:18px;align-items:center;margin:8px 0 12px}.lc{flex:1;background:#fff;border:1.5px solid var(--line);border-radius:20px;padding:16px 20px}.lc b{display:block;font-size:20px}.lc small{color:#5a6577;font-size:15px}
.lbtns{display:flex;flex-direction:column;gap:10px}.bp,.bs{display:block;text-align:center;font-weight:700;font-size:16px;padding:12px 22px;border-radius:14px}.bp{background:var(--amber);color:var(--navy)}.bs{border:1.5px solid var(--navy)}
.ph2{flex:0 0 560px;display:flex;gap:14px}.ph2 img{width:273px;height:420px;object-fit:cover;border-radius:18px;display:block}
.tbd{color:var(--deep);font-weight:700}
"""

async def main():
    html = f'<!doctype html><meta charset=utf-8><style>{CSS}</style><body>' + ''.join(PAGES) + f'<script>{ICONLIB}\nhlIcon.render();</script>'
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1600, 'height': 900})
        await pg.set_content(html, wait_until='networkidle')
        await pg.evaluate('document.fonts.ready')
        await pg.wait_for_timeout(600)
        await pg.pdf(path=os.path.join(OUT, 'StarFunDea-品牌規範.pdf'), width='1600px', height='900px', print_background=True)
        els = await pg.query_selector_all('section.pg')
        for i, el in enumerate(els, 1):
            await el.screenshot(path=os.path.join(PG, f'page-{i:02d}.png'))
        await b.close()
    print('完成：', len(PAGES), '頁')

asyncio.run(main())
