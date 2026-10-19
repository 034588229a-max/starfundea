"""官網 v2：首頁只放五大類入口，各功能依分類獨立成頁；畫面一律用真實系統截圖（shots/*.webp，
由 sfd 正本的 scripts/make_guide_shots.py 產生後轉 WebP）。
執行：python scripts/build_site_v2.py   （讀舊版 index.html 的樣式與價格、FAQ 段落，輸出 index.html、features/*.html、assets/）
"""
import os, re, html, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_INDEX = os.path.join(ROOT, 'scripts', 'legacy_index.html')
if not os.path.exists(SRC_INDEX):
    import shutil; shutil.copy(os.path.join(ROOT, 'index.html'), SRC_INDEX)
old = open(SRC_INDEX, encoding='utf-8').read()
APP = 'https://script.google.com/macros/s/AKfycbwPhHfsMZ-cXx3r_YLv1hQsk6lf_isDBN8GXybqTb46qKceAC8CVXhhpi6WWPTAYGE/exec'

# ---------- 共用樣式：沿用舊版品牌樣式，加上新版元件 ----------
base_css = re.search(r'<style[^>]*>(.*?)</style>', old, re.S).group(1)
NEW_CSS = """
.hero{padding:56px 0 48px;background:var(--navy);color:#fff}
.hero .in{display:grid;grid-template-columns:1.15fr .85fr;gap:40px;align-items:center}
.hero h1{font-size:clamp(30px,5vw,48px);font-weight:900}.hero h1 b{color:var(--orange)}
.hero .sub{color:#b8c4d6;font-size:18px;margin:16px 0 24px}
.hero .acts{display:flex;gap:12px;flex-wrap:wrap}.btn.ghost{border-color:#3a4a66;color:#fff;background:transparent}
.cats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-top:32px}
.cat{display:flex;flex-direction:column;gap:6px;padding:22px;border:1px solid var(--line);border-radius:18px;background:#fff;text-decoration:none;transition:transform .15s,box-shadow .15s}
.cat:hover{transform:translateY(-3px);box-shadow:0 12px 28px rgba(14,22,35,.10)}
.cat .ic{font-size:26px}.cat h3{font-size:20px;font-weight:900}.cat p{margin:0;color:var(--mute);font-size:14.5px}
.cat .go{margin-top:auto;padding-top:8px;font-weight:700;color:var(--amb)}
.phone{margin:0;width:100%;max-width:300px;justify-self:center}
.phone .scr{height:560px;overflow-y:auto;border:10px solid var(--navy3);border-radius:34px;background:#fff;box-shadow:0 18px 40px rgba(14,22,35,.25);overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
.phone .scr img{display:block;width:100%;height:auto}
.phone figcaption{text-align:center;font-size:13px;color:var(--mute);margin-top:10px}.dark .phone figcaption,.hero .phone figcaption{color:#b8c4d6}
.subnav{position:sticky;top:64px;z-index:5;background:#fff;border-bottom:1px solid var(--line)}
.subnav .wrap{display:flex;gap:8px;overflow-x:auto;padding-block:10px;scrollbar-width:none}
.subnav a{flex:none;padding:6px 14px;border-radius:999px;background:var(--soft);text-decoration:none;font-size:14.5px;font-weight:700}
.subnav a.on{background:var(--navy);color:#fff}
.feat{scroll-margin-top:130px;display:grid;grid-template-columns:1fr 300px;gap:40px;align-items:center;padding:48px 0;border-bottom:1px solid var(--line)}
.feat:nth-of-type(even){grid-template-columns:300px 1fr}.feat:nth-of-type(even) .txt{order:2}
.feat h2{font-size:clamp(22px,3vw,30px)}.feat ul{padding-left:20px;margin:14px 0 0}.feat li{margin:6px 0}
.feat .pair{display:flex;gap:16px;justify-content:center}.feat .pair .phone{max-width:240px}.feat .pair .phone .scr{height:480px}
.feat.multi{grid-template-columns:1fr 520px}.feat.multi:nth-of-type(even){grid-template-columns:520px 1fr}
.tag-soon{display:inline-block;margin-left:8px;padding:2px 10px;border-radius:999px;background:#FFF1D6;color:var(--amb);font-size:13px;font-weight:700;vertical-align:middle}
.soon{display:grid;place-items:center;height:300px;border:2px dashed var(--line);border-radius:24px;color:var(--mute);text-align:center;padding:20px}
.note{font-size:13.5px;color:var(--mute);margin-top:12px}
.crumb{font-size:14px;color:#b8c4d6;margin-bottom:8px}.crumb a{color:#b8c4d6}
.next{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:40px 0}
@media (max-width:860px){.hero .in,.feat,.feat:nth-of-type(even),.feat.multi,.feat.multi:nth-of-type(even){grid-template-columns:1fr}.feat:nth-of-type(even) .txt{order:0}.subnav{top:56px}.feat .pair{flex-direction:row}.feat .pair .phone{max-width:48%}.feat .pair .phone .scr{height:400px}}
"""

