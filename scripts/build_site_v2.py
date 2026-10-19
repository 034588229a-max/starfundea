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
.painlist{list-style:none;padding:0;margin:20px 0 0;display:grid;gap:10px;max-width:760px}.painlist li{background:rgba(255,255,255,.06);border-left:4px solid var(--orange);border-radius:10px;padding:10px 14px;font-size:16.5px}
.fit{margin:18px 0 0;font-weight:700;color:var(--orange)}
.pns{margin:16px 0 0;display:grid;gap:10px}.pns>div{border-radius:14px;padding:12px 16px}.pns dt{font-weight:900;font-size:14px;letter-spacing:.08em;margin-bottom:2px}.pns dd{margin:0}
.pns .was{background:#FDF2F2}.pns .was dt{color:#B4362B}.pns .now{background:#EEF4FB}.pns .now dt{color:#1B4F8A}.pns .gain{background:#EEF8F1}.pns .gain dt{color:var(--ok)}
.outimg{margin:16px 0 0}.outimg img{width:100%;border-radius:12px;border:1px solid var(--line);box-shadow:0 8px 24px rgba(14,22,35,.12)}.outimg figcaption{font-size:13px;color:var(--mute);margin-top:6px}
.next{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:40px 0}
@media (max-width:860px){.hero .in,.feat,.feat:nth-of-type(even),.feat.multi,.feat.multi:nth-of-type(even){grid-template-columns:1fr}.feat:nth-of-type(even) .txt{order:0}.subnav{top:56px}.feat .pair{flex-direction:row}.feat .pair .phone{max-width:48%}.feat .pair .phone .scr{height:400px}}
"""

def esc(s): return html.escape(s, quote=True)

# ---------- 五大類與功能（只列系統裡真的有的功能；截圖檔名對應 shots/） ----------
CATS = [
 {'id': 'staff', 'ic': '👥', 'name': '人事管理', 'one': '排班、請假、交接不再靠 LINE 和記憶',
  'pains': ['排班表改了三次，還是有人說沒看到？', '員工用 LINE 請假，訊息一多就漏掉，排班時才發現少一個人？', '交接靠嘴巴講，下一班根本不知道雞肉快沒了？', '新人來上班，資料、證件還要老闆一個一個打進電腦？'],
  'fit': '店裡有 2 位以上員工、每週要排班的店。',
  'feats': [
   {'id': 'emp', 't': '員工建檔與邀請加入', 'pain': '新人到職，老闆要抄姓名、電話、緊急聯絡人，再一筆一筆輸入。', 'now': '傳一條專屬連結給新同事，他用自己的手機填好資料、設定打卡 PIN，你按確認就建檔完成。', 'gain': '老闆不用代打資料；連結一次性、7 天內有效，不怕外流。', 'shots': ['15-staff-emp', '23-join']},
   {'id': 'avail', 't': '排班邀請', 'pain': '每個月要在群組裡問「下個月哪幾天可以上班」，再自己整理回覆。', 'now': '系統在你設定的日期自動請員工回報，員工在月曆上點選可上班的日子，誰回了、誰還沒回清楚列出。', 'gain': '不用追訊息，排班前就知道每個人能上哪幾天。', 'shots': ['29-avail', '30-staff-avail']},
   {'id': 'plan', 'shot_note': '', 't': '每週班表', 'pain': '班表貼在牆上或傳照片，改了一格就要重傳，員工常看到舊的。', 'now': '在手機上排一週的早班、晚班，員工手機上看到的永遠是最新的班表。', 'gain': '改班不用再重傳照片，也不會有人照舊班表來上班。', 'shots': ['16-staff-plan']},
   {'id': 'leave', 't': '請假審核', 'pain': '請假散在 LINE 和口頭，排班時才發現當天有人請假。', 'now': '員工在手機送出假單，你按「核准」或「駁回」，員工自動收到結果，待審的假單有紅點提醒。', 'gain': '不用翻訊息找假單，誰請過假都有紀錄。', 'shots': ['18-staff-leave']},
   {'id': 'clock', 't': '員工打卡', 'pain': '用紙本簽到或打卡鐘，月底還要一張一張算工時。', 'now': '員工用自己的 PIN 在店裡手機打卡，遲到可以填原因；打卡紀錄可以查詢、匯出 CSV。', 'gain': '不用買打卡鐘，月底直接匯出紀錄算薪水。', 'shots': ['22-clock-home', '17-staff-punch']},
   {'id': 'hand', 't': '交接紀錄', 'pain': '交接靠嘴巴講或寫在便條紙，下一班沒看到，食材沒叫、設備壞了沒人知道。', 'now': '每一班把要交代的事寫下來，可以標「急」、指定交給誰，下一班打開就看到今日摘要。', 'gain': '重要的事不會在換班時掉了。', 'shots': ['04-tools-hand']},
   {'id': 'hire', 't': '徵才與面試登記', 'pain': '門口貼「誠徵」，應徵電話打來時正在忙，聯絡方式也記不住。', 'now': '產生徵才海報與 QR Code，應徵者掃碼自己登記，資料直接進到你的應徵名單。', 'gain': '忙的時候不用接應徵電話，有空再一次看名單。', 'shots': ['19-staff-hire', '24-apply']},
   {'id': 'docs', 't': '文件下載', 'pain': '員工手冊、開店流程每個新人都要再傳一次，版本也不一致。', 'now': '把文件上傳一次、設定誰看得到，員工自己用手機下載。', 'gain': '新人訓練用同一份最新的文件。', 'shots': ['20-staff-docs']},
  ]},
 {'id': 'marketing', 'ic': '📣', 'name': '行銷管理', 'one': '改一次價格，菜單、海報、QR 一起更新',
  'pains': ['改兩個價格，就要找人重排一張 A3 菜單？', '牆上的菜單、桌上的 QR、外送平台價格不一樣，客人來問才發現？', '公休、活動要做海報，每次都要開電腦、找範本？', '想做名片、LINE 圖文選單，卻不知道尺寸怎麼抓？'],
  'fit': '常常調價、會印紙本菜單或在 LINE 經營熟客的店。',
  'feats': [
   {'id': 'menu', 't': '菜單改價與 A3 排版', 'pain': '每次調價都要找人改檔、重排版、重印，小改也要等好幾天。', 'now': '在手機上改價格，A3 菜單自動重新排版成 PDF；品項多時可分成兩頁，自己勾選每頁放哪些分類。', 'gain': '改價當天就能印出新菜單；調價助手可以整批漲價或降價。品項多寡都會自動排滿整頁。', 'shots': ['03-menu'], 'out': 'o-a3', 'out_cap': '做出來的成品：A3 菜單（實際輸出，51 個品項自動排滿一頁）'},
   {'id': 'emenu', 't': '顧客電子菜單', 'pain': '客人問「這個有沒有蛋」「有沒有素的」，忙的時候很難一個一個回答。', 'now': '客人掃桌上的 QR 看到最新菜單，還能自己篩選過敏原和素食；你一改價，這裡馬上更新。', 'gain': '價格永遠是最新的，客人自己就能找到能吃的品項。', 'shots': ['26-customer-menu']},
   {'id': 'notice', 't': '公告海報', 'pain': '要公休、辦活動，就得開電腦找範本做海報，再另外發到 LINE。', 'now': '選公告類別、填幾個字，就產生可以印的海報；勾一下也會同時顯示在顧客首頁。', 'gain': '手機上幾分鐘做好公告，門口和線上同步。', 'shots': ['06-tools-notice'], 'out': 'o-notice', 'out_cap': '做出來的成品：公告海報（實際輸出）'},
   {'id': 'rich', 't': 'LINE 圖文選單', 'pain': 'LINE 官方帳號的圖文選單尺寸很多種，自己做常常被裁切或模糊。', 'now': '選格數、填每個按鈕要連到哪裡，系統產生符合 LINE 規格的圖片。', 'gain': '不用學修圖，客人在 LINE 一點就能看菜單、預訂、留言。', 'shots': ['31-tools-rich'], 'out': 'o-rich', 'out_cap': '做出來的成品：LINE 圖文選單（實際輸出）'},
   {'id': 'table', 't': '桌號 QR 海報', 'pain': '桌上的 QR 連到舊菜單或舊網址，換了也不知道要重印哪幾張。', 'now': '每一桌產生一張 QR 海報，連結固定指向你的顧客頁，菜單更新不用重印。', 'gain': '印一次就好，菜單改了 QR 不用換。', 'shots': ['07-tools-table']},
   {'id': 'wifi', 't': 'Wi-Fi 卡', 'pain': '客人一直問 Wi-Fi 密碼，還要一個字一個字念給他聽。', 'now': '填網路名稱和密碼，產生客人掃碼就能連上的卡片。', 'gain': '不用再念密碼。', 'shots': ['08-tools-wifi']},
   {'id': 'card', 't': '名片', 'pain': '印名片要自己排版、確認尺寸，改了電話又要重做。', 'now': '依店家資料自動產生 90×54mm 名片，含 LINE 官方帳號 QR，可以直接送印。', 'gain': '店家資料改了，名片跟著更新。', 'shots': ['09-tools-card']},
   {'id': 'social', 't': '社群貼文生成器', 'soon': True, 'pain': '每次發 Facebook、Instagram 都要想文案、做圖。', 'now': '開發中：用菜單和公告資料一鍵產生貼文圖片與文案。', 'gain': '完成後會在這裡放上實際畫面。', 'shots': []},
  ]},
 {'id': 'finance', 'ic': '💰', 'name': '收支管理', 'one': '叫貨不再忘記，月底不用翻發票',
  'pains': ['忙到忘記叫貨，隔天開店才發現食材不夠？', '發票、收據塞在抽屜，月底報帳要整理一整晚？', '每個月到底花最多錢在哪裡，心裡沒有數字？'],
  'fit': '有固定進貨廠商、想知道每月收支的店。',
  'feats': [
   {'id': 'book', 't': '進貨記帳與發票', 'pain': '進貨單和發票到處放，記帳要等月底一次補，常常漏記。', 'now': '點廠商、按常用金額，幾秒記好一筆；發票號碼、品項、採購人員一起記下，收據可以拍照存。', 'gain': '收貨當下就記好，月底不用再翻抽屜。', 'shots': ['11-ledger', '12-ledger-sheet']},
   {'id': 'vendor', 't': '固定廠商與叫貨提醒', 'pain': '叫貨全靠老闆記，忙起來就忘，隔天才發現少了食材。', 'now': '設定每家廠商的叫貨日、時間和負責人，當天沒按「已叫貨」系統會寄提醒，沒叫完隔天再提醒。', 'gain': '叫貨交給員工也不怕忘，誰負責一清二楚。', 'shots': ['14-ledger-vendors']},
   {'id': 'report', 't': '報表與月結', 'pain': '只知道錢花出去了，不知道花在哪裡，月結廠商還欠多少也不清楚。', 'now': '收入、支出、淨額和月結待付一頁看完，還有支出分類和廠商支出排行。', 'gain': '每個月花最多的地方一眼就看到。', 'shots': ['13-ledger-report']},
  ]},
 {'id': 'customer', 'ic': '🙋', 'name': '顧客服務', 'one': '客人想知道的，一個連結全部看得到',
  'pains': ['客人一直打電話問「今天有開嗎」「幾點關門」？', '大單、團訂靠電話記，常常記錯時間或數量？', '客人有意見卻找不到地方說，只好去 Google 留負評？'],
  'fit': '有熟客、常接電話詢問或團訂的店。',
  'feats': [
   {'id': 'home', 't': '顧客首頁', 'pain': '營業時間、公休、菜單、預訂資訊散在 LINE、Facebook、Google，客人找不到就打電話。', 'now': '一個連結放公告、營業時間、看菜單、線上點餐、大單預訂和「敲敲老闆」留言，貼在 LINE 和 Google 商家都好用。', 'gain': '少接很多重複的電話，大單預訂和客人意見都有紀錄。', 'shots': ['25-customer']},
   {'id': 'cal', 't': '店休日曆', 'pain': '公休要分別通知客人、員工，還是有人白跑一趟。', 'now': '在月曆上設定公休和特別營業日，顧客頁和公告會一起更新。', 'gain': '設定一次，客人和員工都看得到。', 'shots': ['05-tools-cal']},
  ]},
 {'id': 'setup', 'ic': '🏪', 'name': '開店與帳號', 'one': '第一次用 3 分鐘設定，之後所有文宣自動套用',
  'pains': ['店名、地址、電話、LINE 要在每張文宣上重打一次？', '換了 Logo 或配色，菜單、名片、海報要全部重做？', '不同員工能看到哪些功能，很難控制？'],
  'fit': '剛開店，或想讓店裡所有文宣看起來是同一個品牌的店。',
  'feats': [
   {'id': 'home', 't': '主畫面', 'pain': '功能一多就找不到在哪裡。', 'now': '登入後先看到大按鈕主畫面，依菜單、行銷、店務、財務、人員分類，待處理的事有小徽章提醒。', 'gain': '打開就知道今天要處理什麼。', 'shots': ['02-home']},
   {'id': 'wizard', 't': '設定精靈', 'pain': '每做一份文宣都要重新輸入店家資料。', 'now': '第一次使用照步驟填好店名、地址、電話、LINE 和配色，之後所有菜單、海報、名片自動帶入。', 'gain': '資料只填一次。', 'shots': ['28-setup']},
   {'id': 'logo', 't': 'Logo 與店家資料', 'pain': '每份文宣用的 Logo 和顏色都不一樣，看起來不像同一家店。', 'now': '上傳 Logo、選配色範本，菜單、名片、海報全部用同一套品牌。', 'gain': '換 Logo 或配色，所有文宣一起換。', 'shots': ['10-tools-logo']},
   {'id': 'account', 't': '帳號、夥伴與通知', 'pain': '員工共用老闆帳號，誰改了什麼不知道，通知也全部擠在一起。', 'now': '夥伴各自有帳號，店主決定誰能用哪些功能；要收哪些 Email 通知可以逐項開關。', 'gain': '權限分清楚，只收你需要的通知。', 'shots': ['27-account', '33-notify']},
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
    outimg = ('<figure class="outimg"><img loading="lazy" decoding="async" src="%sshots/%s.webp" alt="%s"><figcaption>%s</figcaption></figure>' % (prefix, f['out'], esc(f['out_cap']), esc(f['out_cap']))) if f.get('out') else ''
    return ('<section class="%s" id="%s"><div class="txt"><h2>%s%s</h2><dl class="pns">'
            '<div class="was"><dt>以前</dt><dd>%s</dd></div><div class="now"><dt>現在</dt><dd>%s</dd></div><div class="gain"><dt>你省下的</dt><dd>%s</dd></div></dl>%s</div>%s</section>'
            % (cls, f['id'], esc(f['t']), soon, esc(f['pain']), esc(f['now']), esc(f['gain']), outimg, vis))

os.makedirs(os.path.join(ROOT, 'features'), exist_ok=True); os.makedirs(os.path.join(ROOT, 'assets'), exist_ok=True)
open(os.path.join(ROOT, 'assets', 'site.css'), 'w', encoding='utf-8').write(base_css + NEW_CSS)

for i, c in enumerate(CATS):
    prev, nxt = CATS[i - 1], CATS[(i + 1) % len(CATS)]
    body = ('<section class="sec dark"><div class="wrap"><p class="crumb"><a href="../index.html">首頁</a> ／ %s</p><p class="eyebrow">%s</p><h1 style="font-size:clamp(30px,5vw,44px);font-weight:900">%s</h1><p class="lead">%s</p><ul class="painlist">%s</ul><p class="fit">適合你，如果你是：%s</p><p class="note" style="color:#b8c4d6">下面每個功能都先說以前的麻煩，再看系統怎麼解決；手機裡是系統的實際畫面，可以上下滑動。</p></div></section>'
            '<div class="subnav"><div class="wrap">%s</div></div><div class="wrap">%s'
            '<div class="next"><a class="btn ghost" style="color:var(--ink);border-color:var(--line)" href="%s.html">← %s</a><a class="btn pri" href="%s">免費試用 14 天</a><a class="btn ghost" style="color:var(--ink);border-color:var(--line)" href="%s.html">%s →</a></div></div>') % (
        esc(c['name']), c['id'].upper(), esc(c['name']), esc(c['one']), ''.join('<li>%s</li>' % esc(x) for x in c['pains']), esc(c['fit']),
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
