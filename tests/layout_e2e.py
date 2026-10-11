"""A3 菜單版面測試：正面品項上限、跨到背面、列距自動調整（減少留白）、不漏品項、不被裁掉。
真的 Code.gs＋Page.html 在 iframe 裡跑（跟 integration_e2e.py 同一套模擬）。
執行：python tests/layout_e2e.py
"""
import re, asyncio, base64, json, os, sys, tempfile
from PIL import Image
import zxingcpp
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfutil import pdf_to_pngs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T, SRC = os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'src')
VEND = {'html2canvas': os.path.join(T, 'vendor/html2canvas-1.4.1/dist/html2canvas.min.js'),
        'jspdf': os.path.join(T, 'vendor/jspdf-2.5.1/dist/jspdf.umd.min.js')}
TMP = tempfile.gettempdir()
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:600]))

def files_json():
    f = {n: open(os.path.join(SRC, n + '.html'), encoding='utf-8').read() for n in ['Page', 'Customer', 'Tools', 'Login', 'Admin', 'Account']}
    return json.dumps(f).replace('</', '<\\/')

SEED = """
(function () {
  __store.props.ssId = 'test';
  var p = __ss.insertSheet('價格表');
  p.data = [['弘林'], [''], [''], [''], ['代碼']];
  ITEMS.forEach(function (it) { p.data.push([it[0], it[1], it[2], it[3], it[4], it[4], false, !!it[5], '']); });
})();
"""
HOST = """<!doctype html><html><head><meta charset="utf-8">
<script>window.__REAL_CODE = true;</script>
<script src="/mock.js"></script><script src="/Code.gs.js"></script><script src="/Tools.gs.js"></script><script src="/Tenant.gs.js"></script><script src="/Mail.gs.js"></script><script src="/Auth.gs.js"></script><script src="/Billing.gs.js"></script><script src="/Provision.gs.js"></script><script src="/Shop.gs.js"></script><script src="/BrandServer.gs.js"></script><script src="/saas_mock.js"></script>
<script>window.__FILES = %s;</script><script src="/seed.js"></script>
<script>
function openPage(params) {
  var html = doGet({ parameter: params }).getContent();
  html = html.replace('<head>', '<head><script>window.google = parent.google;<\\/script>');
  return new Promise(function (res) { var f = document.getElementById('f'); f.onload = function () { setTimeout(function () { res(true); }, 300); }; f.srcdoc = html; });
}
</script></head><body style="margin:0"><iframe id="f" style="width:900px;height:1000px;border:0"></iframe></body></html>"""

# 在頁面裡執行：額外加 n 列品項到某個分類（只改畫面上的資料，不動試算表），然後重排並回報
MEASURE = """async ([sid, n, mode]) => {
  const rows = [];
  window.__baseRows = window.__baseRows || server.rows.map(r => ({ ...r }));
  window.__baseRows.forEach(r => rows.push({ ...r }));
  const s = SECTIONS.find(x => x.id === sid);
  for (let i = 0; i < n; i++) s.cols.forEach((_, c) => rows.push({ k: sid + '|新品項' + String(i + 1).padStart(3, '0') + '|' + c, cat: s.t, name: '新品項' + (i + 1), spec: s.cols[c], p: '55', l: '55', hidden: false, star: i % 7 === 0, side: '' }));
  layoutSig = ''; rebuildFromRows(rows);
  for (const k in DEFAULTS) prices[k] = prices[k] || '55';
  const html = sheetHTML(mode || 'menu', 'V9');
  const host = document.getElementById('render'); host.innerHTML = html;
  const pages = [...host.querySelectorAll('.sheet')];
  const info = pages.map(pg => {
    const grid = pg.querySelector('.grid'), gb = grid.getBoundingClientRect();
    return [...pg.querySelectorAll('.col')].map(col => {
      const kids = [...col.children], last = kids[kids.length - 1];
      const bottom = last ? last.getBoundingClientRect().bottom - gb.top : 0;
      return { bottom, h: gb.height, clip: col.scrollHeight - col.clientHeight, n: kids.length };
    });
  });
  const rowsDom = host.querySelectorAll('.r:not(.h)').length;
  const p = lastPlan;
  const out = { pageCount: p.pageCount, overflow: p.overflow, left: p.left, rowsTotal: p.rowsTotal, usage: p.usage, rowsDom, info,
    conts: host.querySelectorAll('.cn').length, d: p.cols.map(c => c.d), how: p.how, rb: p.rb, base: p.M.base, titles: pages.map(pg => [...pg.querySelectorAll('.s h2 > span')].map(x => x.firstChild.textContent)), text: fitText(), foot: pages.map(pg => pg.querySelector('.foot').innerText) };
  return out;
}"""