def esc(s): return html.escape(s, quote=True)

# ---------- 五大類與功能（只列系統裡真的有的功能；截圖檔名對應 shots/） ----------
CATS = [
 {'id': 'staff', 'ic': '👥', 'name': '人事管理', 'one': '排班邀請、建檔、交接、請假、打卡，員工用手機就能完成',
  'feats': [
   {'id': 'emp', 't': '員工建檔與邀請加入', 'd': '傳一條專屬連結給新同事，對方用手機自己填好基本資料、設定打卡 PIN，你按確認就完成建檔。',
    'b': ['專屬連結一次性、7 天內有效', '新同事自己填資料，老闆不用代打', '員工清單一眼看到在職、待確認'], 'shots': ['15-staff-emp', '23-join']},
   {'id': 'avail', 'shot_note': '', 't': '排班邀請與排班表', 'd': '每月固定日期自動請員工回報可上班的日子，回報進度一目了然，再排成每週班表。',
    'b': ['員工在月曆上點選可上班日期', '誰回報了、誰還沒，清楚列出並可提醒', '排好的班表員工手機上就看得到'], 'shots': ['29-avail', '30-staff-avail']},
   {'id': 'plan', 't': '每週班表', 'd': '早班、晚班一週排好，今日出勤和遲到狀況在同一頁。', 'b': ['依週排班，可複製上週', '今日出勤：誰到了、誰遲到', '員工手機同步看到自己的班'], 'shots': ['16-staff-plan']},
   {'id': 'leave', 't': '請假審核', 'd': '員工在手機上送出假單，老闆按「核准」或「駁回」，結果自動通知員工。', 'b': ['事假、病假等假別', '待審核的假單有紅點提醒', '保留最近 90 天紀錄'], 'shots': ['18-staff-leave']},
   {'id': 'clock', 't': '員工打卡', 'd': '員工用自己的 PIN 在店裡手機打卡，系統記下上下班時間與遲到原因。', 'b': ['顯示今天的班別與時間', '遲到可填原因', '打卡紀錄可查詢、匯出 CSV'], 'shots': ['22-clock-home', '17-staff-punch']},
   {'id': 'hand', 't': '交接紀錄', 'd': '每一班把要交代的事寫下來，下一班打開就看到今日摘要和待辦。', 'b': ['依班別記錄，可標「急」', '可指定交給誰', '今日摘要自動整理'], 'shots': ['04-tools-hand']},
   {'id': 'hire', 't': '徵才與面試登記', 'd': '產生徵才海報與 QR Code，應徵者掃碼登記，資料直接進到你的應徵名單。', 'b': ['職缺名稱自己設定', '海報可印出貼在店門口', '應徵者資料集中管理'], 'shots': ['19-staff-hire', '24-apply']},
   {'id': 'docs', 't': '文件下載', 'd': '員工手冊、開店流程等文件集中上傳，設定誰看得到。', 'b': ['依分類整理', '可設定員工看或公開', '員工手機直接下載'], 'shots': ['20-staff-docs']},
  ]},
 {'id': 'marketing', 'ic': '📣', 'name': '行銷管理', 'one': '名片、菜單、公告、圖文選單，改一次就同步',
  'feats': [
   {'id': 'menu', 't': '菜單改價與 A3 排版', 'd': '在手機上改價格，A3 菜單自動重新排版成 PDF，可選一頁或兩頁並指定每頁的分類。', 'b': ['調價助手：整批漲價或降價', '過敏原、素食標示自動印在菜單上', '一頁／兩頁自動排版，字體大小兩頁一致'], 'shots': ['03-menu']},
   {'id': 'emenu', 't': '顧客電子菜單', 'd': '客人掃桌上的 QR 就看到最新菜單和價格，還能依過敏原與素食篩選。', 'b': ['改價後立即更新', '避開蛋、奶、花生等過敏原', '多規格價格合成一筆顯示'], 'shots': ['26-customer-menu']},
   {'id': 'notice', 't': '公告海報', 'd': '選公告類別、填幾個字，就產生公休、活動、價格調整的海報，可印出也可放到顧客頁。', 'b': ['休假、活動、節慶等類別', 'A4 直式等版型', '同時顯示在顧客首頁'], 'shots': ['06-tools-notice']},
   {'id': 'rich', 't': 'LINE 圖文選單', 'd': '選格數、填按鈕功能，產生符合 LINE 官方帳號規格的圖文選單圖片。', 'b': ['2／4／6 格版型', '大尺寸 2500×1686 等規格', '按鈕可連到看菜單、預訂、留言等'], 'shots': ['31-tools-rich']},
   {'id': 'table', 't': '桌號 QR 海報', 'd': '每一桌一張 QR，客人掃了就看到這家店的電子菜單，也可做候位、外帶海報。', 'b': ['一次產生多桌', '可印出 PDF', '連結自動指向你的顧客頁'], 'shots': ['07-tools-table']},
   {'id': 'wifi', 't': 'Wi-Fi 卡', 'd': '填網路名稱與密碼，產生客人掃碼就能連網的卡片。', 'b': ['支援 WPA／WPA2', 'A5、A6 等版面', '可加店名與 Logo'], 'shots': ['08-tools-wifi']},
   {'id': 'card', 't': '名片', 'd': '依店家資料自動產生 90×54mm 名片，含 LINE 官方帳號 QR，可直接送印。', 'b': ['橫式、直式版型', '自動帶入店名、電話、地址', '配色跟著店家品牌'], 'shots': ['09-tools-card']},
   {'id': 'social', 't': '社群貼文生成器', 'soon': True, 'd': '用菜單和公告資料一鍵產生 Facebook、Instagram 貼文圖片與文案。', 'b': ['開發中，完成後會在這裡放上實際畫面'], 'shots': []},
  ]},
 {'id': 'finance', 'ic': '💰', 'name': '收支管理', 'one': '固定叫貨、叫貨提醒、採購記帳、月結報表',
  'feats': [
   {'id': 'book', 't': '進貨記帳與發票', 'd': '點固定廠商、按常用金額，幾秒記好一筆進貨；統一發票號碼、品項、採購人員一起記下。', 'b': ['統一發票、收據、無憑證分開記', '記下採購人員與品項', '現金、轉帳、月結等付款方式'], 'shots': ['11-ledger', '12-ledger-sheet']},
   {'id': 'vendor', 't': '固定廠商與叫貨提醒', 'd': '設定每家廠商的叫貨日、時間與負責人，當天沒叫貨會寄提醒，叫好按「已叫貨」。', 'b': ['叫貨日與時間、負責人', '當天提醒，沒叫完隔天再提醒', '常用金額一鍵帶入'], 'shots': ['14-ledger-vendors']},
   {'id': 'report', 'shot_note': '', 't': '報表與月結', 'd': '收入、支出、淨額與月結待付一頁看完，支出分類和廠商排行幫你找出花最多的地方。', 'b': ['依月份切換', '支出分類比例', '廠商支出排行'], 'shots': ['13-ledger-report']},
  ]},
 {'id': 'customer', 'ic': '🙋', 'name': '顧客服務', 'one': '顧客首頁、大單預訂、敲敲老闆、店休日曆',
  'feats': [
   {'id': 'home', 't': '顧客首頁', 'd': '一個連結放公告、營業時間、看菜單、線上點餐、大單預訂與留言，貼在 LINE 和 Google 商家都好用。', 'b': ['公告與暫停營業自動顯示', '大單預訂：客人填好時間與內容', '敲敲老闆：客人直接留言給店家'], 'shots': ['25-customer']},
   {'id': 'cal', 't': '店休日曆', 'd': '在月曆上設定公休與特別營業日，顧客頁和公告會一起更新。', 'b': ['公休、特別營業日', '顧客頁自動顯示', '員工排班也看得到'], 'shots': ['05-tools-cal']},
  ]},
 {'id': 'setup', 'ic': '🏪', 'name': '開店與帳號', 'one': '設定精靈、Logo 配色、通知、多店與帳號',
  'feats': [
   {'id': 'home', 't': '主畫面', 'd': '登入後先看到大按鈕主畫面，待處理的事會有小徽章提醒。', 'b': ['依菜單、行銷、店務、財務、人員分類', '今日支出、待審假單等徽章', '店主與夥伴看到各自能用的功能'], 'shots': ['02-home']},
   {'id': 'wizard', 't': '設定精靈', 'd': '第一次使用照步驟填好店名、地址、電話、LINE 與配色，所有文宣自動套用。', 'b': ['地址、電話分欄填寫', '配色範本或自訂', '填完立即套用到菜單與海報'], 'shots': ['28-setup']},
   {'id': 'logo', 't': 'Logo 與店家資料', 'd': '上傳 Logo、選配色，菜單、名片、海報全部用同一套品牌。', 'b': ['支援 PNG、JPG、WebP', '20 組配色範本', '品牌色自動套用'], 'shots': ['10-tools-logo']},
   {'id': 'account', 't': '帳號、夥伴與通知', 'd': '管理夥伴帳號、顧客網址與訂閱，並選擇要收到哪些 Email 通知。', 'b': ['顧客網址一鍵複製', '夥伴與授權管理', '通知可逐項開關'], 'shots': ['27-account', '33-notify']},
  ]},
]

