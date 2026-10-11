"""店務收支＋主畫面測試：固定廠商、快速記帳（含鍵盤輸入）、其他支出、收入、月結待付與結清、月報表、權限（店主／夥伴）、
點餐機式主畫面的大按鈕與徽章，以及真的在瀏覽器操作記帳畫面。
執行：python tests/ledger_e2e.py
"""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T, SRC = os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'src')
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:500]))

NAMES = ['Page', 'Customer', 'Tools', 'Login', 'Admin', 'Account', 'Setup', 'Brand', 'Staff', 'Clock', 'Apply', 'Join', 'Avail', 'Ledger', 'Home']
def files_json():
    return json.dumps({n: open(os.path.join(SRC, n + '.html'), encoding='utf-8').read() for n in NAMES}).replace('</', '<\\/')

SEED = """
(function () {
  __store.props.ssId = 'test';
  var p = __ss.insertSheet('價格表'); p.data = [['弘林'], [''], [''], [''], ['代碼']];
  var real = Date.now; window.__real = real; window.__off = 0; Date.now = function () { return real.call(Date) + window.__off; };
})();
"""
HOST = """<!doctype html><html><head><meta charset="utf-8">
<script>window.__REAL_CODE = true;</script>
<script src="/mock.js"></script><script src="/Code.gs.js"></script><script src="/Tools.gs.js"></script><script src="/Tenant.gs.js"></script><script src="/Mail.gs.js"></script><script src="/Auth.gs.js"></script><script src="/Billing.gs.js"></script><script src="/Provision.gs.js"></script><script src="/Shop.gs.js"></script><script src="/BrandServer.gs.js"></script><script src="/StaffServer.gs.js"></script><script src="/LedgerServer.gs.js"></script><script src="/HomeServer.gs.js"></script><script src="/saas_mock.js"></script>
<script>window.__FILES = %s;</script><script src="/seed.js"></script>
<script>
function openPage(params) {
  var html = doGet({ parameter: params }).getContent();
  html = html.replace('<head>', '<head><script>window.google = parent.google;<\\/script>');
  return new Promise(function (res) { var f = document.getElementById('f'); f.onload = function () { setTimeout(function () { res(true); }, 500); }; f.srcdoc = html; });
}
</script></head><body style="margin:0"><iframe id="f" style="width:420px;height:900px;border:0"></iframe></body></html>"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 420, 'height': 900})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        if os.environ.get('DEBUG'): page.on('pageerror', lambda e: print('PAGEERR', str(e)[:300]))
        async def route(r):
            u = r.request.url
            if u == 'http://t/': return await r.fulfill(body=HOST % files_json(), content_type='text/html; charset=utf-8')
            if u.endswith('/mock.js'): return await r.fulfill(path=os.path.join(T, 'tools_mock.js'), content_type='text/javascript')
            if u.endswith('/saas_mock.js'): return await r.fulfill(path=os.path.join(T, 'saas_mock.js'), content_type='text/javascript')
            if u.endswith('/Code.gs.js'): return await r.fulfill(path=os.path.join(SRC, 'Code.gs'), content_type='text/javascript')
            if u.endswith('/Tools.gs.js'): return await r.fulfill(path=os.path.join(SRC, 'ToolsServer.gs'), content_type='text/javascript')
            m = re.search(r'/(Tenant|Mail|Auth|Billing|Provision|Shop|BrandServer|StaffServer|LedgerServer|HomeServer)\.gs\.js$', u)
            if m: return await r.fulfill(path=os.path.join(SRC, m.group(1) + '.gs'), content_type='text/javascript')
            if u.endswith('/seed.js'): return await r.fulfill(body=SEED, content_type='text/javascript')
            return await r.abort()
        await page.route('**/*', route)
        await page.goto('http://t/')
        H = page.main_frame
        check('所有指令碼載入無錯誤', not errors, errors)

        async def ev(js, arg=None): return await H.evaluate(js, arg)
        async def fn(name, *args):
            return await ev("([n, a]) => { try { var r = window[n].apply(null, a); return { v: r === undefined ? null : r }; } catch (e) { return { err: String(e.message || e) }; } }", [name, list(args)])
        async def at(hhmm):
            await ev("t => { var d = new Date(window.__real.call(Date) + 8 * 3600000); var day = d.toISOString().slice(0, 10); window.__off = new Date(day + 'T' + t + ':00+08:00').getTime() - window.__real.call(Date); }", hhmm)

        await ev("setupCenter()")
        sid = await ev("createTestShop()")
        tok = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: shopById_(s).tv }, 1)", sid)
        await ev("s => { CTX = { shopId: s, ssId: shopById_(s).ssId, shop: shopById_(s) }; _spMap = null; props_().setProperty('cfg', JSON.stringify({ name: '收支測試店', notifyEmail: 'boss@example.com' })); }", sid)
        inv = await fn('ownInvite', tok, '小幫手'); code = inv['v']['code']
        tokP = (await ev("c => authInvite(c, 'devP')", code))['token']
        await at('10:00')
        today = await ev("stToday_()"); yest = await ev("t => stAdd_(t, -1)", today); old = await ev("t => stAdd_(t, -3)", today)

        # ================= 廠商 =================
        st = (await fn('lgState', tok, ''))['v']
        check('收支：初始狀態沒有廠商、分類與付款方式齊全、店主看得到報表', st['owner'] and st['vendors'] == [] and '進貨：食材' in st['outCats'] and '現場營業額' in st['inCats'] and st['pays'] == ['現金', '轉帳', '信用卡', '月結'] and 'report' in st, st)
        r = await fn('lgVendorSave', {'name': '', 'cat': '進貨：食材'}, tok); check('廠商：沒填名稱被擋', 'err' in r and '名稱' in r['err'], r)
        r = await fn('lgVendorSave', {'name': '阿財肉品', 'cat': '進貨：食材', 'pay': '月結', 'quick': '1200, 2500，4000, 0, 99999999, 5000, 6000'}, tok)
        check('廠商：新增固定廠商，常用金額最多 4 個且過濾不合理的值', 'err' not in r and r['v'][0]['name'] == '阿財肉品' and r['v'][0]['quick'] == [1200, 2500, 4000, 5000] and r['v'][0]['pay'] == '月結', r)
        vid1 = r['v'][0]['id']
        r = await fn('lgVendorSave', {'name': '阿財肉品'}, tok); check('廠商：同名被擋', 'err' in r and '已經有' in r['err'], r)
        r = await fn('lgVendorSave', {'name': '大成飲料', 'cat': '進貨：飲料', 'pay': '現金', 'quick': '800'}, tok); vid2 = r['v'][1]['id']
        r = await fn('lgVendorSave', {'name': '亂寫', 'cat': '不存在的分類', 'pay': '亂寫'}, tok)
        check('廠商：分類或付款方式亂填會改回預設', r['v'][2]['cat'] == '進貨：食材' and r['v'][2]['pay'] == '現金', r)
        r = await fn('lgVendorSave', {'name': '夥伴想加'}, tokP); check('權限：夥伴不能新增或修改廠商', 'err' in r and '店主' in r['err'], r)
        r = await fn('lgVendorSave', {'id': vid2, 'name': '大成飲料行', 'cat': '進貨：飲料', 'pay': '轉帳', 'quick': '800, 1600'}, tok)
        check('廠商：修改名稱、付款方式與常用金額', [v for v in r['v'] if v['id'] == vid2][0]['name'] == '大成飲料行' and [v for v in r['v'] if v['id'] == vid2][0]['quick'] == [800, 1600], r)
        r = await fn('lgVendorDelete', [v for v in r['v'] if v['name'] == '亂寫'][0]['id'], tok); check('廠商：停用後不再出現在記帳清單', all(v['name'] != '亂寫' for v in r['v']) and len(r['v']) == 2, r)
        check('廠商：亂填通行證被拒絕', 'err' in await fn('lgVendorSave', {'name': 'x'}, 'garbage') and 'err' in await fn('lgState', 'garbage', ''))

        # ================= 記帳 =================
        r = await fn('lgAdd', {'type': '支出', 'amount': 0}, tok); check('記帳：沒輸入金額被擋', 'err' in r and '金額' in r['err'], r)
        r = await fn('lgAdd', {'type': '支出', 'amount': 99999999}, tok); check('記帳：金額太大被擋', 'err' in r and '太大' in r['err'], r)
        r = await fn('lgAdd', {'type': '支出', 'amount': 100, 'date': await ev("t => stAdd_(t, 2)", today)}, tok); check('記帳：不能記未來的日期', 'err' in r and '未來' in r['err'], r)
        r = await fn('lgAdd', {'type': '支出', 'amount': 100, 'vendorId': 'V999'}, tok); check('記帳：找不到廠商被擋', 'err' in r and '廠商' in r['err'], r)
        r = await fn('lgAdd', {'type': '支出', 'vendorId': vid1, 'amount': '2,500'}, tok)
        check('固定廠商記帳：分類與付款方式自動帶入廠商預設（進貨：食材、月結），金額逗號可解析', 'err' not in r and r['v']['today'][0]['amt'] == 2500 and r['v']['today'][0]['cat'] == '進貨：食材' and r['v']['today'][0]['pay'] == '月結' and r['v']['today'][0]['vendor'] == '阿財肉品', r)
        check('月結：記帳後標示「未結清」', r['v']['today'][0]['paid'] is False)
        r = await fn('lgAdd', {'type': '支出', 'cat': '水電瓦斯', 'amount': 1830, 'pay': '轉帳', 'note': '10 月電費'}, tok); check('其他支出：選分類記帳，付款方式「轉帳」視為已付', r['v']['today'][1]['cat'] == '水電瓦斯' and r['v']['today'][1]['paid'] is True and r['v']['today'][1]['note'] == '10 月電費', r)
        r = await fn('lgAdd', {'type': '支出', 'cat': '亂寫', 'amount': 50}, tok); check('其他支出：分類亂填會改成「其他」', r['v']['today'][2]['cat'] == '其他', r)
        r = await fn('lgAdd', {'type': '收入', 'cat': '現場營業額', 'amount': 12800, 'pay': '月結'}, tok); check('收入：記營業額；收入不能用月結（改成轉帳）', r['v']['today'][3]['type'] == '收入' and r['v']['today'][3]['pay'] == '轉帳', r)
        await fn('lgAdd', {'type': '支出', 'vendorId': vid2, 'amount': 800, 'date': yest}, tok)
        st = (await fn('lgState', tok, ''))['v']
        check('今日合計：收入 12,800、支出 4,380；淨額 8,420', st['todaySum']['inn'] == 12800 and st['todaySum']['out'] == 4380 and st['todaySum']['net'] == 8420, st['todaySum'])
        check('狀態：每家廠商最近一次金額（給畫面快速帶入）', st['recent'][vid1] == 2500 and st['recent'][vid2] == 800, st['recent'])

        # ================= 採購憑證：發票號碼、購買品項、應稅金額、採購人員 =================
        before_ids = set(x['id'] for x in (await fn('lgReport', today[:7], tok))['v']['entries'])
        base = {'type': '支出', 'vendorId': vid1, 'amount': 2100, 'pay': '轉帳'}
        r = await fn('lgAdd', dict(base, doc='統一發票'), tok); check('發票：選統一發票但沒填號碼被擋', 'err' in r and '發票號碼' in r['err'], r)
        r = await fn('lgAdd', dict(base, doc='統一發票', invoice='A123'), tok); check('發票：號碼格式不對被擋（要 2 個英文字母＋8 位數字）', 'err' in r and '8 位數字' in r['err'], r)
        r = await fn('lgAdd', dict(base, doc='統一發票', invoice='ab-12345678', items='雞腿肉 20 斤、蛋 5 箱'), tok); e1 = r['v']['today'][-1] if 'v' in r else {}
        check('發票：號碼自動轉大寫、去掉橫線；應稅金額預設＝含稅 ÷ 1.05（2100 → 2000、稅額 100）', 'err' not in r and e1['inv'] == 'AB12345678' and e1['taxable'] == 2000 and e1['tax'] == 100 and e1['doc'] == '統一發票', r)
        check('發票：購買品項與採購人員（預設登入者，店主）一起記下', e1['items'] == '雞腿肉 20 斤、蛋 5 箱' and e1['buyer'] == '店主', e1)
        r = await fn('lgAdd', dict(base, doc='統一發票', invoice='AB12345678'), tok); check('發票：同一個發票號碼重複記帳被擋並提醒', 'err' in r and '已經記過' in r['err'], r)
        r = await fn('lgAdd', dict(base, doc='統一發票', invoice='AB12345678', allowDup=True), tok); check('發票：確認後可以選「仍要記帳」', 'err' not in r, r)
        r = await fn('lgAdd', dict(base, doc='統一發票', invoice='CD00000001', taxable=1800), tok); e2 = r['v']['today'][-1]
        check('發票：應稅金額可手動修改（1800 → 稅額 300）', e2['taxable'] == 1800 and e2['tax'] == 300, e2)
        r = await fn('lgAdd', dict(base, doc='統一發票', invoice='CD00000002', taxable=2500), tok); check('發票：應稅金額不能超過含稅金額', 'err' in r and '應稅' in r['err'], r)
        r = await fn('lgAdd', dict(base, doc='統一發票', invoice='CD00000003', taxFree=True), tok); e3 = r['v']['today'][-1]
        check('發票：免稅時應稅金額＝金額、稅額 0', e3['taxable'] == 2100 and e3['tax'] == 0, e3)
        r = await fn('lgAdd', dict(base, doc='收據', invoice='R-0099', buyer='阿志'), tok); e4 = r['v']['today'][-1]
        check('收據：不算進項稅額，編號與採購人員照記', e4['doc'] == '收據' and e4['inv'] == 'R0099' and e4['taxable'] is None and e4['buyer'] == '阿志', e4)
        r = await fn('lgAdd', dict(base, doc='無憑證', invoice='AB99999999'), tok); e5 = r['v']['today'][-1]
        check('無憑證：發票號碼不記', e5['inv'] == '' and e5['doc'] == '無憑證', e5)
        r = await fn('lgAdd', {'type': '收入', 'cat': '現場營業額', 'amount': 500, 'doc': '統一發票', 'invoice': 'AB12345678', 'buyer': '誰'}, tok); e6 = r['v']['today'][-1]
        check('收入：不需要憑證與採購人員', e6['doc'] == '' and e6['inv'] == '' and e6['buyer'] == '', e6)
        st = (await fn('lgState', tok, ''))['v']
        check('狀態：採購人員清單（店主＋夥伴＋在職員工）與廠商最近品項建議', st['buyers'][0] == '店主' and '小幫手' in st['buyers'] and st['me'] == '店主' and st['itemsBy'][vid1] and '雞腿肉' in st['itemsBy'][vid1][0], (st['buyers'], st['itemsBy']))
        rep = (await fn('lgReport', today[:7], tok))['v']
        check('月報表：統一發票張數、含稅合計、應稅金額、進項稅額（只算統一發票）', rep['invoice']['n'] == 4 and rep['invoice']['tax'] == 100 + 100 + 300 + 0 and rep['invoice']['taxable'] == 2000 + 2000 + 1800 + 2100, rep['invoice'])
        check('月報表：採購人員支出排行', any(b['name'] == '店主' for b in rep['byBuyer']) and any(b['name'] == '阿志' for b in rep['byBuyer']), rep['byBuyer'])
        # 清掉這批發票測試資料，避免影響後面的金額驗證
        for ent in [x for x in (await fn('lgReport', today[:7], tok))['v']['entries'] if x['id'] not in before_ids]:
            await fn('lgDelete', ent['id'], tok)
        check('清除測試發票資料後，今日合計恢復', (await fn('lgState', tok, ''))['v']['todaySum']['out'] == 4380)

        # ================= 夥伴權限 =================
        stp = (await fn('lgState', tokP, ''))['v']
        check('夥伴：只看得到今天明細與廠商，沒有報表', stp['owner'] is False and 'report' not in stp and len(stp['vendors']) == 2 and len(stp['entries']) == 4, stp.keys())
        r = await fn('lgAdd', {'type': '支出', 'vendorId': vid2, 'amount': 800}, tokP); pid = r['v']['id']; check('夥伴：可以記今天的帳，採購人員預設是夥伴自己的名字', 'err' not in r and r['v']['today'][-1]['buyer'] == '小幫手', r)
        r = await fn('lgAdd', {'type': '支出', 'cat': '雜支', 'amount': 60, 'date': yest}, tokP); check('夥伴：可以記昨天的帳', 'err' not in r, r)
        r = await fn('lgAdd', {'type': '支出', 'cat': '雜支', 'amount': 60, 'date': old}, tokP); check('夥伴：不能記更早的帳（請店主補記）', 'err' in r and '店主' in r['err'], r)
        r = await fn('lgReport', '', tokP); check('夥伴：不能看報表', 'err' in r and '店主' in r['err'], r)
        r = await fn('lgSettle', vid1, [], tokP); check('夥伴：不能結清月結', 'err' in r, r)
        r = await fn('lgDelete', pid, tokP); check('夥伴：可以撤銷自己剛記的帳', 'err' not in r and all(e['id'] != pid for e in r['v']['today']), r)
        r = await fn('lgAdd', {'type': '支出', 'vendorId': vid2, 'amount': 800}, tokP); pid2 = r['v']['id']
        first = (await fn('lgState', tok, ''))['v']['entries'][0]['id']
        r = await fn('lgDelete', first, tokP); check('夥伴：不能刪店主記的帳', 'err' in r and '自己' in r['err'], r)
        await at('10:20')
        r = await fn('lgDelete', pid2, tokP); check('夥伴：超過 10 分鐘就不能撤銷', 'err' in r and '10 分鐘' in r['err'], r)
        await at('10:30')
        r = await fn('lgDelete', pid2, tok); check('店主：可以刪任何一筆', 'err' not in r and all(e['id'] != pid2 for e in r['v']['today']), r)

        # ================= 月結與報表 =================
        rep = (await fn('lgReport', today[:7], tok))['v']
        check('月報表：本月支出分類與廠商排行', any(c['name'] == '水電瓦斯' and c['amt'] == 1830 for c in rep['byCat']) and any(c['name'] == '進貨：食材' and c['amt'] == 2500 for c in rep['byCat']) and rep['byVendor'][0]['name'] == '阿財肉品', rep['byCat'])
        check('月報表：收入、支出、淨額與每日統計', rep['sum']['inn'] == 12800 and rep['sum']['out'] == rep['sum']['inn'] - rep['sum']['net'] and len(rep['days']) >= 1, rep['sum'])
        check('月報表：月結待付款只列阿財肉品 2,500', len(rep['unpaid']) == 1 and rep['unpaid'][0]['name'] == '阿財肉品' and rep['unpaid'][0]['amt'] == 2500, rep['unpaid'])
        check('月報表：明細由新到舊', all(rep['entries'][i]['d'] >= rep['entries'][i + 1]['d'] for i in range(len(rep['entries']) - 1)))
        prev = await ev("t => { var d = new Date(Date.parse(t.slice(0, 7) + '-01T00:00:00Z')); d.setUTCMonth(d.getUTCMonth() - 1); return d.toISOString().slice(0, 7); }", today)
        check('月報表：上個月沒有資料也能查（全部是 0）', (await fn('lgReport', prev, tok))['v']['sum']['out'] == 0 and (await fn('lgReport', 'abc', tok))['v']['month'] == today[:7])
        r = await fn('lgSettle', vid1, [], tok); check('結清：把阿財肉品的月結全部標成已付款', r['v']['settled'] == 1, r)
        check('結清後：待付款清單清空、仍記在支出', (await fn('lgReport', today[:7], tok))['v']['unpaid'] == [] and (await fn('lgReport', today[:7], tok))['v']['sum']['unpaid'] == 0)
        check('收支資料以純文字存在試算表（金額不會變成日期或科學記號）', await ev("() => stRows_('ledger').every(r => String(r['金額']) === String(Number(r['金額'])))"))

        # ================= 主畫面 =================
        hs = (await fn('homeState', tok))['v']
        ids = [t['id'] for t in hs['tiles']]
        check('主畫面（店主）：依分類列出菜單、行銷、店務、財務、人員、設定的大按鈕', all(x in ids for x in ['menu', 'customer', 'notice', 'table', 'wifi', 'card', 'hiring', 'cal', 'hand', 'ledger', 'staff', 'clock', 'logo', 'setup', 'account']) and [c['n'] for c in hs['cats']] == ['菜單', '行銷', '店務', '財務', '人員', '設定與帳號'], (ids, hs['cats']))
        check('主畫面：每個按鈕都屬於一個分類，工具類按鈕直達店家工具的對應分頁（&tab=）', all(t['cat'] in [c['k'] for c in hs['cats']] for t in hs['tiles']) and 'tab=notice' in [t for t in hs['tiles'] if t['id'] == 'notice'][0]['url'].replace('\\/', '/') and 'tab=card' in [t for t in hs['tiles'] if t['id'] == 'card'][0]['url'].replace('\\/', '/') and 'hiring=1' in [t for t in hs['tiles'] if t['id'] == 'hiring'][0]['url'].replace('\\/', '/'))
        check('主畫面：店務收支按鈕有「今日支出」徽章', '今日支出' in [t for t in hs['tiles'] if t['id'] == 'ledger'][0]['badge'], [t['badge'] for t in hs['tiles']])
        hp = (await fn('homeState', tokP))['v']
        check('主畫面（夥伴）：沒有人員與班表、店家設定、帳號、分店', all(t['id'] not in ('staff', 'setup', 'account', 'brand') for t in hp['tiles']) and any(t['id'] == 'ledger' for t in hp['tiles']) and any(t['id'] == 'notice' for t in hp['tiles']), [t['id'] for t in hp['tiles']])
        await fn('stApplySubmit', sid, {'name': '應徵者', 'phone': '0911222333'})
        check('主畫面：有待處理的徵才登記時，人員與班表顯示徽章', '1 件待處理' in [t for t in (await fn('homeState', tok))['v']['tiles'] if t['id'] == 'staff'][0]['badge'])
        check('網址：?p=home、?p=ledger 會開對應頁面，沒有通行證則回登入頁',
              '主畫面' in await ev("t => doGet({ parameter: { p: 'home', t } }).getContent()", tok) and '店務收支' in await ev("t => doGet({ parameter: { p: 'ledger', t } }).getContent()", tok) and '登入' in await ev("() => doGet({ parameter: { p: 'ledger', t: 'bad' } }).getContent()"))
        ci = await fn('authCheck', tok)
        check('登入資訊帶主畫面與收支網址', 'p=home' in ci['v']['urls']['home'].replace('\\\\/', '/') and 'p=ledger' in ci['v']['urls']['ledger'].replace('\\\\/', '/') if 'v' in ci and ci['v'].get('ok') else False, ci)

        # ================= 瀏覽器：記帳畫面（點餐機形式）=================
        await ev("(t) => { var s = 1; }", None)
        await H.evaluate("p => openPage(p)", {'p': 'ledger', 't': tok}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelectorAll("#vTiles .tile").length >= 2', timeout=15000)
        check('記帳畫面：固定廠商是大按鈕，上面寫分類、付款方式與上次金額', await fr.locator('#vTiles .tile[data-v]').count() == 2 and '上次 2,500' in await fr.inner_text('#vTiles'))
        check('記帳畫面：下方有「其他支出」「收入」大按鈕', '其他支出' in await fr.inner_text('#oTiles') and '收入' in await fr.inner_text('#oTiles'))
        await page.screenshot(path=os.path.join(os.environ.get('TEMP', '.'), 'ledger_pos.png'))
        await fr.click(f'#vTiles [data-v="{vid1}"]'); await fr.wait_for_selector('#sheet:not(.hidden)')
        check('點廠商：開全螢幕記帳面板，標題是廠商名，付款方式預設廠商設定', '阿財肉品' in await fr.inner_text('#shT') and 'on' in (await fr.get_attribute('#pays [data-p="月結"]', 'class')) and await fr.is_disabled('#go'))
        check('面板：常用金額按鈕（含上次金額）', '1,200' in await fr.inner_text('#quick') and '2,500' in await fr.inner_text('#quick'))
        for k in '1250': await fr.click(f'#pad [data-k="{k}"]')
        check('廠商記帳：預設憑證是統一發票，顯示發票號碼、應稅金額（預設含稅÷1.05）、稅額、購買品項、採購人員', 'on' in (await fr.get_attribute('#docs [data-doc="統一發票"]', 'class')) and await fr.is_visible('#inv') and await fr.input_value('#taxable') == '1190' and await fr.inner_text('#taxv') == '60' and await fr.is_visible('#items') and 'on' in (await fr.get_attribute('#buyers [data-by="店主"]', 'class')), (await fr.input_value('#taxable'), await fr.inner_text('#taxv')))
        check('數字鍵盤：按 1-2-5-0 顯示 1,250，記帳按鈕寫出金額', await fr.inner_text('#amt') == '1,250' and 'NT$ 1,250' in await fr.inner_text('#go'))
        await fr.click('#pad [data-k="del"]'); check('數字鍵盤：退格', await fr.inner_text('#amt') == '125')
        await fr.click('#quick [data-q="4000"]'); check('常用金額一鍵帶入，應稅金額跟著重算（4000 → 3810、稅額 190）', await fr.inner_text('#amt') == '4,000' and await fr.input_value('#taxable') == '3810' and await fr.inner_text('#taxv') == '190')
        await fr.click('#go'); await page.wait_for_timeout(300)
        check('沒填發票號碼按「記下」會提示格式', '發票號碼' in await fr.inner_text('#shMsg') and await fr.is_visible('#sheet'))
        await fr.fill('#inv', 'ab12345678'); await fr.fill('#items', '雞腿肉 20 斤')
        check('發票號碼輸入自動轉大寫', await fr.input_value('#inv') == 'AB12345678')
        await fr.click('#pays [data-p="轉帳"]'); await fr.fill('#note', '補貨'); await fr.click('#dates [data-d="' + yest + '"]')
        await fr.click('#go');
        await fr.wait_for_selector('#sheet.hidden', state='attached', timeout=8000)
        check('按「記下」：面板關閉並出現「已記」提示與撤銷按鈕', '已記' in await fr.inner_text('#toastT') and await fr.is_visible('#undo'))
        e = [x for x in (await fn('lgReport', today[:7], tok))['v']['entries'] if x['note'] == '補貨'][0]
        check('記進去的是廠商、金額 4,000、轉帳、昨天、備註、發票號碼、品項、應稅金額 3,810、稅額 190、採購人員', e['vendor'] == '阿財肉品' and e['amt'] == 4000 and e['pay'] == '轉帳' and e['d'] == yest and e['inv'] == 'AB12345678' and e['items'] == '雞腿肉 20 斤' and e['taxable'] == 3810 and e['tax'] == 190 and e['buyer'] == '店主', e)
        await fr.click('#modes [data-m=today]'); await fr.click('#modes [data-m=pos]')
        await fr.click(f'#vTiles [data-v="{vid1}"]'); await fr.wait_for_selector('#sheet:not(.hidden)')
        await fr.click('#quick [data-q="2500"]'); await fr.fill('#inv', 'AB12345678'); await fr.click('#go'); await page.wait_for_timeout(500)
        check('重複的發票號碼：提示已經記過，按鈕變成「仍要記帳」', '已經記過' in await fr.inner_text('#shMsg') and '仍要記帳' in await fr.inner_text('#go'))
        await fr.click('#docs [data-doc="無憑證"]'); await fr.click('#go'); await fr.wait_for_selector('#sheet.hidden', state='attached', timeout=8000)
        check('改選「無憑證」就不需要發票號碼，記帳成功', any(x['doc'] == '無憑證' and x['amt'] == 2500 and x['inv'] == '' for x in (await fn('lgState', tok, ''))['v']['entries']))
        await fr.click('#undo'); await fr.wait_for_function('document.querySelector("#gmsg").innerText.includes("撤銷")', timeout=8000)
        check('按「撤銷」：剛記的那筆（無憑證 2,500）被刪除，先前的補貨那筆還在', sum(1 for x in (await fn('lgState', tok, ''))['v']['entries'] if x['doc'] == '無憑證' and x['amt'] == 2500) == 1 and any(x['note'] == '補貨' for x in (await fn('lgReport', today[:7], tok))['v']['entries']))
        await fr.click('#oTiles [data-o="out"]'); await fr.wait_for_selector('#sheet:not(.hidden)')
        check('其他支出：面板有分類按鈕可選', await fr.locator('#cats [data-c]').count() == 10 and await fr.is_visible('#catBox'))
        await fr.click('#cats [data-c="租金"]')
        for k in '28000': await fr.click(f'#pad [data-k="{k}"]')
        await fr.click('#go'); await fr.wait_for_selector('#sheet.hidden', state='attached', timeout=8000)
        check('其他支出：選分類、鍵入金額後記帳', any(x['cat'] == '租金' and x['amt'] == 28000 for x in (await fn('lgState', tok, ''))['v']['entries']))
        await fr.click('#oTiles [data-o="in"]'); await fr.wait_for_selector('#sheet:not(.hidden)')
        check('收入：分類改成營業額等，付款方式沒有「月結」', '現場營業額' in await fr.inner_text('#cats') and await fr.locator('#pays [data-p="月結"]').count() == 0)
        await fr.click('#shX'); await fr.wait_for_selector('#sheet.hidden', state='attached')
        await fr.click('#modes [data-m=today]')
        check('今日分頁：收入、支出、淨額大數字與明細', '今日支出' in await fr.inner_text('#tKpi') and '租金' in await fr.inner_text('#tList'))
        await fr.click('#modes [data-m=report]')
        check('報表分頁（店主）：收入、支出、淨額、月結待付大數字與分類長條，以及採購人員、統一發票進項稅額', '月結待付' in await fr.inner_text('#rKpi') and '租金' in await fr.inner_text('#rCat') and '店主' in await fr.inner_text('#rBuy') and '進項稅額' in await fr.inner_text('#rInv') and '190' in await fr.inner_text('#rInv'))
        await fr.click('#mPrev'); await fr.wait_for_timeout(500)
        check('報表分頁：切換上個月', await fr.inner_text('#mTitle') == prev.replace('-', ' / '))
        await fr.click('#modes [data-m=vendors]')
        await fr.fill('#vName', '好鮮蔬菜'); await fr.select_option('#vCat', '進貨：食材'); await fr.fill('#vQuick', '600, 900'); await fr.click('#vSave'); await fr.wait_for_function('document.querySelector("#vList").innerText.includes("好鮮蔬菜")', timeout=8000)
        check('廠商分頁：新增固定廠商後出現在清單', '好鮮蔬菜' in await fr.inner_text('#vList') and '600' in await fr.inner_text('#vList'))
        check('記帳畫面沒有 JS 錯誤', not errors, errors)
        # 夥伴看到的畫面
        # ================= 常用廠商置頂、叫貨日、收據上傳、憑證正本 =================
        JPG = 'iVBORw0KGgo='
        async def mails(): return await ev("__store.mails.slice()")
        r = await fn('lgVendorSave', {'id': vid2, 'name': '大成飲料行', 'cat': '進貨：飲料', 'pay': '轉帳', 'quick': '800', 'pin': True, 'orderDays': [4, 1, 9, 4]}, tok)
        vv = r['v']
        check('廠商：設為常用會置頂，叫貨日只收 0～6 且不重複', vv[0]['id'] == vid2 and vv[0]['pin'] and vv[0]['orderDays'] == [1, 4], vv)
        r = await fn('lgAdd', {'type': '支出', 'vendorId': vid2, 'amount': 900, 'pay': '現金', 'doc': '收據', 'invoice': 'R7', 'receipt': {'name': 'r.jpg', 'b64': JPG}}, tokP)
        e7 = r['v']['today'][-1]
        check('夥伴登記採購：可以附收據照片，收據憑證預設「正本未收到」', 'err' not in r and e7['hasFile'] and e7['orig'] == '未收到' and e7['buyer'] != '' , r)
        r = await fn('lgAdd', {'type': '支出', 'vendorId': vid2, 'amount': 100, 'receipt': {'name': 'r.exe', 'b64': JPG}}, tokP); check('收據：只收 JPG、PNG、PDF', 'err' in r and 'JPG' in r['err'], r)
        r = await fn('lgAdd', {'type': '支出', 'vendorId': vid2, 'amount': 100, 'receipt': {'name': 'r.jpg', 'b64': '!!!'}}, tokP); check('收據：壞檔案被擋', 'err' in r, r)
        r = await fn('lgSetOriginal', e7['id'], True, tokP); check('憑證正本：夥伴不能勾選', 'err' in r and '店主' in r['err'], r)
        r = await fn('lgSetOriginal', e7['id'], True, tok); check('憑證正本：店主勾「已收到」', 'err' not in r and r['v']['orig'] == '已收到', r)
        r = await fn('lgSetOriginal', e6['id'], True, tok); check('憑證正本：收入沒有憑證，不能勾', 'err' in r, r)
        r = await fn('lgReceiptUrl', e7['id'], tok); check('收據：店主取得雲端連結', 'err' not in r and r['v']['url'].startswith('https://drive.google.com/'), r)
        r = await fn('lgReceiptUrl', e7['id'], tokP); check('收據：夥伴不能開別人的收據連結', 'err' in r, r)
        e8 = (await fn('lgAdd', {'type': '支出', 'vendorId': vid2, 'amount': 300, 'doc': '收據', 'invoice': 'R8'}, tokP))['v']['today'][-1]
        r = await fn('lgAttach', e8['id'], {'name': 'later.png', 'b64': JPG}, tokP); check('收據：記帳的人事後可以補傳', 'err' not in r and [x for x in r['v']['today'] if x['id'] == e8['id']][0]['hasFile'], r)
        rep = (await fn('lgReport', today[:7], tok))['v']
        check('報表：列出還沒收到正本的憑證', e8['id'] in [x['id'] for x in rep['origPending']] and e7['id'] not in [x['id'] for x in rep['origPending']], rep['origPending'])
        # 叫貨：叫貨日、時間、負責人；當天提醒、已叫貨、隔天再提醒
        emp = (await fn('stEmpSave', {'name': '小明', 'pin': '1234', 'email': 'ming@example.com'}, tok))
        emp_id = [x for x in (await fn('stState', tok, ''))['v']['emps'] if x['name'] == '小明'][0]['id']
        etok = await ev("id => stEmpToken_(stEmpById_(id))", emp_id)
        tdow = await ev("t => stDow_(t)", today); ydow = await ev("t => stDow_(stAdd_(t, -1))", today)
        r = await fn('lgVendorSave', {'id': vid2, 'name': '大成飲料行', 'cat': '進貨：飲料', 'pay': '轉帳', 'quick': '800', 'pin': True, 'orderDays': [tdow], 'orderTime': '16:30', 'assignee': '小明'}, tok)
        v2 = [v for v in r['v'] if v['id'] == vid2][0]
        check('廠商：叫貨時間與負責人存得下來', v2['time'] == '16:30' and v2['assignee'] == '小明' and v2['orderDays'] == [tdow], v2)
        r = await fn('lgVendorSave', {'id': vid2, 'name': '大成飲料行', 'orderDays': [tdow]}, tok); v2 = [v for v in r['v'] if v['id'] == vid2][0]
        check('廠商：沒給時間與負責人時保留原設定', v2['time'] == '16:30' and v2['assignee'] == '小明', v2)
        st = (await fn('lgState', tok, ''))['v']
        check('狀態：今天要叫的廠商列出來，尚未叫貨', [x['name'] for x in st['orders']['today']] == ['大成飲料行'] and not st['orders']['today'][0]['done'] and '小明' in st['assignees'], st['orders'])
        await ev("() => tSetJson_('lg_order_last', '')")
        n20 = len(await mails()); r = await fn('lgOrderRemind_'); ms = (await mails())[n20:]
        check('叫貨提醒：叫貨日當天寄給店主與負責的員工', r['v']['sent'] == 2 and any(x['to'] == 'boss@example.com' and '今天要叫' in x['body'] and '大成飲料行' in x['body'] for x in ms) and any(x['to'] == 'ming@example.com' and '16:30' in x['body'] for x in ms), (r, ms))
        await ev("() => tSetJson_('lg_order_last', '')"); await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", ['orderEmp'])
        n24 = len(await mails()); r = await fn('lgOrderRemind_'); ms = (await mails())[n24:]
        check('通知信開關：關掉「叫貨寄給員工」→ 只寄店主', [x['to'] for x in ms] == ['boss@example.com'], ms)
        await ev("() => tSetJson_('lg_order_last', '')"); await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", ['order', 'orderEmp'])
        n25 = len(await mails()); r = await fn('lgOrderRemind_')
        check('通知信開關：叫貨兩個都關 → 不寄信', len(await mails()) == n25 and r['v']['sent'] == 0, r)
        await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", [])
        n21 = len(await mails()); r = await fn('lgOrderRemind_')
        check('叫貨提醒：一天只寄一次', r['v']['sent'] == 0 and len(await mails()) == n21, r)
        await ev("() => tSetJson_('lg_order_last', '')"); await at('08:00')
        r = await fn('lgOrderRemind_'); check('叫貨提醒：早上 9 點前不寄', r['v']['sent'] == 0, r); await at('10:00')
        r = await fn('stEmpHome', etok); eo = r['v']['orders']
        check('員工入口：只看到自己負責、今天要叫的廠商', [x['name'] for x in eo['today']] == ['大成飲料行'] and eo['overdue'] == [], eo)
        r = await fn('stOrderDone', tok, vid2); check('員工入口：店主通行證不能當員工按「已叫貨」', 'err' in r, r)
        r = await fn('stOrderDone', etok, vid1); check('員工入口：不是自己負責的廠商不能按', 'err' in r and '不是你負責' in r['err'], r)
        r = await fn('stOrderDone', etok, vid2); st = (await fn('lgState', tok, ''))['v']
        check('員工按「已叫貨」：老闆這邊同步變成已叫貨並記下是誰', 'err' not in r and st['orders']['today'][0]['done'] and st['orders']['today'][0]['by'] == '小明', (r, st['orders']))
        await ev("() => tSetJson_('lg_order_last', '')"); n22 = len(await mails()); r = await fn('lgOrderRemind_')
        check('叫貨提醒：已經叫完的不再提醒', r['v']['sent'] == 0 or all('大成飲料行' not in x['body'] for x in (await mails())[n22:]), r)
        # 昨天是叫貨日但沒叫 → 今天再提醒
        await fn('lgVendorSave', {'id': vid1, 'name': '阿財肉品', 'cat': '進貨：食材', 'pay': '月結', 'quick': '1200', 'orderDays': [ydow], 'assignee': '小明'}, tok)
        await ev("() => tSetJson_('lg_order_last', '')")
        st = (await fn('lgState', tok, ''))['v']
        check('狀態：昨天沒叫完的列為「逾期」', [x['name'] for x in st['orders']['overdue']] == ['阿財肉品'], st['orders'])
        n23 = len(await mails()); r = await fn('lgOrderRemind_'); ms = (await mails())[n23:]
        check('叫貨提醒：昨天沒叫的隔天再提醒（店主與負責人）', r['v']['sent'] == 2 and any('昨天沒叫' in x['body'] and '阿財肉品' in x['body'] for x in ms), (r, ms))
        r = await fn('lgOrdered', vid1, tokP); st = (await fn('lgState', tok, ''))['v']
        check('夥伴也能按「已叫貨」，逾期的就消失', 'err' not in r and st['orders']['overdue'] == [], (r, st['orders']))

        await H.evaluate("p => openPage(p)", {'p': 'ledger', 't': tokP}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelectorAll("#vTiles .tile").length >= 2', timeout=15000)
        check('夥伴的記帳畫面：沒有「報表」「廠商」分頁，也沒有「新增固定廠商」', await fr.locator('#modes [data-m=report]').is_hidden() and await fr.locator('#modes [data-m=vendors]').is_hidden() and await fr.locator('#vTiles [data-go]').count() == 0)
        # 主畫面
        await H.evaluate("p => openPage(p)", {'p': 'home', 't': tok}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelectorAll("#cats .tile").length > 3', timeout=15000)
        await page.screenshot(path=os.path.join(os.environ.get('TEMP', '.'), 'home_pos.png'))
        check('主畫面頁：店名、身分、時鐘與大按鈕格', '收支測試店' in await fr.inner_text('#nm') and '店主' in await fr.inner_text('#role') and await fr.locator('#cats .tile').count() >= 14)
        cats_txt = await fr.inner_text('#cats')
        check('主畫面頁：分類標題「菜單」「行銷」「店務」「財務」「人員」「設定與帳號」', all(x in cats_txt for x in ['菜單', '行銷', '店務', '財務', '人員', '設定與帳號']) and await fr.locator('#cats .cat').count() == 6)
        check('主畫面頁：店務收支按鈕連到收支頁並帶徽章，圖示用圖示庫', 'p=ledger' in (await fr.get_attribute('#cats a[href*="ledger"]', 'href') or '').replace('\\\\/', '/') and await fr.locator('#cats .tile svg.hl-icon').count() >= 14 and '今日支出' in await fr.inner_text('#cats'))
        await H.evaluate("p => openPage(p)", {'p': 'tools', 't': tok, 'tab': 'card'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('主畫面按「名片」直達店家工具的名片分頁', await fr.is_visible('#tab-card') and await fr.is_hidden('#tab-hand'))
        await H.evaluate("p => openPage(p)", {'t': tok, 'later': '1'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('菜單工具上方有「主畫面」「收支」連結', 'p=home' in (await fr.get_attribute('#homeLink', 'href') or '').replace('\\\\/', '/') and 'p=ledger' in (await fr.get_attribute('#ledgerLink', 'href') or '').replace('\\\\/', '/'))
        await H.evaluate("p => openPage(p)", {}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('登入頁：登入後有「進入主畫面」按鈕', await fr.locator('#goHome').count() == 1)
        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
