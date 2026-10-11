"""商家指南用的畫面截圖：用測試用的 Apps Script 模擬器，建立一家「示範店」並放進示範資料，
再用手機寬度（420px）把各功能畫面截下來，存到 guide/shots/。
執行：python scripts/make_guide_shots.py（約 1～2 分鐘；之後執行 python scripts/make_merchant_guide.py 產生指南）"""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T, SRC = os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'src')
OUT = os.path.join(ROOT, 'guide', 'shots'); os.makedirs(OUT, exist_ok=True)

NAMES = ['Page', 'Customer', 'Tools', 'Login', 'Admin', 'Account', 'Setup', 'Brand', 'Staff', 'Clock', 'Apply', 'Join', 'Ledger', 'Home', 'Avail']
def files_json():
    return json.dumps({n: open(os.path.join(SRC, n + '.html'), encoding='utf-8').read() for n in NAMES}).replace('</', '<\\/')
SEED = """
(function () {
  __store.props.ssId = 'test';
  var p = __ss.insertSheet('價格表'); p.data = [['示範'], [''], [''], [''], ['代碼']];
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
  return new Promise(function (res) { var f = document.getElementById('f'); f.style.height = '900px'; f.onload = function () { setTimeout(function () { res(true); }, 700); }; f.srcdoc = html; });
}
</script></head><body style="margin:0;background:#fff"><iframe id="f" style="width:420px;height:900px;border:0;display:block"></iframe></body></html>"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 420, 'height': 1800}, device_scale_factor=2)
        page = await ctx.new_page()
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
        async def ev(js, arg=None): return await H.evaluate(js, arg)
        async def fn(name, *args):
            r = await ev("([n, a]) => { try { var r = window[n].apply(null, a); return { v: r === undefined ? null : r }; } catch (e) { return { err: String(e.message || e) }; } }", [name, list(args)])
            if 'err' in r: print('  ！', name, r['err'][:120])
            return r.get('v')
        async def at(hhmm):
            await ev("t => { var d = new Date(window.__real.call(Date) + 8 * 3600000); var day = d.toISOString().slice(0, 10); window.__off = new Date(day + 'T' + t + ':00+08:00').getTime() - window.__real.call(Date); }", hhmm)

        # ---------- 建立示範店與示範資料 ----------
        await ev("setupCenter()"); sid = await ev("createTestShop()")
        tok = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: shopById_(s).tv }, 1)", sid)
        await ev("s => { CTX = { shopId: s, ssId: shopById_(s).ssId, shop: shopById_(s) }; _spMap = null; props_().setProperty('cfg', JSON.stringify({ name: '阿福早餐', tagline: '社區裡的早餐好味道', address: '台北市大安區和平東路一段 18 號', phone: '02-2345-6789', hours: '06:00–13:00', lineId: '@afubreakfast', primary: '#1B4F8A', accent: '#E8762A', notifyEmail: 'boss@example.com' })); props_().setProperty('t_shop', JSON.stringify({ name: '阿福早餐', tagline: '社區裡的早餐好味道', hours: '06:00–13:00', primary: '#1B4F8A', accent: '#E8762A', chips: '會員累點折抵；支援 LINE Pay；歡迎外帶', knockUrl: '', lineUrl: '' })); props_().setProperty('onboarded', '1'); }", sid)
        await at('09:30')
        today = await ev("stToday_()"); yest = await ev("t => stAdd_(t, -1)", today)
        draft = {'sections': [
            {'title': '蛋餅', 'columns': ['價格'], 'items': [{'name': '原味蛋餅', 'prices': [35], 'star': True}, {'name': '玉米蛋餅', 'prices': [45]}, {'name': '起司蛋餅', 'prices': [50], 'tags': ['egg', 'milk']}, {'name': '培根蛋餅', 'prices': [55]}]},
            {'title': '吐司漢堡', 'columns': ['價格'], 'items': [{'name': '火腿蛋吐司', 'prices': [45], 'star': True}, {'name': '豬排蛋堡', 'prices': [65]}, {'name': '雞腿蛋堡', 'prices': [75]}, {'name': '花生厚片', 'prices': [35], 'tags': ['peanut']}]},
            {'title': '飲料', 'columns': ['中杯', '大杯'], 'items': [{'name': '紅茶', 'prices': [25, 30]}, {'name': '奶茶', 'prices': [35, 45], 'star': True}, {'name': '豆漿', 'prices': [25, 35], 'tags': ['soy']}, {'name': '檸檬紅茶', 'prices': [35, 45]}]}]}
        await fn('menuImportApply', draft, tok)
        for nm, title, pin, em, ph in [('王小明', '外場', '1234', 'ming@example.com', '0912-345-678'), ('林小華', '內場', '2345', 'hua@example.com', '0922-111-222'), ('陳小美', '外場', '3456', '', '0933-444-555'), ('張阿強', '洗碗備料', '4567', '', '')]:
            await fn('stEmpSave', {'name': nm, 'title': title, 'pin': pin, 'email': em, 'phone': ph, 'hired': '2023-03-01'}, tok)
        wk = await ev("t => stWeekStart_(t)", today)
        rows = []
        for i in range(7):
            d = await ev("([t, n]) => stAdd_(t, n)", [wk, i])
            if i in (0, 1, 3, 4, 5, 6): rows += [{'d': d, 'e': 'E001', 'n': '早班', 's': '06:00', 't': '13:00'}]
            if i in (2, 3, 5, 6): rows += [{'d': d, 'e': 'E002', 'n': '早班', 's': '06:00', 't': '13:00'}]
            if i in (0, 1, 4, 5): rows += [{'d': d, 'e': 'E003', 'n': '晚班', 's': '13:00', 't': '20:00'}]
        await fn('stShiftSave', wk, rows, tok)
        tkA = (await fn('stEmpLogin', sid, 'E001', '1234'))['token']; tkB = (await fn('stEmpLogin', sid, 'E002', '2345'))['token']
        await at('06:04'); await fn('stPunch', tkA, ''); await at('06:22'); await fn('stPunch', tkB, '', '交通延誤'); await at('09:30')
        d3 = await ev("t => stAdd_(t, 3)", today)
        await fn('stLeaveSubmit', tkA, {'type': '事假', 'start': d3, 'end': d3, 'reason': '家裡有事'})
        await fn('stApplySubmit', sid, {'name': '李小弟', 'phone': '0955-666-777', 'email': 'lee@example.com', 'pos': '外場', 'when': '平日下午', 'intro': '有餐飲經驗一年'})
        await fn('stDocAdd', 'JVBERi0xLjQ=', '員工手冊.pdf', '員工手冊', '規章制度', '員工', tok)
        await fn('stDocAdd', 'JVBERi0xLjQ=', '過敏原說明.pdf', '過敏原說明', '菜單與價目', '公開', tok)
        v1 = (await fn('lgVendorSave', {'name': '阿財肉品', 'cat': '進貨：食材', 'pay': '月結', 'quick': '1200, 2500, 4000'}, tok))[0]['id']
        v2 = (await fn('lgVendorSave', {'name': '大成飲料行', 'cat': '進貨：飲料', 'pay': '轉帳', 'quick': '800, 1600'}, tok))[1]['id']
        await fn('lgVendorSave', {'name': '好鮮蔬菜', 'cat': '進貨：食材', 'pay': '現金', 'quick': '600, 900'}, tok)
        await fn('lgAdd', {'type': '支出', 'vendorId': v1, 'amount': 2500, 'pay': '月結', 'doc': '統一發票', 'invoice': 'AB12345678', 'items': '雞腿肉 20 斤、培根 5 包', 'buyer': '店主'}, tok)
        await fn('lgAdd', {'type': '支出', 'vendorId': v2, 'amount': 1600, 'pay': '轉帳', 'doc': '統一發票', 'invoice': 'CD87654321', 'items': '紅茶茶葉、紙杯', 'buyer': '王小明'}, tok)
        await fn('lgAdd', {'type': '支出', 'cat': '水電瓦斯', 'amount': 1830, 'pay': '轉帳', 'note': '10 月電費'}, tok)
        await fn('lgAdd', {'type': '收入', 'cat': '現場營業額', 'amount': 12800}, tok)
        await fn('tSaveNotice', {'title': '連假營業調整', 'start': today, 'end': await ev("t => stAdd_(t, 20)", today), 'show': True, 'content': {'cat': 'hours', 'lead': '連假期間 07:00 開門，歡迎光臨', 'tag': '公告'}}, tok)
        await fn('tSaveClosure', {'s': await ev("t => stAdd_(t, 9)", today), 'e': await ev("t => stAdd_(t, 9)", today), 'type': 'closed', 'reason': '店內設備保養', 'show': True}, tok)
        await fn('tAddHandover', {'who': '王小明', 'shift': '早班', 'types': ['備料'], 'text': '雞腿肉剩 2 包，下午請叫貨；冰箱門要記得關緊。', 'todo': True, 'prio': '急', 'to': '林小華'}, tok)
        await fn('tAddHandover', {'who': '王小明', 'shift': '早班', 'types': ['設備'], 'text': '外場桌面膠條要換新', 'todo': True, 'prio': '一般'}, tok)
        await fn('stDocAdd', 'JVBERi0xLjQ=', '開店流程.pdf', '開店流程', '工作守則', '員工', tok)
        await fn('stCfgSave', {'avail': {'on': True, 'mode': 'month', 'day': 25}}, tok)
        await fn('lgVendorSave', {'id': v1, 'name': '阿財肉品', 'cat': '進貨：食材', 'pay': '月結', 'quick': '1200, 2500, 4000', 'pin': True, 'orderDays': [1, 4], 'orderTime': '15:00', 'assignee': '林小華'}, tok)

        per = await ev("t => stAvailPeriod_(t, 'month').id", today)
        avtok = await ev("([e, p]) => stAvailToken_(stEmpById_(e), stPeriodById_(p))", ['E001', per])
        await fn('stAvailSubmit', avtok, [await ev("([p, n]) => stAdd_(stPeriodById_(p).from, n)", [per, 4]), await ev("([p, n]) => stAdd_(stPeriodById_(p).from, n)", [per, 5]), await ev("([p, n]) => stAdd_(stPeriodById_(p).from, n)", [per, 11])], '週末要考試')
        shots = []
        async def shot(name, params, setup=None, tall=None, full=True):
            await H.evaluate("p => openPage(p)", params); fr = H.child_frames[0]
            await fr.wait_for_function('window.__hlEnd === true', timeout=15000)
            await page.wait_for_timeout(500)
            if setup: await setup(fr)
            await page.wait_for_timeout(400)
            h = tall or await fr.evaluate("Math.min(2200, Math.max(document.documentElement.scrollHeight, document.body.scrollHeight))")
            h = max(700, min(int(h), 2200)) if full else 900
            await H.evaluate("h => { document.getElementById('f').style.height = h + 'px'; }", h)
            await page.wait_for_timeout(300)
            path = os.path.join(OUT, name + '.png')
            await page.locator('#f').screenshot(path=path)
            shots.append(name); print('  ✓', name)

        print('截圖中…')
        await shot('01-login', {})
        await shot('02-home', {'p': 'home', 't': tok})
        await shot('03-menu', {'t': tok, 'later': '1'}, tall=1500)
        await shot('04-tools-hand', {'p': 'tools', 't': tok, 'tab': 'hand'})
        await shot('05-tools-cal', {'p': 'tools', 't': tok, 'tab': 'cal'})
        await shot('06-tools-notice', {'p': 'tools', 't': tok, 'tab': 'notice'}, tall=1900)
        await shot('07-tools-table', {'p': 'tools', 't': tok, 'tab': 'table'})
        await shot('08-tools-wifi', {'p': 'tools', 't': tok, 'tab': 'wifi'}, tall=1500)
        await shot('09-tools-card', {'p': 'tools', 't': tok, 'tab': 'card'}, tall=2100)
        await shot('10-tools-logo', {'p': 'tools', 't': tok, 'tab': 'logo'})
        await shot('11-ledger', {'p': 'ledger', 't': tok})
        async def sheet(fr):
            await fr.click(f'#vTiles [data-v="{v1}"]'); await fr.wait_for_selector('#sheet:not(.hidden)')
            for k in '2500': await fr.click(f'#pad [data-k="{k}"]')
            await fr.fill('#inv', 'EF11223344'); await fr.fill('#items', '雞腿肉 20 斤、培根 5 包')
        await shot('12-ledger-sheet', {'p': 'ledger', 't': tok}, setup=sheet, tall=1500)
        async def rep(fr): await fr.click('#modes [data-m=report]')
        await shot('13-ledger-report', {'p': 'ledger', 't': tok}, setup=rep)
        async def vend(fr): await fr.click('#modes [data-m=vendors]')
        await shot('14-ledger-vendors', {'p': 'ledger', 't': tok}, setup=vend)
        async def emp(fr): await fr.click('#tabs [data-t=emp]')
        await shot('15-staff-emp', {'p': 'staff', 't': tok}, setup=emp)
        await shot('16-staff-plan', {'p': 'staff', 't': tok})
        async def punch(fr): await fr.click('#tabs [data-t=punch]'); await fr.click('#pGo'); await page.wait_for_timeout(600)
        await shot('17-staff-punch', {'p': 'staff', 't': tok}, setup=punch)
        async def leave(fr): await fr.click('#tabs [data-t=leave]'); await page.wait_for_timeout(600)
        await shot('18-staff-leave', {'p': 'staff', 't': tok}, setup=leave)
        async def hire(fr): await fr.click('#tabs [data-t=hire]'); await page.wait_for_timeout(600)
        await shot('19-staff-hire', {'p': 'staff', 't': tok}, setup=hire)
        async def docs(fr): await fr.click('#tabs [data-t=docs]')
        await shot('20-staff-docs', {'p': 'staff', 't': tok}, setup=docs)
        await shot('21-clock-login', {'s': sid, 'p': 'clock'}, full=False)
        async def clk(fr):
            await fr.fill('#emp', 'E001'); await fr.fill('#pin', '1234'); await fr.click('#go'); await fr.wait_for_selector('#home:not(.hidden)'); await page.wait_for_timeout(600)
        await shot('22-clock-home', {'s': sid, 'p': 'clock'}, setup=clk)
        await shot('23-join', {'s': sid, 'p': 'join', 'jc': (await fn('stEmpInviteForm', '新同事', '', '', tok))['url'].split('jc=')[1]})
        await shot('24-apply', {'s': sid, 'p': 'apply'})
        await shot('25-customer', {'s': sid})
        await shot('26-customer-menu', {'s': sid, 'p': 'menu'}, tall=1400)
        await shot('27-account', {'p': 'account', 't': tok})
        async def nf(fr):
            await fr.wait_for_selector('#nfBox:not([hidden])')
            await fr.uncheck('#nfBox [data-nf=wish]'); await fr.uncheck('#nfBox [data-nf=missEmp]')
            await fr.evaluate("window.scrollTo(0, document.getElementById('cNotify').closest('label').getBoundingClientRect().top + window.scrollY - 12)")
        await shot('33-notify', {'p': 'account', 't': tok}, setup=nf, full=False)
        await shot('28-setup', {'p': 'setup', 't': tok}, tall=1500)
        await shot('29-avail', {'s': sid, 'p': 'avail', 'jc': avtok}, tall=1400)
        async def sched(fr): await fr.evaluate("document.getElementById('avCard').scrollIntoView()")
        await shot('30-staff-avail', {'p': 'staff', 't': tok}, setup=sched, tall=2300)
        await shot('31-tools-rich', {'p': 'tools', 't': tok, 'tab': 'rich'}, tall=2200)
        await b.close()
    print('完成：', len(shots), '張，在 guide/shots/')

asyncio.run(main())