def phone(shot, cap='系統實際畫面，可上下滑動', prefix=''):
    return ('<figure class="phone"><div class="scr" tabindex="0" aria-label="%s"><img loading="lazy" decoding="async" src="%sshots/%s.webp" alt="%s" width="560"></div><figcaption>%s</figcaption></figure>'
            % (esc(cap), prefix, shot, esc(cap), esc(cap)))

def header(prefix, active=''):
    links = ''.join('<a href="%sfeatures/%s.html"%s>%s</a>' % (prefix, c['id'], ' aria-current="page"' if c['id'] == active else '', c['name']) for c in CATS)
    return ('<header class="nav"><div class="wrap in"><a class="logo" href="%sindex.html" aria-label="星樂創意 StarFunDea 首頁"><img src="%sbrand/official/logo-horizontal-dark.svg" alt="StarFunDea 星樂創意" width="238" height="30"></a>'
            '<nav id="nav" aria-label="主選單">%s<a href="%sindex.html#pricing">方案費用</a><a href="%sguide/">使用指南</a></nav>'
            '<div style="display:flex;gap:10px;align-items:center"><a class="btn pri cta" href="%s">免費試用 14 天</a>'
            '<button class="menu-btn" id="menuBtn" aria-label="開啟選單" aria-expanded="false" aria-controls="nav">☰</button></div></div></header>') % (prefix, prefix, links, prefix, prefix, APP)

