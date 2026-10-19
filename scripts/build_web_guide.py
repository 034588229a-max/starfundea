"""網頁版使用指南：依官網五大類拆成獨立頁面，截圖用 shots/*.webp（延遲載入）。
內容來自 scripts/make_merchant_guide.py 的 CHAPTERS（PDF 版仍由該檔產生）。執行：python scripts/build_web_guide.py"""
import ast, os, re, html, importlib.util
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'scripts', 'make_merchant_guide.py'), encoding='utf-8').read()
CH = {c[0]: c[2] for c in ast.literal_eval(re.search(r'CHAPTERS = (\[.*?\n\])', src, re.S).group(1))}
spec = importlib.util.spec_from_file_location('site', os.path.join(ROOT, 'scripts', 'build_site_v2.py'))
def esc(s): return html.escape(s, quote=True)
def fmt(s): return ''.join(('<b>' + esc(p) + '</b>') if i % 2 else esc(p) for i, p in enumerate(s.split('**')))
def items(ch, only=None, skip=()):
    return [it for it in CH[ch] if (only is None or it[0] in only) and it[0] not in skip]
GROUPS = [
 ('staff', '人事管理', items('人員與班表') + items('店務', only=['交接紀錄']) + items('行銷', only=['徵才海報與面試登記'])),
 ('marketing', '行銷管理', items('菜單') + items('行銷', skip=['徵才海報與面試登記'])),
 ('finance', '收支管理', items('財務：店務收支')),
 ('customer', '顧客服務', items('店務', only=['店休日曆'])),
 ('setup', '開店與帳號', items('開始使用') + items('設定與帳號') + items('常見問題')),
]
# 共用官網的頁首、頁尾與樣式（只執行 build_site_v2 的函式定義，不重新輸出官網）
code = open(os.path.join(ROOT, 'scripts', 'build_site_v2.py'), encoding='utf-8').read()
code = code.split("os.makedirs(os.path.join(ROOT, 'features')")[0]
ns = {'__file__': os.path.join(ROOT, 'scripts', 'build_site_v2.py')}; exec(code, ns)
CSS = '<style>.gtopic{display:grid;grid-template-columns:1fr 280px;gap:32px;padding:40px 0;border-bottom:1px solid var(--line);scroll-margin-top:130px}.gtopic ol{padding-left:22px}.gtopic li{margin:8px 0}.tip{background:#FFF7E6;border-radius:12px;padding:12px 16px;margin-top:12px;font-size:15px}.tip b{margin-right:8px;color:var(--amb)}.gnum{font-family:var(--num);color:var(--amb);font-weight:700;letter-spacing:.1em}.gcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:32px 0}@media(max-width:860px){.gtopic{grid-template-columns:1fr}}</style>'
os.makedirs(os.path.join(ROOT, 'guide'), exist_ok=True)
for gi, (gid, gname, its) in enumerate(GROUPS):
    sub = ''.join('<a href="#t%d">%s</a>' % (i + 1, esc(it[0])) for i, it in enumerate(its))
    topics = []
    for i, (title, one, steps, tip, shot) in enumerate(its):
        vis = ns['phone'](shot, '系統實際畫面，可上下滑動', '../') if shot and os.path.exists(os.path.join(ROOT, 'shots', shot + '.webp')) else '<div></div>'
        topics.append('<section class="gtopic" id="t%d"><div><div class="gnum">%d.%d</div><h2 style="font-size:24px">%s</h2><p class="lead">%s</p><ol>%s</ol>%s</div>%s</section>' % (
            i + 1, gi + 1, i + 1, esc(title), esc(one), ''.join('<li>%s</li>' % fmt(s) for s in steps), ('<div class="tip"><b>小提醒</b>%s</div>' % esc(tip)) if tip else '', vis))
    body = (CSS + '<section class="sec dark"><div class="wrap"><p class="crumb"><a href="index.html">使用指南</a> ／ %s</p><h1 style="font-size:clamp(28px,5vw,40px);font-weight:900">%s 使用指南</h1><p class="lead">一步一步的操作說明，畫面都是系統實際畫面。</p></div></section>'
            '<div class="subnav"><div class="wrap">%s</div></div><div class="wrap">%s<div class="next"><a class="btn pri" href="../features/%s.html">看「%s」功能介紹</a><a class="btn ghost" style="color:var(--ink);border-color:var(--line)" href="index.html">回使用指南目錄</a></div></div>') % (esc(gname), esc(gname), sub, ''.join(topics), gid, esc(gname))
    open(os.path.join(ROOT, 'guide', gid + '.html'), 'w', encoding='utf-8').write(ns['page']('%s 使用指南｜星樂創意 StarFunDea' % gname, gname + '的操作步驟與實際畫面', '../', body))
cards = ''.join('<a class="cat" href="%s.html"><h3>%s</h3><p>%d 個主題：%s</p><span class="go">開始看 →</span></a>' % (g, esc(n), len(its), esc('、'.join(it[0] for it in its[:4])) + ('…' if len(its) > 4 else '')) for g, n, its in GROUPS)
body = (CSS + '<section class="sec dark"><div class="wrap"><p class="eyebrow">MERCHANT GUIDE</p><h1 style="font-size:clamp(30px,5vw,44px);font-weight:900">SFD 系統使用指南</h1><p class="lead">依五大類分開，點你要用的那一類就好。</p></div></section>'
        '<div class="wrap"><div class="gcards">%s</div><p class="note">要印出來看？<a href="SFD系統使用指南.pdf">下載完整 PDF 版</a>。</p></div>') % cards
open(os.path.join(ROOT, 'guide', 'index.html'), 'w', encoding='utf-8').write(ns['page']('SFD 系統使用指南｜星樂創意 StarFunDea', '依人事、行銷、收支、顧客服務、開店與帳號分類的操作說明', '../', body))
for g in ['index'] + [x[0] for x in GROUPS]: print('guide/%s.html' % g, os.path.getsize(os.path.join(ROOT, 'guide', g + '.html')) // 1024, 'KB')