def fills(info):
    return [round(c['bottom'] / c['h'], 2) for pg in info for c in pg if c['n']]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 900, 'height': 1000})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        async def route(r):
            u = r.request.url
            if u == 'http://t/': return await r.fulfill(body=HOST % files_json(), content_type='text/html; charset=utf-8')
            if u.endswith('/mock.js'): return await r.fulfill(path=os.path.join(T, 'tools_mock.js'), content_type='text/javascript')
            if u.endswith('/Code.gs.js'): return await r.fulfill(path=os.path.join(SRC, 'Code.gs'), content_type='text/javascript')
            if u.endswith('/Tools.gs.js'): return await r.fulfill(path=os.path.join(SRC, 'ToolsServer.gs'), content_type='text/javascript')
            m = re.search(r'/(Tenant|Mail|Auth|Billing|Provision|Shop|BrandServer)\.gs\.js$', u)
            if m: return await r.fulfill(path=os.path.join(SRC, m.group(1) + '.gs'), content_type='text/javascript')
            if u.endswith('/saas_mock.js'): return await r.fulfill(path=os.path.join(T, 'saas_mock.js'), content_type='text/javascript')
            if u.endswith('/seed.js'): return await r.fulfill(body=SEED, content_type='text/javascript')
            for k, v in VEND.items():
                if k in u and 'cdnjs' in u: return await r.fulfill(path=v, content_type='text/javascript')
            return await r.abort()
        await page.route('**/*', route)
        await page.goto('http://t/')
        H = page.main_frame
        await H.evaluate("p => openPage(p)", {'staff': 'hl7q2x9m'})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b") && loaded')
        await fr.evaluate('document.fonts.ready')

        # ---------- 1. 原本的弘林菜單：一頁放得下，不被裁掉，不漏品項 ----------
        r = await fr.evaluate(MEASURE, ['toast', 0, 'menu'])
        expected = await fr.evaluate("FLOW.reduce((a, id) => a + BYID[id].rows.filter(x => !HIDDEN.has(id + '|' + clean(x[0]))).length, 0)")
        f = fills(r['info'])
        print('  [原菜單] 列數', r['rowsTotal'], '用量', round(r['usage'] * 100), '%  各欄填滿率', f, '列距增量', [round(x, 1) for x in r['d']])
        check('原菜單：一頁放得下', r['pageCount'] == 1 and not r['overflow'], r)
        check('原菜單：沒有任何一欄被裁掉', all(c['clip'] <= 0 and c['bottom'] <= c['h'] + 0.5 for pg in r['info'] for c in pg), r['info'])
        check('原菜單：每個品項都有印出來（%d 列）' % expected, r['rowsDom'] == expected, (r['rowsDom'], expected))
        check('原菜單：四欄用量平均（每欄填滿率 ≥ 85%）', min(f) >= 0.85, f)
        check('原菜單：列距有自動拉高去吃留白', max(r['d']) > 0, r['d'])

        # ---------- 2. 正面上限：不斷加品項（每個品項 1 列），看哪個階段換成哪種排法 ----------
        async def max_items(cond):
            lo, hi = 0, 260
            while lo < hi:
                mid = (lo + hi + 1) // 2
                q = await fr.evaluate(MEASURE, ['toast', mid, 'menu'])
                if cond(q): lo = mid
                else: hi = mid - 1
            return lo, await fr.evaluate(MEASURE, ['toast', lo, 'menu'])
        n_norm, qn = await max_items(lambda q: q['how'] == 'one')
        n_tight, qt = await max_items(lambda q: q['pageCount'] == 1)
        print('  [正面上限] 原本排法最多再加 %d 列（共 %d 列）；縮小列高後最多再加 %d 列（共 %d 列，列高 %.1f→%.1f px）' % (
            n_norm, qn['rowsTotal'], n_tight, qt['rowsTotal'], qt['base'], qt['rb']))
        check('正面上限：原排法的上限不裁掉任何一欄', qn['pageCount'] == 1 and all(c['clip'] <= 0 for pg in qn['info'] for c in pg))
        check('正面上限：超過後先「縮小列高」仍留在正面', n_tight > n_norm and qt['how'] == 'tight' and qt['rb'] < qt['base'], (n_norm, n_tight, qt['how']))
        check('正面上限：縮小後的字級不低於 11.3px（A3 印出來仍清楚）', (12.5 - (qt['base'] - qt['rb']) * 0.55) >= 11.3, (qt['base'], qt['rb']))
        check('正面上限：縮小排法也不被裁掉、品項都在', all(c['clip'] <= 0 and c['bottom'] <= c['h'] + 0.5 for pg in qt['info'] for c in pg) and qt['rowsDom'] == qt['rowsTotal'], qt['info'])
        q2 = await fr.evaluate(MEASURE, ['toast', n_tight + 1, 'menu'])
        check('正面上限：再多一個品項就換到背面', q2['pageCount'] == 2, q2['pageCount'])
        front_limit_rows = qt['rowsTotal']

        # ---------- 3. 跨到背面 ----------
        r = await fr.evaluate(MEASURE, ['toast', n_tight + 12, 'menu'])
        f = fills(r['info'])
        print('  [兩頁] 列數', r['rowsTotal'], '頁數', r['pageCount'], '排法', r['how'], '各欄填滿率', f, '續', r['conts'], '分類', r['titles'])
        check('兩頁：共 2 頁、沒有溢出', r['pageCount'] == 2 and not r['overflow'], r)
        check('兩頁：每一欄都沒被裁掉', all(c['clip'] <= 0 and c['bottom'] <= c['h'] + 0.5 for pg in r['info'] for c in pg), r['info'])
        check('兩頁：每個品項都有印出來', r['rowsDom'] == r['rowsTotal'], (r['rowsDom'], r['rowsTotal']))
        front = [c['bottom'] / c['h'] for c in r['info'][0] if c['n']]
        check('兩頁：正面每欄都有拉高到接近滿（≥ 90%）', min(front) >= 0.9, front)
        check('兩頁：背面有內容', sum(c['n'] for c in r['info'][1]) > 0, r['info'][1])
        t0 = {x.replace('（續）', '') for x in r['titles'][0]}; t1 = {x.replace('（續）', '') for x in r['titles'][1]}
        check('兩頁：同一個分類不會被硬切在正反兩面', not (t0 & t1), (t0 & t1))
        check('兩頁：頁尾提示「背面還有更多品項」與頁碼', '背面還有更多品項' in r['foot'][0] and '第 1／2 頁' in r['foot'][0] and '第 2／2 頁' in r['foot'][1], r['foot'])
        check('兩頁：容量提示文字', '排到背面' in r['text'], r['text'])
        # 某個分類大到正面放不下，才允許逐列接續到背面
        r = await fr.evaluate(MEASURE, ['toast', 130, 'menu'])
        print('  [大分類] 排法', r['how'], '頁數', r['pageCount'], '分類', r['titles'])
        check('大分類：一個分類比正面還大時仍排得下（逐列接續到背面）', r['pageCount'] == 2 and not r['overflow'] and r['rowsDom'] == r['rowsTotal'], r)

        if os.environ.get('SNAP'):   # 目視檢查用：SNAP=資料夾 python tests/layout_e2e.py
            for tag, n in [('one', 0), ('tight', n_tight), ('two', n_tight + 12)]:
                await fr.evaluate(MEASURE, ['toast', n, 'menu'])
                await fr.evaluate("document.getElementById('render').style.left = '0'")
                for i, el in enumerate(await fr.locator('#render .sheet').all()):
                    await el.screenshot(path=os.path.join(os.environ['SNAP'], '%s_%d.png' % (tag, i + 1)))
                await fr.evaluate("document.getElementById('render').style.left = '-30000px'")

        # ---------- 3b. 只印單面：不排到背面 ----------
        await fr.evaluate("SINGLE_PAGE = true")
        r = await fr.evaluate(MEASURE, ['toast', n_tight + 5, 'menu'])
        check('只印單面：多出來的品項仍擠在單面（列高縮更小）、沒有背面', r['pageCount'] == 1 and not r['overflow'] and r['rowsDom'] == r['rowsTotal'], r['text'])
        r = await fr.evaluate(MEASURE, ['toast', n_tight + 60, 'menu'])
        check('只印單面：真的放不下時不會偷偷排到背面，而是告訴還差幾列', r['pageCount'] == 1 and r['overflow'] and r['left'] > 0 and '只印單面放不下' in r['text'], r['text'])
        await fr.evaluate("SINGLE_PAGE = false")
        r = await fr.evaluate(MEASURE, ['toast', n_tight + 12, 'menu'])
        check('雙面：背面很空時提示可改只印單面', '只印單面' in r['text'], r['text'])

        # ---------- 4. 超過兩頁 ----------
        r = await fr.evaluate(MEASURE, ['toast', 330, 'menu'])
        print('  [爆量] 列數', r['rowsTotal'], 'overflow', r['overflow'], '差', r['left'])
        check('爆量：標示溢出並算出還差幾列', r['overflow'] and r['left'] > 0 and '放不下' in r['text'], r)
        msg = await fr.evaluate("makePdf().then(() => 'no error', e => e.message)")
        vcalls = await H.evaluate("__calls.filter(c => c === 'reserveVersion').length")
        check('爆量：輸出 PDF 被擋下，而且沒有用掉版本號', '放不下' in msg and vcalls == 0, (msg, vcalls))

        # ---------- 5. 隱藏的品項不佔位置 ----------
        r0 = await fr.evaluate(MEASURE, ['toast', 0, 'menu'])
        await fr.evaluate("""() => { const rows = window.__baseRows.map(r => ({ ...r, hidden: r.k.startsWith('toast|') ? true : r.hidden })); layoutSig = ''; rebuildFromRows(rows); }""")
        hidden_rows = await fr.evaluate("(() => { const h = sheetHTML('menu', 'V1'); return document.createElement('div'); })() && lastPlan.rowsTotal")
        check('隱藏整個分類後，列數減少', hidden_rows < r0['rowsTotal'], (hidden_rows, r0['rowsTotal']))
        fill_h = await fr.evaluate("lastPlan.cols.map(c => +c.fill.toFixed(2))")
        print('  [隱藏吐司] 列數', hidden_rows, '各欄填滿率（含拉高後）', fill_h)

        # ---------- 6. 空白核對表也走同一套 ----------
        r = await fr.evaluate(MEASURE, ['toast', 0, 'blank'])
        check('核對表：不被裁掉、每個品項都在', not r['overflow'] and r['rowsDom'] == r['rowsTotal'] and all(c['clip'] <= 0 and c['bottom'] <= c['h'] + 0.5 for pg in r['info'] for c in pg), r)
        print('  [核對表] 頁數', r['pageCount'], '排法', r['how'])

        # ---------- 7. 真的輸出 PDF：兩頁，LINE QR 掃得到 ----------
        await fr.evaluate("""() => { layoutSig = ''; rebuildFromRows(window.__baseRows); }""")
        await fr.evaluate(MEASURE, ['toast', n_tight + 12, 'menu'])
        f = await fr.evaluate("makePdf().then(x => x.id)")
        b64 = await H.evaluate("(id => Utilities.base64Encode(__store.files[id].blob.getBytes()))", f)
        pdf = os.path.join(TMP, 'layout2.pdf'); open(pdf, 'wb').write(base64.b64decode(b64))
        for x in os.listdir(TMP):
            if x.startswith('lay-'): os.remove(os.path.join(TMP, x))
        pdf_to_pngs(pdf, os.path.join(TMP, 'lay'), 100)
        pngs = sorted(x for x in os.listdir(TMP) if x.startswith('lay-'))
        qrs = [rr.text for x in pngs for rr in zxingcpp.read_barcodes(Image.open(os.path.join(TMP, x)))]
        check('輸出 PDF：兩頁 A3', len(pngs) == 2, pngs)
        check('輸出 PDF：正面 LINE QR 掃得到', any('lin.ee' in t for t in qrs), qrs)

        check('全程沒有 JS 錯誤', not errors, errors)
        print('\n  ★ 弘林菜單目前 %d 列；A3 正面最多約 %d 列（含自動縮小列高）' % (r0['rowsTotal'], front_limit_rows))
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