def footer(prefix):
    links = '　'.join('<a href="%sfeatures/%s.html">%s</a>' % (prefix, c['id'], c['name']) for c in CATS)
    return ('<footer><div class="wrap in"><div><img src="%sbrand/official/logo-horizontal-dark.svg" alt="StarFunDea 星樂創意" style="height:24px;display:block;margin-bottom:12px">把點子，走成亮點。<br>讓餐廳的手機，成為菜單與文宣的控制台。預計 2027 年 2 月正式開賣。</div>'
            '<div>%s<br><a href="%sindex.html#pricing">方案費用</a>　<a href="%sindex.html#faq">常見問題</a>　<a href="%sguide/">使用指南</a><br><span style="opacity:.8">服務條款與隱私權政策將於正式開賣前公布。</span></div></div></footer>') % (prefix, links, prefix, prefix, prefix)

SCRIPT = """<script>
(function () {
  var mb = document.getElementById('menuBtn'), nav = document.getElementById('nav');
  if (mb && nav) mb.addEventListener('click', function () { var o = nav.classList.toggle('open'); mb.setAttribute('aria-expanded', o ? 'true' : 'false'); });
  var els = document.querySelectorAll('.cat,.feat,.card,.step,.plan,.fact');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (en) { en.forEach(function (x) { if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); } }); }, { threshold: .1 });
    [].forEach.call(els, function (e) { e.classList.add('reveal'); io.observe(e); });
  }
  if (nav) nav.addEventListener('click', function (e) { if (e.target.tagName === 'A') { nav.classList.remove('open'); mb.setAttribute('aria-expanded', 'false'); } });
  var tabs = document.querySelector('.tabs');
  if (tabs) tabs.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    [].forEach.call(tabs.children, function (x) { x.setAttribute('aria-selected', x === b ? 'true' : 'false'); });
    [].forEach.call(document.querySelectorAll('.tabp'), function (p) { p.hidden = p.dataset.p !== b.dataset.s; });
  });
  var $ = function (id) { return document.getElementById(id); };
  function cycle(y) {
    var t = { pb: y ? '3,990' : '399', ub: y ? '元／年（省 798）' : '元／月', pp: y ? '5,990' : '599', up: y ? '元／年（省 1,198）' : '元／月',
      nb: y ? '年繳只收 10 個月，平均每月約 333 元' : '專注紙本菜單與桌號標示的單店', np: y ? '年繳只收 10 個月，平均每月約 499 元' : '含門市文宣、交接與顧客電子菜單' };
    if ($('bm')) $('bm').setAttribute('aria-pressed', y ? 'false' : 'true'); if ($('by')) $('by').setAttribute('aria-pressed', y ? 'true' : 'false');
    Object.keys(t).forEach(function (k) { if ($(k)) $(k).textContent = t[k]; });
  }
  if ($('bm')) $('bm').onclick = function () { cycle(false); }; if ($('by')) $('by').onclick = function () { cycle(true); };
  var sub = document.querySelectorAll('.subnav a');
  if (sub.length && 'IntersectionObserver' in window) {
    var so = new IntersectionObserver(function (en) { en.forEach(function (x) { if (x.isIntersecting) [].forEach.call(sub, function (a) { a.classList.toggle('on', a.getAttribute('href') === '#' + x.target.id); }); }); }, { rootMargin: '-40% 0px -55% 0px' });
    [].forEach.call(document.querySelectorAll('.feat[id]'), function (s) { so.observe(s); });
  }
})();
</script>"""

def page(title, desc, prefix, body, active=''):
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>%s</title><meta name="description" content="%s"><meta name="theme-color" content="#0E1623">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap">'
            '<link rel="icon" href="%sbrand/starfundea-appicon.svg"><link rel="stylesheet" href="%sassets/site.css"></head><body>%s<main id="top">%s</main>%s%s</body></html>'
            % (esc(title), esc(desc), prefix, prefix, header(prefix, active), body, footer(prefix), SCRIPT))

def feat_html(f, prefix):
    shots = f['shots']
    if f.get('soon'): vis = '<div class="soon">開發中<br>完成後放上實際畫面</div>'
    elif len(shots) == 1: vis = phone(shots[0], prefix=prefix)
    else: vis = '<div class="pair">' + ''.join(phone(s, prefix=prefix) for s in shots) + '</div>'
    cls = 'feat multi' if len(shots) > 1 else 'feat'
    soon = '<span class="tag-soon">開發中</span>' if f.get('soon') else ''
    return ('<section class="%s" id="%s"><div class="txt"><h2>%s%s</h2><p class="lead">%s</p><ul>%s</ul></div>%s</section>'
            % (cls, f['id'], esc(f['t']), soon, esc(f['d']), ''.join('<li>%s</li>' % esc(x) for x in f['b']), vis))

os.makedirs(os.path.join(ROOT, 'features'), exist_ok=True); os.makedirs(os.path.join(ROOT, 'assets'), exist_ok=True)
open(os.path.join(ROOT, 'assets', 'site.css'), 'w', encoding='utf-8').write(base_css + NEW_CSS)

for i, c in enumerate(CATS):
    prev, nxt = CATS[i - 1], CATS[(i + 1) % len(CATS)]
    body = ('<section class="sec dark"><div class="wrap"><p class="crumb"><a href="../index.html">首頁</a> ／ %s</p><p class="eyebrow">%s</p><h1 style="font-size:clamp(30px,5vw,44px);font-weight:900">%s</h1><p class="lead">%s。下面每一張都是系統的實際畫面，手指可以在畫面裡上下滑動。</p></div></section>'
            '<div class="subnav"><div class="wrap">%s</div></div><div class="wrap">%s'
            '<div class="next"><a class="btn ghost" style="color:var(--ink);border-color:var(--line)" href="%s.html">← %s</a><a class="btn pri" href="%s">免費試用 14 天</a><a class="btn ghost" style="color:var(--ink);border-color:var(--line)" href="%s.html">%s →</a></div></div>') % (
        esc(c['name']), c['id'].upper(), esc(c['name']), esc(c['one']),
        ''.join('<a href="#%s">%s</a>' % (f['id'], esc(f['t'])) for f in c['feats']),
        ''.join(feat_html(f, '../') for f in c['feats']), prev['id'], esc(prev['name']), APP, nxt['id'], esc(nxt['name']))
    open(os.path.join(ROOT, 'features', c['id'] + '.html'), 'w', encoding='utf-8').write(
        page('%s｜星樂創意 StarFunDea' % c['name'], c['one'], '../', body, c['id']))

# ---------- 首頁：保留舊版的痛點、適合對象、開始方式、價格、FAQ、結尾段落 ----------
secs = {}
for m in re.finditer(r'<section[^>]*>.*?</section>', old, re.S):
    h = re.search(r'<h2[^>]*>(.*?)</h2>', m.group(0), re.S)
    if h: secs[re.sub('<[^>]+>', '', h.group(1)).strip()] = m.group(0)
def pick(prefix_txt):
    for k, v in secs.items():
        if k.startswith(prefix_txt): return v.replace('href="#demo"', 'href="#cats"').replace('href="#features"', 'href="#cats"')
    raise SystemExit('找不到段落：' + prefix_txt)
cards = ''.join('<a class="cat" href="features/%s.html"><span class="ic" aria-hidden="true">%s</span><h3>%s</h3><p>%s</p><span class="go">看實際畫面 →</span></a>'
                % (c['id'], c['ic'], esc(c['name']), esc(c['one'])) for c in CATS)
hero = ('<section class="hero"><div class="wrap in"><div><p class="eyebrow">From idea to spark.</p><h1>老闆改一次價格，<br><b>菜單、海報、QR 一起更新</b></h1>'
        '<p class="sub">人事、行銷、收支、顧客服務，一支手機管好一家店。下面每個功能都放上系統的實際畫面。</p>'
        '<div class="acts"><a class="btn pri" href="%s">免費試用 14 天</a><a class="btn ghost" href="#cats">看五大功能</a></div></div>%s</div></section>') % (APP, phone('02-home', '系統主畫面（實際畫面，可上下滑動）'))
catsec = '<section class="sec" id="cats"><div class="wrap center"><p class="eyebrow">FEATURES</p><h2>依店裡的工作分成五大類</h2><p class="lead">點進每一類，看每個功能的實際操作畫面。</p></div><div class="wrap"><div class="cats">%s</div></div></section>' % cards
body = hero + pick('改兩個價格') + catsec + pick('1～3 家門市') + pick('一家新店') + pick('新開店') + pick('從第一線') + pick('開店的人最常問') + pick('下次換季')
open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(
    page('星樂創意 StarFunDea｜老闆改一次價格，A3 菜單、海報、QR 一起更新', '給 1～3 家門市的早餐店、小吃店、飲料店與咖啡廳：人事、行銷、收支、顧客服務一支手機管好。14 天免費試用。', '', body))
for f in ['index.html'] + ['features/%s.html' % c['id'] for c in CATS] + ['assets/site.css']:
    print(f, os.path.getsize(os.path.join(ROOT, f)) // 1024, 'KB')
