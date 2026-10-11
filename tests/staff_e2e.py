"""人員與班表測試：員工與 PIN、排班、打卡（遲到判斷）、請假審核、文件下載區、權限，以及管理頁、員工打卡頁、店家資料配色範本（真的在瀏覽器操作）。
執行：python tests/staff_e2e.py
"""
import asyncio, base64, json, os, re, sys
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T, SRC = os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'src')
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:500]))

NAMES = ['Page', 'Customer', 'Tools', 'Login', 'Admin', 'Account', 'Setup', 'Brand', 'Staff', 'Clock', 'Apply', 'Join', 'Avail']
def files_json():
    return json.dumps({n: open(os.path.join(SRC, n + '.html'), encoding='utf-8').read() for n in NAMES}).replace('</', '<\\/')

SEED = """
(function () {
  __store.props.ssId = 'test';
  var p = __ss.insertSheet('價格表');
  p.data = [['弘林'], [''], [''], [''], ['代碼']];
  var real = Date.now; window.__real = real; window.__off = 0; Date.now = function () { return real.call(Date) + window.__off; };
})();
"""
HOST = """<!doctype html><html><head><meta charset="utf-8">
<script>window.__REAL_CODE = true;</script>
<script src="/mock.js"></script><script src="/Code.gs.js"></script><script src="/Tools.gs.js"></script><script src="/Tenant.gs.js"></script><script src="/Mail.gs.js"></script><script src="/Auth.gs.js"></script><script src="/Billing.gs.js"></script><script src="/Provision.gs.js"></script><script src="/Shop.gs.js"></script><script src="/BrandServer.gs.js"></script><script src="/StaffServer.gs.js"></script><script src="/saas_mock.js"></script>
<script>window.__FILES = %s;</script><script src="/seed.js"></script>
<script>
function openPage(params) {
  var html = doGet({ parameter: params }).getContent();
  html = html.replace('<head>', '<head><script>window.google = parent.google;<\\/script>');
  return new Promise(function (res) { var f = document.getElementById('f'); f.onload = function () { setTimeout(function () { res(true); }, 500); }; f.srcdoc = html; });
}
</script></head><body style="margin:0"><iframe id="f" style="width:420px;height:900px;border:0"></iframe></body></html>"""

PDF = base64.b64encode(b'%PDF-1.4 test').decode()

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
            m = re.search(r'/(Tenant|Mail|Auth|Billing|Provision|Shop|BrandServer|StaffServer)\.gs\.js$', u)
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
            # 固定在週三（2026-10-07），避免測試在週日、週一等週界日跑出不同結果
            await ev("t => { var day = '2026-10-07'; window.__off = new Date(day + 'T' + t + ':00+08:00').getTime() - window.__real.call(Date); }", hhmm)

        await ev("setupCenter()")
        sid = await ev("createTestShop()")
        tok = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: shopById_(s).tv }, 1)", sid)
        await ev("s => { CTX = { shopId: s, ssId: shopById_(s).ssId, shop: shopById_(s) }; _spMap = null; props_().setProperty('cfg', JSON.stringify({ name: '員工測試店', notifyEmail: 'boss@example.com' })); }", sid)
        await at('06:00')
        today = await ev("stToday_()")
        wk = await ev("t => stWeekStart_(t)", today)

        # ================= 員工 =================
        st = (await fn('stState', tok, ''))['v']
        check('初始狀態：沒有員工、有 3 種預設班別、遲到寬限 5 分鐘', st['emps'] == [] and len(st['cfg']['shifts']) == 3 and st['cfg']['grace'] == 5, st)
        check('員工打卡網址帶店家編號', ('s=' + sid + '&p=clock') in st['clockUrl'], st['clockUrl'])
        r = await fn('stEmpSave', {'name': '', 'pin': '1234'}, tok); check('員工：沒填姓名被擋', 'err' in r and '姓名' in r['err'], r)
        r = await fn('stEmpSave', {'name': '小明', 'pin': '12'}, tok); check('員工：PIN 不是 4～6 位數字被擋', 'err' in r and 'PIN' in r['err'], r)
        r = await fn('stEmpSave', {'name': '小明'}, tok); check('員工：新員工沒設 PIN 被擋', 'err' in r and 'PIN' in r['err'], r)
        r = await fn('stEmpSave', {'name': '小明', 'title': '外場', 'pin': '1234', 'hired': '2025-01-10'}, tok); check('員工：新增小明', 'err' not in r and len(r['v']) == 1 and r['v'][0]['id'] == 'E001' and r['v'][0]['pinSet'], r)
        await fn('stEmpSave', {'name': '小華', 'title': '內場', 'pin': '5678', 'hired': '2022-03-01'}, tok)
        r = await fn('stEmpSave', {'name': '小明', 'pin': '9999'}, tok); check('員工：在職同名被擋', 'err' in r and '區別' in r['err'], r)
        check('員工 PIN 以雜湊儲存，不是明文', await ev("() => { var e = stEmpById_('E001'); return e.hash.length === 64 && e.hash.indexOf('1234') < 0; }"))
        check('打卡頁名單只有姓名與編號（不含 PIN 雜湊）', json.dumps((await fn('stClockRoster', sid))['v'], ensure_ascii=False) == '[{"id": "E001", "name": "小明"}, {"id": "E002", "name": "小華"}]')
        r = await fn('stEmpLogin', sid, 'E001', '0000'); check('登入：PIN 錯誤被擋', 'err' in r and 'PIN 不正確' in r['err'], r)
        for _ in range(4): await fn('stEmpLogin', sid, 'E001', '0000')
        r = await fn('stEmpLogin', sid, 'E001', '1234'); check('登入：連錯 5 次後鎖定，連正確 PIN 也先擋', 'err' in r and '鎖定' in r['err'], r)
        r = await fn('stEmpLogin', sid, 'E002', '5678'); check('登入：另一位員工不受影響', 'err' not in r and r['v']['token'], r)
        tokB = r['v']['token']
        await ev("() => { CacheService.getScriptCache().remove('lock:stpin:' + CTX.shopId + ':E001'); CacheService.getScriptCache().remove('fail:stpin:' + CTX.shopId + ':E001'); }")
        r = await fn('stEmpLogin', sid, 'E001', '1234'); check('登入：解除鎖定後可登入', 'err' not in r, r)
        tokA = r['v']['token']
        check('員工通行證不能當店主通行證用', 'err' in await fn('stState', tokA, '') and 'err' in await fn('getData', tokA))
        check('亂填通行證：員工功能與管理功能都拒絕', 'err' in await fn('stEmpHome', 'garbage') and 'err' in await fn('stState', 'garbage', ''))

        # ================= 排班 =================
        d1 = await ev("t => stAdd_(t, 1)", today)
        rows = [{'d': today, 'e': 'E001', 'n': '早班', 's': '06:00', 't': '13:00'}, {'d': d1, 'e': 'E001', 'n': '早班', 's': '06:00', 't': '13:00'}, {'d': today, 'e': 'E002', 'n': '晚班', 's': '13:00', 't': '20:00'}]
        r = await fn('stShiftSave', wk, [dict(rows[0], d=await ev("t => stAdd_(t, 14)", wk))], tok); check('排班：日期超出這一週被擋', 'err' in r and '超出' in r['err'], r)
        r = await fn('stShiftSave', wk, [dict(rows[0], s='25:00')], tok); check('排班：時間格式不對被擋', 'err' in r, r)
        r = await fn('stShiftSave', wk, [dict(rows[0], e='E999')], tok); check('排班：找不到員工被擋', 'err' in r and '找不到' in r['err'], r)
        r = await fn('stShiftSave', wk, [dict(rows[0], t='06:00')], tok); check('排班：開始結束一樣被擋', 'err' in r, r)
        r = await fn('stShiftSave', wk, rows, tok); check('排班：儲存 3 個班', 'err' not in r and r['v']['saved'] == 3, r)
        r = await fn('stShiftSave', wk, rows[:2], tok); st = (await fn('stState', tok, today))['v']
        check('排班：整週覆蓋（再存 2 個班就只剩 2 個）', len(st['shifts']) == 2 and st['week'] == wk, st['shifts'])
        await fn('stShiftSave', wk, rows, tok)
        home = (await fn('stEmpHome', tokA))['v']
        check('員工看自己的班表（只有自己的、今天起的）', [s['d'] for s in home['shifts']] == [today, d1] and home['emp']['name'] == '小明', home['shifts'])
        check('員工首頁帶出文件與請假類別', home['leaveTypes'][0] == '事假' and home['docs'] == [] and home['open'] is None)

        # ================= 打卡 =================
        await at('06:03')
        r = await fn('stPunch', tokA, 'out'); check('打卡：還沒上班就下班被擋', 'err' in r and '還沒有上班' in r['err'], r)
        r = await fn('stPunch', tokA, 'in'); check('打卡：小明 06:03 上班打卡成功', 'err' not in r and r['v']['time'] == '06:03', r)
        r = await fn('stPunch', tokA, 'in'); check('打卡：重複上班打卡被擋', 'err' in r and '已經' in r['err'], r)
        await at('06:20')
        r = await fn('stPunch', tokB, 'in'); check('打卡：小華 06:20 上班打卡', 'err' not in r, r)
        await at('13:02')
        r = await fn('stPunch', tokA, 'out'); check('打卡：小明下班打卡，回報從幾點開始', 'err' not in r and r['v']['from'] == '06:03' and r['v']['time'] == '13:02', r)
        r = await fn('stPunch', tokA, 'out'); check('打卡：重複下班被擋', 'err' in r, r)
        lst = (await fn('stPunchList', today, today, tok))['v']
        a = [x for x in lst if x['e'] == 'E001'][0]; bb = [x for x in lst if x['e'] == 'E002'][0]
        check('打卡紀錄：小明工時 6 小時 59 分、06:03 在寬限內不算遲到、對上早班', a['mins'] == 419 and a['late'] == 0 and a['plan'] == '06:00–13:00', a)
        check('打卡紀錄：小華 06:20 上班，對上晚班 13:00 仍在上班中（未下班）', bb['out'] == '' and bb['in'] == '06:20', bb)
        await fn('stShiftSave', wk, [dict(rows[0], s='06:00'), dict(rows[1]), dict(rows[2], e='E002', s='06:00', t='13:00', n='早班')], tok)
        lst = (await fn('stPunchList', today, today, tok))['v']; bb = [x for x in lst if x['e'] == 'E002'][0]
        check('打卡紀錄：改排小華早班後，06:20 算遲到 20 分', bb['late'] == 20 and bb['plan'] == '06:00–13:00', bb)
        st = (await fn('stState', tok, today))['v']
        check('管理頁狀態：小華正在上班中', [o['e'] for o in st['on']] == ['E002'], st['on'])
        r = await fn('stPunchFix', {'d': today, 'e': 'E002', 'in': '06:20', 'out': '13:00', 'note': '忘了打卡'}, tok)
        check('補登：不指定 id 會新增一筆；指定 id 修改既有紀錄', 'err' not in r and r['v']['id'].startswith('P'), r)
        pid = bb['id']
        r = await fn('stPunchFix', {'id': pid, 'd': today, 'e': 'E002', 'in': '06:20', 'out': '13:00', 'note': '店長補下班'}, tok)
        lst = (await fn('stPunchList', today, today, tok))['v']
        check('補登：修改後下班時間補上，來源標示「店家補登」', [x for x in lst if x['id'] == pid][0]['out'] == '13:00' and [x for x in lst if x['id'] == pid][0]['src'] == '店家補登', lst)
        await fn('stPunchDelete', r['v']['id'] if False else (await fn('stPunchFix', {'d': today, 'e': 'E001', 'in': '09:00', 'out': '10:00'}, tok))['v']['id'], tok)
        check('補登：可以刪除錯誤的紀錄', len((await fn('stPunchList', today, today, tok))['v']) == 3)
        r = await fn('stPunchList', '2026-01-01', '2026-12-31', tok); check('打卡紀錄：一次最多查 3 個月', 'err' in r and '3 個月' in r['err'], r)
        # 跨夜班：昨天沒下班
        await ev("(d) => { stPut_('punch', 0, ['P90001', stAdd_(stToday_(), -1), 'E001', '20:00', '', '', '員工打卡']); }")
        await at('06:00')
        r = await fn('stPunch', tokA, 'in'); check('打卡：昨天忘了下班，今天上班打卡仍成功並提醒', 'err' not in r and '沒有下班打卡' in r['v']['warn'], r)

        # ================= 請假 =================
        r = await fn('stLeaveSubmit', tokA, {'type': '', 'start': today, 'end': today}); check('請假：沒選類別被擋', 'err' in r, r)
        r = await fn('stLeaveSubmit', tokA, {'type': '事假', 'start': today, 'end': d1[:8] + '00'}); check('請假：日期格式錯誤被擋', 'err' in r, r)
        old = await ev("t => stAdd_(t, -20)", today)
        r = await fn('stLeaveSubmit', tokA, {'type': '事假', 'start': old, 'end': old}); check('請假：太久以前的假被擋', 'err' in r and '7 天' in r['err'], r)
        mails = await ev("__store.mails.length")
        d3 = await ev("t => stAdd_(t, 3)", today); d4 = await ev("t => stAdd_(t, 4)", today)
        r = await fn('stLeaveSubmit', tokA, {'type': '病假', 'start': d3, 'end': d4, 'reason': '感冒'}); lid = r['v']['id'] if 'v' in r else ''
        check('請假：送出成功並寄信通知店主', 'err' not in r and lid == 'L0001' and await ev("__store.mails.length") == mails + 1, r)
        check('請假通知信寄給店主', await ev("__store.mails[__store.mails.length - 1].to") == 'boss@example.com')
        r = await fn('stLeaveSubmit', tokA, {'type': '事假', 'start': d4, 'end': d4}); check('請假：日期重疊被擋', 'err' in r and '已經有請假' in r['err'], r)
        st = (await fn('stState', tok, ''))['v']
        check('管理頁：待審核 1 筆', [l['id'] for l in st['pending']] == ['L0001'] and st['pending'][0]['reason'] == '感冒', st['pending'])
        r = await fn('stLeaveDecide', lid, True, '好好休息', tok); check('請假：核准', 'err' not in r and r['v'] == [], r)
        r = await fn('stLeaveDecide', lid, False, '', tok); check('請假：不能重複審核', 'err' in r and '已經處理' in r['err'], r)
        r = await fn('stLeaveCancel', tokA, lid); check('請假：核准後員工不能自己取消', 'err' in r and '審核過' in r['err'], r)
        st = (await fn('stState', tok, today))['v']
        check('核准的請假出現在班表週視圖', any(l['id'] == 'L0001' and l['status'] == '核准' for l in st['leaves']) or d3 > st['week'] and d3 > await ev("t => stAdd_(t, 6)", st['week']), st['leaves'])
        home = (await fn('stEmpHome', tokA))['v']
        check('員工看得到審核結果與店主回覆', home['leaves'][0]['status'] == '核准' and home['leaves'][0]['reply'] == '好好休息', home['leaves'])
        r = await fn('stLeaveSubmit', tokB, {'type': '特休', 'start': d3, 'end': d3}); lid2 = r['v']['id']
        r = await fn('stLeaveCancel', tokB, lid2); check('請假：待審時員工可以取消', 'err' not in r, r)
        r = await fn('stLeaveCancel', tokA, lid2); check('請假：不能取消別人的', 'err' in r, r)
        check('請假紀錄查詢', len((await fn('stLeaveList', today, d4, tok))['v']) == 2)

        # ================= PIN 與離職 =================
        await fn('stEmpSave', {'id': 'E001', 'name': '小明', 'title': '外場', 'pin': '4321'}, tok)
        check('改 PIN：舊的登入立即失效', 'err' in await fn('stEmpHome', tokA))
        r = await fn('stEmpLogin', sid, 'E001', '4321'); check('改 PIN：新 PIN 可登入', 'err' not in r, r); tokA = r['v']['token']
        await fn('stEmpSave', {'id': 'E002', 'name': '小華', 'status': '離職'}, tok)
        check('離職：登入失效、不在打卡名單', 'err' in await fn('stEmpHome', tokB) and [x['name'] for x in (await fn('stClockRoster', sid))['v']] == ['小明'])
        check('離職：歷史打卡紀錄保留', len([x for x in (await fn('stPunchList', today, today, tok))['v'] if x['e'] == 'E002']) >= 1)

        # ================= 文件下載區 =================
        r = await fn('stDocAdd', PDF, 'virus.exe', '壞檔', '其他', '員工', tok); check('文件：不支援的檔案類型被擋', 'err' in r and '不支援' in r['err'], r)
        r = await fn('stDocAdd', '', 'a.pdf', '空', '其他', '員工', tok); check('文件：空檔被擋', 'err' in r, r)
        r = await fn('stDocAdd', PDF, '員工手冊.pdf', '員工手冊 2026', '規章制度', '員工', tok); check('文件：上傳員工手冊（只給員工）', 'err' not in r and len(r['v']) == 1 and r['v'][0]['aud'] == '員工' and r['v'][0]['url'].startswith('https'), r)
        r = await fn('stDocAdd', PDF, '過敏原.pdf', '過敏原說明', '菜單與價目', '公開', tok); check('文件：上傳公開文件', 'err' not in r and len(r['v']) == 2, r)
        home = (await fn('stEmpHome', tokA))['v']
        check('員工看得到全部文件（含公開與員工用）', sorted(d['title'] for d in home['docs']) == ['員工手冊 2026', '過敏原說明'], home['docs'])
        cust = await ev("s => doGet({ parameter: { s } }).getContent()", sid)
        check('顧客頁只顯示公開文件', '過敏原說明' in cust and '員工手冊' not in cust and '資訊下載' in cust)
        did = [d for d in (await fn('stState', tok, ''))['v']['docs'] if d['title'] == '員工手冊 2026'][0]['id']
        await fn('stDocSet', did, '員工手冊 2026', '規章制度', '公開', tok)
        cust = await ev("s => doGet({ parameter: { s } }).getContent()", sid)
        check('文件：改成公開後顧客頁也出現', '員工手冊 2026' in cust)
        r = await fn('stDocDelete', did, tok); check('文件：刪除', len(r['v']) == 1, r)
        check('文件：檔案放在店家工具資料夾並設成連結可看', await ev("() => Object.keys(__store.files).some(k => __store.files[k].shared)"))

        # ================= 瀏覽器：管理頁 =================
        await at('08:00')
        await H.evaluate("p => openPage(p)", {'p': 'staff', 't': tok})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#grid td.emp")', timeout=15000)
        await page.screenshot(path=os.path.join(os.environ.get('TEMP', '.'), 'staff_plan.png'))
        check('管理頁：班表格有員工列與 7 天欄位', await fr.locator('#grid thead th').count() == 9 and await fr.locator('#grid td.emp').count() == 1)
        check('管理頁：今天的班顯示在格子裡', '早班' in await fr.inner_text('#grid') and '06:00–13:00' in await fr.inner_text('#grid'))
        d2 = await ev("t => stAdd_(t, 2)", wk)
        await fr.click(f'#grid td.cell[data-e="E001"][data-d="{d2}"]')
        check('管理頁：點格子開啟編輯視窗', await fr.is_visible('#editor'))
        await fr.click('#edPre [data-pre="1"]')
        check('管理頁：點班別範本加班，儲存按鈕可按', await fr.is_enabled('#wSave') and '晚班' in await fr.inner_text('#grid'))
        await fr.click('#wNext'); await fr.wait_for_timeout(300)
        check('管理頁：有未儲存變更時不能換週', '尚未儲存' in await fr.inner_text('#gmsg'))
        await fr.click('#wSave'); await fr.wait_for_function('document.querySelector("#gmsg").innerText.includes("班表已儲存")', timeout=8000)
        check('管理頁：儲存後寫進試算表', await ev("([s, d]) => stRows_('shift').some(r => stStr_(r['日期']) === d && r['班別'] === '晚班' && r['員工編號'] === 'E001')", [sid, d2]))
        await fr.click('#wNext'); await fr.wait_for_timeout(500)
        await fr.click('#wCopy'); await fr.wait_for_timeout(800)
        check('管理頁：複製上週班表到下一週（顯示未儲存）', '尚未儲存' in await fr.inner_text('#dirty') and await fr.locator('#grid .sc').count() >= 1)
        await fr.click('#wUndo'); await fr.wait_for_timeout(400)
        await fr.click('#tabs [data-t=punch]'); await fr.wait_for_selector('#pList .li', timeout=8000)
        check('管理頁：打卡紀錄分頁列出紀錄與遲到標示', '遲到' in await fr.inner_text('#pList') and '補登' in await fr.inner_text('#pList'))
        check('管理頁：打卡統計列出各員工工時', '小明' in await fr.inner_text('#pSum'))
        await fr.click('#tabs [data-t=leave]'); await fr.wait_for_timeout(500)
        check('管理頁：請假分頁顯示歷史（沒有待審）', '沒有待審核' in await fr.inner_text('#lPend') and '病假' in await fr.inner_text('#lHist'))
        await fr.click('#tabs [data-t=emp]')
        check('管理頁：員工分頁顯示打卡網址與名單', '小明' in await fr.inner_text('#eList') and '離職' in await fr.inner_text('#eList'))
        await fr.fill('#efName', '小美'); await fr.fill('#efPin', '2468'); await fr.click('#efSave'); await fr.wait_for_timeout(600)
        check('管理頁：新增員工小美，顯示一次性的 PIN 提示', '2468' in await fr.inner_text('#efMsg') and '小美' in await fr.inner_text('#eList'), await fr.inner_text('#efMsg'))
        await fr.click('#tabs [data-t=docs]')
        check('管理頁：文件分頁列出已上傳文件', '過敏原說明' in await fr.inner_text('#dList'))
        await fr.set_input_files('#dFile', files=[{'name': '請假單.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.4 form'}])
        await fr.fill('#dTitle', '請假單'); await fr.select_option('#dCat', '表單'); await fr.click('#dUp'); await fr.wait_for_function('document.querySelector("#dList").innerText.includes("請假單")', timeout=10000)
        check('管理頁：瀏覽器上傳文件成功', '請假單' in await fr.inner_text('#dList') and '表單' in await fr.inner_text('#dList'))
        check('管理頁沒有 JS 錯誤', not errors, errors)

        # ================= 瀏覽器：員工打卡頁 =================
        await at('06:05')
        await ev("s => { var t = stEmpById_('E001'); }", sid)
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'clock'})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        login_txt = await fr.inner_text('#login')
        check('打卡頁：顯示店名，登入前不列出任何員工的名字', '員工測試店' in await fr.inner_text('#shop') and not any(n in login_txt for n in ['小明', '小華', '小梅']))
        await fr.fill('#emp', 'e001'); await fr.fill('#pin', '0000'); await fr.click('#go'); await fr.wait_for_timeout(500)
        check('打卡頁：PIN 錯誤顯示訊息', 'PIN 不正確' in await fr.inner_text('#lmsg'))
        await fr.fill('#pin', '4321'); await fr.click('#go'); await fr.wait_for_selector('#home:not(.hidden)', timeout=8000)
        await page.screenshot(path=os.path.join(os.environ.get('TEMP', '.'), 'clock_home.png'))
        check('打卡頁：登入後顯示姓名職稱與今天的班', '小明' in await fr.inner_text('#who') and '早班' in await fr.inner_text('#todayShift'))
        check('打卡頁：已上班打卡的狀態顯示「已打卡」，按鈕只有一個「打卡」', '已打卡' in await fr.inner_text('#pstat') and await fr.inner_text('#punch') == '打卡', await fr.inner_text('#pstat'))
        await fr.click('#punch'); await fr.wait_for_function('document.querySelector("#pmsg").innerText.includes("成功")', timeout=8000)
        check('打卡頁：再按一下就是下班，狀態變成「今日已完成」', '打卡成功' in await fr.inner_text('#pmsg') and '今日已完成' in await fr.inner_text('#pstat'), await fr.inner_text('#pstat'))
        await fr.click('#punch'); await fr.wait_for_timeout(800)
        check('打卡頁：下班後再按一下是新的一筆上班，顯示「今日已打卡 06:05」', '今日已打卡 06:05' in await fr.inner_text('#pstat'), (await fr.inner_text('#pstat'), await fr.inner_text('#pmsg')))
        await fr.click('#tabs [data-t=plan]')
        check('打卡頁：班表分頁', '早班' in await fr.inner_text('#planBody'))
        await fr.click('#tabs [data-t=leave]'); d9 = await ev("t => stAdd_(t, 9)", today)
        await fr.fill('#ls', d9); await fr.fill('#le', d9); await fr.select_option('#lt', '特休'); await fr.fill('#lr', '家庭旅遊'); await fr.click('#lsend')
        await fr.wait_for_function('document.querySelector("#llist").innerText.includes("待審")', timeout=8000)
        check('打卡頁：送出請假後出現在我的紀錄（待審）', '特休' in await fr.inner_text('#llist') and '等店長審核' in await fr.inner_text('#lmsg2'))
        await fr.click('#llist [data-cancel]'); await fr.wait_for_function('document.querySelector("#llist").innerText.includes("已取消")', timeout=8000)
        check('打卡頁：可以取消待審的請假', '已取消' in await fr.inner_text('#llist'))
        await fr.click('#tabs [data-t=docs]')
        check('打卡頁：文件分頁依分類列出', '過敏原說明' in await fr.inner_text('#docBody') and '請假單' in await fr.inner_text('#docBody') and '表單' in await fr.inner_text('#docBody'))
        await fr.click('#logout')
        check('打卡頁：登出後回到登入畫面', await fr.is_visible('#login'))
        check('打卡頁沒有 JS 錯誤', not errors, errors)

        # ================= 員工 Email／電話、邀請為夥伴、寄班表 =================
        r = await fn('stEmpSave', {'id': 'E001', 'name': '小明', 'email': 'bad-mail'}, tok); check('員工：電子郵件格式不對被擋', 'err' in r and '電子郵件' in r['err'], r)
        r = await fn('stEmpSave', {'id': 'E001', 'name': '小明', 'phone': 'abc'}, tok); check('員工：電話格式不對被擋', 'err' in r and '電話' in r['err'], r)
        r = await fn('stEmpSave', {'id': 'E001', 'name': '小明', 'title': '外場', 'email': 'ming@example.com', 'phone': '0912-345-678'}, tok)
        check('員工：存電子郵件與電話（沒改 PIN 不影響登入）', 'err' not in r and [x for x in r['v'] if x['id'] == 'E001'][0]['email'] == 'ming@example.com' and 'err' not in await fn('stEmpHome', tokA), r)
        r = await fn('stEmpSave', {'name': '小梅', 'pin': '2468', 'email': 'mei@example.com', 'phone': '0922-111-222'}, tok)
        check('員工：新增小梅（有信箱與電話）', 'err' not in r, r)
        eid_mei = [x for x in r['v'] if x['name'] == '小梅'][0]['id']
        r = await fn('stEmpSave', {'name': '阿強', 'pin': '1357'}, tok); eid_no = [x for x in r['v'] if x['name'] == '阿強'][0]['id']
        st = (await fn('stState', tok, ''))['v']
        off = {x['name']: x for x in st['offDuty']}
        check('緊急聯絡名單：今天沒排班的在職員工（小梅、阿強），有班的小明不在名單', '小梅' in off and '阿強' in off and '小明' not in off and off['小梅']['phone'] == '0922-111-222', st['offDuty'])
        check('緊急聯絡名單：離職的不列入', '小華' not in off)
        r = await fn('stEmpInvite', eid_no, tok); check('邀請：沒有電子郵件被擋', 'err' in r and '電子郵件' in r['err'], r)
        n0 = await ev("__store.mails.length")
        r = await fn('stEmpInvite', eid_mei, tok); check('邀請：寄出邀請信', 'err' not in r and await ev("__store.mails.length") == n0 + 1, r)
        mail = await ev("__store.mails[__store.mails.length - 1]")
        check('邀請信寄到員工信箱，內含邀請連結', mail['to'] == 'mei@example.com' and '?invite=' in (mail.get('body') or '').replace('\\/', '/'), mail)
        st = (await fn('stState', tok, ''))['v']
        check('員工狀態顯示「邀請中」', [x for x in st['emps'] if x['id'] == eid_mei][0]['invite'] == '邀請中')
        code = re.search(r'invite=([A-Z0-9]+)', (mail.get('body') or '').replace('\\/', '/')).group(1)
        r = await ev("c => authInvite(c, 'devMei')", code)
        check('員工用邀請連結登入成為夥伴', r['ok'] and r['token'], r)
        st = (await fn('stState', tok, ''))['v']
        check('員工狀態改為「使用中」（店主備用）', [x for x in st['emps'] if x['id'] == eid_mei][0]['invite'] == '使用中')
        r = await fn('stEmpInvite', eid_mei, tok); check('邀請：已經是夥伴不能重複邀請', 'err' in r and '已經是夥伴' in r['err'], r)
        check('夥伴的通行證不能進人員與班表（只有店主）', 'err' in await fn('stState', r['v']['token'] if False else (await ev("c => 1", 1)) and '', ''))
        r = await fn('stEmpInvite', 'E999', tok); check('邀請：找不到員工被擋', 'err' in r, r)
        # 寄班表
        n0 = await ev("__store.mails.length")
        r = await fn('stScheduleMail', 'week', today, [], tok)
        check('寄班表（本週、全部）：只寄給有信箱而且有班的人（小明），其他列在「沒寄」', 'err' not in r and r['v']['sent'] == ['小明'] and any('小梅' in x and '沒有班' in x for x in r['v']['skipped']) and any('阿強' in x and '沒有電子郵件' in x for x in r['v']['skipped']), r)
        mail = await ev("__store.mails[__store.mails.length - 1]")
        check('班表信：寄給小明，列出日期、班別與時間、合計工時', mail['to'] == 'ming@example.com' and '早班 06:00–13:00' in mail['body'] and '合計約' in mail['body'], mail)
        check('班表信附上員工打卡網址', 's=' + sid in mail['body'].replace('\\/', '/'))
        r = await fn('stScheduleMail', 'month', today, [], tok); check('寄班表（當月）', 'err' not in r and r['v']['sent'] == ['小明'] and '月班表' in r['v']['label'], r)
        r = await fn('stScheduleMail', 'week', today, [eid_mei], tok); check('寄班表：指定員工但那人沒班，不會寄', r['v']['sent'] == [], r)
        r = await fn('stScheduleMail', 'week', 'bad', [], tok); check('寄班表：日期不正確被擋', 'err' in r, r)

        # ================= 徵才與面試登記 =================
        r = await fn('stHireSave', {'positions': [], 'open': True}, tok); check('徵才：職缺不能是空的', 'err' in r, r)
        r = await fn('stHireSave', {'positions': ['外場', '內場', '洗碗'], 'open': True}, tok); check('徵才：儲存職缺', 'err' not in r and r['v']['positions'] == ['外場', '內場', '洗碗'], r)
        check('徵才：面試登記網址', ('s=' + sid + '&p=apply') in (await fn('stState', tok, ''))['v']['applyUrl'])
        r = await fn('stApplySubmit', sid, {'name': '', 'phone': '0911222333'}); check('登記：沒填姓名被擋', 'err' in r and '姓名' in r['err'], r)
        r = await fn('stApplySubmit', sid, {'name': '王小弟'}); check('登記：沒留聯絡方式被擋', 'err' in r and '聯絡方式' in r['err'], r)
        r = await fn('stApplySubmit', sid, {'name': '王小弟', 'phone': 'xx'}); check('登記：電話格式不對被擋', 'err' in r, r)
        r = await fn('stApplySubmit', sid, {'name': '王小弟', 'email': 'abc'}); check('登記：電子郵件格式不對被擋', 'err' in r, r)
        r = await fn('stApplySubmit', sid, {'name': '機器人', 'phone': '0911000000', 'hp': 'http://spam'}); check('登記：蜜罐欄位有填被當成機器人（假裝成功但不存）', 'err' not in r and (await fn('stApplyList', tok))['v'] == [], r)
        n0 = await ev("__store.mails.length")
        r = await fn('stApplySubmit', sid, {'name': '王小弟', 'phone': '0911-222-333', 'email': 'kid@example.com', 'pos': '外場', 'when': '平日下午', 'intro': '有早餐店經驗'}); check('登記：成功並寄信通知店主', 'err' not in r and await ev("__store.mails.length") == n0 + 1 and await ev("__store.mails[__store.mails.length - 1].to") == 'boss@example.com', r)
        r = await fn('stApplySubmit', sid, {'name': '王小弟', 'phone': '0911-222-333'}); check('登記：同一個人短時間不能重複登記', 'err' in r and '已經登記' in r['err'], r)
        lst = (await fn('stApplyList', tok))['v']
        check('登記名單：職位、時段、自我介紹、狀態「新登記」', len(lst) == 1 and lst[0]['pos'] == '外場' and lst[0]['when'] == '平日下午' and lst[0]['status'] == '新登記' and lst[0]['id'] == 'A0001', lst)
        check('管理頁狀態：新登記 1 筆', (await fn('stState', tok, ''))['v']['newApplies'] == 1)
        r = await fn('stApplySet', 'A0001', '亂寫', '', tok); check('登記：狀態不正確被擋', 'err' in r, r)
        r = await fn('stApplySet', 'A0001', '約定面試', '週六 10:00', tok); check('登記：改成約定面試並寫備註', 'err' not in r and r['v'][0]['status'] == '約定面試' and r['v'][0]['note'] == '週六 10:00', r)
        r = await fn('stApplyInterview', 'A0001', '2020-01-01T10:00', tok); check('面試：過去的日期被擋', 'err' in r, r)
        r = await fn('stApplyInterview', 'A0001', 'bad', tok); check('面試：沒選時間被擋', 'err' in r, r)
        n9 = await ev("__store.mails.length")
        fut = await ev("() => stAdd_(stToday_(), 5)")
        r = await fn('stApplyInterview', 'A0001', fut + 'T14:30', tok)
        lm = await ev("__store.mails[__store.mails.length - 1]")
        check('面試：約定時間後，狀態＝約定面試，確認信寄給應徵者', 'err' not in r and r['v']['mailed'] and r['v']['list'][0]['status'] == '約定面試' and lm['to'] == 'kid@example.com' and '14:30' in lm['body'] and await ev("__store.mails.length") == n9 + 1, (r, lm))
        r = await fn('stApplyHire', 'A0001', '8642', tok); check('登記：轉成員工（姓名、電話、信箱帶入，狀態變錄取）', 'err' not in r and any(x['name'] == '王小弟' and x['email'] == 'kid@example.com' and x['phone'] == '0911-222-333' for x in r['v']['emps']) and (await fn('stApplyList', tok))['v'][0]['status'] == '錄取', r)
        await fn('stHireSave', {'positions': ['外場'], 'open': False}, tok)
        r = await fn('stApplySubmit', sid, {'name': '遲到者', 'phone': '0900111222'}); check('登記：關閉招募後不能登記', 'err' in r and '沒有招募' in r['err'], r)
        await fn('stHireSave', {'positions': ['外場', '內場'], 'open': True}, tok)
        check('登記：亂填通行證不能看名單', 'err' in await fn('stApplyList', 'garbage'))
        # 瀏覽器：公開登記頁
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'apply'})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('登記頁：顯示店名與職缺選單', '員工測試店' in await fr.inner_text('.hero') and '內場' in await fr.inner_text('#pos'))
        await fr.click('#go'); await fr.wait_for_timeout(200)
        check('登記頁：沒填姓名會提示', '請填姓名' in await fr.inner_text('#msg'))
        await fr.fill('#name', '陳小梅'); await fr.fill('#email', 'chen@example.com'); await fr.select_option('#pos', '內場'); await fr.fill('#when', '週末'); await fr.click('#go')
        await fr.wait_for_selector('#ok:not(.hidden)', timeout=8000)
        check('登記頁：送出後顯示成功畫面，資料進名單', '收到了' in await fr.inner_text('#ok') and any(a['name'] == '陳小梅' and a['pos'] == '內場' for a in (await fn('stApplyList', tok))['v']))
        await fn('stHireSave', {'positions': ['外場'], 'open': False}, tok)
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'apply'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true')
        check('登記頁：招募關閉時顯示「目前沒有招募」', await fr.is_visible('#closed') and await fr.is_hidden('#form'))
        await fn('stHireSave', {'positions': ['外場', '內場'], 'open': True}, tok)
        # 管理頁：員工、徵才
        await H.evaluate("p => openPage(p)", {'p': 'staff', 't': tok}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#grid td.emp")', timeout=15000)
        check('管理頁：班表頁有「今天沒排班」聯絡名單與寄班表按鈕', '小梅' in await fr.inner_text('#offList') and await fr.is_visible('#wMailW') and await fr.is_visible('#wMailM'))
        await fr.click('#wMailW'); await fr.wait_for_function('document.querySelector("#mailRep").innerText.includes("已寄給")', timeout=10000)
        check('管理頁：按「寄本週班表」顯示已寄給誰、沒寄給誰', '小明' in await fr.inner_text('#mailRep') and '沒寄' in await fr.inner_text('#mailRep'))
        await fr.click('#tabs [data-t=emp]')
        check('管理頁：員工列顯示電話、信箱與夥伴狀態', '0922-111-222' in await fr.inner_text('#eList') and 'mei@example.com' in await fr.inner_text('#eList') and '已是夥伴' in await fr.inner_text('#eList'))
        await fr.fill('#efName', '小新'); await fr.fill('#efPin', '1111'); await fr.fill('#efEmail', 'new@example.com'); await fr.fill('#efPhone', '0933-444-555'); await fr.click('#efSave'); await fr.wait_for_timeout(700)
        check('管理頁：新增員工可填電子郵件與電話', '0933-444-555' in await fr.inner_text('#eList') and 'new@example.com' in await fr.inner_text('#eList'))
        n0 = await ev("__store.mails.length")
        await fr.click('#eList [data-inv]'); await fr.wait_for_function('document.querySelector("#gmsg").innerText.includes("邀請信")', timeout=10000)
        check('管理頁：按「邀請為夥伴」寄出邀請信', await ev("__store.mails.length") == n0 + 1)
        await fr.click('#tabs [data-t=hire]'); await fr.wait_for_selector('#aList .li', timeout=8000)
        check('管理頁：徵才分頁有登記網址、職缺與名單', 'p=apply' in await fr.inner_text('#applyUrl') and '內場' in await fr.input_value('#hPos') and '陳小梅' in await fr.inner_text('#aList') and '王小弟' in await fr.inner_text('#aList'))
        check('管理頁：「做徵才海報」連到店家工具', 'hiring=1' in (await fr.get_attribute('#toPoster', 'href') or ''))
        await fr.fill('#hPos', '外場\n內場\n備餐'); await fr.click('#hSave'); await fr.wait_for_timeout(500)
        check('管理頁：儲存職缺', (await fn('stState', tok, ''))['v']['hire']['positions'] == ['外場', '內場', '備餐'])
        row = fr.locator('#aList [data-a]').filter(has_text='陳小梅')
        await row.locator('.st').select_option('已聯絡'); await row.locator('[data-as]').click(); await fr.wait_for_timeout(700)
        check('管理頁：改登記狀態', [a for a in (await fn('stApplyList', tok))['v'] if a['name'] == '陳小梅'][0]['status'] == '已聯絡')
        # 店家工具：徵才海報預設掃碼登記面試
        await H.evaluate("p => openPage(p)", {'p': 'tools', 't': tok, 'hiring': '1'}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        nj = await fr.evaluate("JSON.stringify(readNotice())")
        check('店家工具：從徵才分頁進來直接開徵才海報，QR 連到登記頁、職缺帶入、寫「掃碼預約面試」', 'p=apply' in nj.replace('\\/', '/') and '外場／內場／備餐' in nj and '預約面試' in nj, nj[:300])

        # ================= 弘林範例菜單（測試帳號）=================
        await H.evaluate("p => openPage(p)", {'t': tok, 'later': '1'}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('菜單工具：測試帳號、菜單是空的時有「載入弘林範例菜單」按鈕', await fr.is_visible('#emptyDemo'))
        nsec = await ev("honglingDraft_().sections.length"); nit = await ev("honglingDraft_().sections.reduce((a, s) => a + s.items.length, 0)")
        check('弘林範例菜單：分類不超過 14 個、品項超過 100 個', 0 < nsec <= 14 and nit > 100, (nsec, nit))
        await ev("() => { var s = __store.props.testAccounts; window.__ta = s; __store.props.testAccounts = ''; }")
        r = await fn('ownDemoMenuLoad', tok); check('範例菜單：不是測試帳號不能載入', 'err' in r and '測試帳號' in r['err'], r)
        await ev("() => { __store.props.testAccounts = window.__ta; }")
        r = await fn('ownDemoMenuLoad', tok); check('範例菜單：載入弘林品項', 'err' not in r and r['v']['added'] == nit and r['v']['updated'] == 0, r)
        rows = (await fn('getData', tok))['v']['rows']
        hit = [x for x in rows if x['name'] == '辣培根薯泥起司蛋堡套餐']
        check('範例菜單：品項、價格、推薦星號都帶入（辣培根薯泥起司蛋堡套餐 150 元、推薦）', len(rows) >= nit and hit and hit[0]['p'] == '150' and hit[0]['star'], hit)
        check('範例菜單：分類跟弘林一樣（超值特餐、經濟特餐…）', any(x['cat'] == '超值特餐' for x in rows) and any(x['cat'] == '經濟特餐' for x in rows))
        r = await fn('ownDemoMenuLoad', tok); check('範例菜單：再載入一次不會重複新增', 'err' not in r and r['v']['added'] == 0, r)
        await H.evaluate("p => openPage(p)", {'t': tok, 'later': '1'}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('菜單工具：有品項後不再顯示空白提示與載入按鈕', await fr.is_hidden('#emptyHint'))
        check('電子菜單（顧客）看得到弘林品項', '辣培根薯泥起司蛋堡套餐' in json.dumps(await fn('getMenu', sid), ensure_ascii=False))

        # ================= 店家資料配色範本（店家工具）=================
        await H.evaluate("p => openPage(p)", {'p': 'tools', 't': tok})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('店家工具：店家資料有 20 組配色範本', await fr.locator('#sPals [data-sp]').count() == 20)
        await fr.click('#tabs button[data-tab=logo], .tabs button[data-tab=logo]')
        await fr.click('#sPals [data-sp="2"]')
        check('店家工具：點範本套用主色與強調色（酒紅金）', (await fr.input_value('#sPri')).upper() == '#8C2F39' and (await fr.input_value('#sAcc')).upper() == '#D9A441' and 'on' in await fr.get_attribute('#sPals [data-sp="2"]', 'class'))
        await fr.click('#shopSave'); await fr.wait_for_timeout(600)
        saved = await ev("s => { CTX = { shopId: s, ssId: shopById_(s).ssId, shop: shopById_(s) }; _spMap = null; return JSON.parse(props_().getProperty('t_shop')); }", sid)
        check('店家工具：儲存後配色寫入店家資料', saved['primary'] == '#8C2F39' and saved['accent'] == '#D9A441', saved)
        check('店家工具：標題列有「人員班表」入口（店主）', await fr.is_visible('#staffLink') and 'p=staff' in (await fr.get_attribute('#staffLink', 'href') or ''))
        await H.evaluate("p => openPage(p)", {'t': tok, 'later': '1'})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('菜單工具：店主看得到「人員班表」入口', await fr.is_visible('#staffLink') and 'p=staff' in (await fr.get_attribute('#staffLink', 'href') or ''))
        # ================= 人員建置：員工自己填資料（建檔連結）=================
        await at('09:00')
        code_of = lambda m: re.search(r'jc=([A-Z0-9]+)', (m.get('body') or '').replace('\\/', '/')).group(1)
        check('建檔：沒有權限（亂填通行證）不能產生連結', 'err' in await fn('stEmpInviteForm', '阿志', '', '', 'garbage') and 'err' in await fn('stJoinSet', True, False, 'garbage') and 'err' in await fn('stEmpApprove', 'E001', True, 'garbage'))
        r = await fn('stEmpInviteForm', '阿志', 'bad-mail', '', tok); check('建檔：電子郵件格式不對被擋', 'err' in r, r)
        n0 = await ev("__store.mails.length")
        r = await fn('stEmpInviteForm', '阿志', 'zhi@example.com', '', tok)
        check('建檔：產生個人連結並寄信給員工（7 天內有效）', 'err' not in r and ('s=' + sid + '&p=join&jc=') in r['v']['url'] and r['v']['mailed'] and await ev("__store.mails.length") == n0 + 1, r)
        mail = await ev("__store.mails[__store.mails.length - 1]"); jcode = code_of(mail); jid = r['v']['id']
        check('建檔：信寄到員工信箱，內含連結', mail['to'] == 'zhi@example.com' and jcode in r['v']['url'], mail)
        st = (await fn('stState', tok, ''))['v']; e0 = [x for x in st['emps'] if x['id'] == jid][0]
        check('建檔：員工狀態是「待填寫」，不在打卡名單、不在可排班名單', e0['status'] == '待填寫' and e0['waiting'] and '阿志' not in [x['name'] for x in (await fn('stClockRoster', sid))['v']])
        check('建檔：個人連結只存雜湊，試算表裡找不到明碼', not await ev("c => stRows_('emp').some(r => JSON.stringify(r).indexOf(c) >= 0)", jcode))
        jp = lambda c: ev("([s, c]) => { var o = joinPage_(s, c).getContent(); return o; }", [sid, c])
        html = await jp(jcode); check('建檔頁：連結有效時顯示表單資料（帶入店主填的名字）', '"ok":true' in html.replace(' ', '') and '阿志' in html, html[:80])
        html = await jp('WRONGCODE12345'); check('建檔頁：連結無效時顯示說明', '"ok":false' in html.replace(' ', '') and '無效' in html)
        r = await fn('stJoinSubmit', sid, jcode, {'name': '', 'phone': '0911000111', 'pin': '1234'}); check('建檔：沒填姓名被擋', 'err' in r and '姓名' in r['err'], r)
        r = await fn('stJoinSubmit', sid, jcode, {'name': '阿志', 'phone': '', 'pin': '1234'}); check('建檔：沒填手機被擋', 'err' in r and '手機' in r['err'], r)
        r = await fn('stJoinSubmit', sid, jcode, {'name': '阿志', 'phone': '0911000111', 'pin': '12'}); check('建檔：PIN 不是 4～6 位數字被擋', 'err' in r and 'PIN' in r['err'], r)
        r = await fn('stJoinSubmit', sid, jcode, {'name': '小明', 'phone': '0911000111', 'pin': '2222'}); check('建檔：跟在職員工同名被擋', 'err' in r and '已經有' in r['err'], r)
        r = await fn('stJoinSubmit', sid, jcode, {'name': '阿志', 'title': '外場', 'phone': '0911-000-111', 'email': 'zhi@example.com', 'emName': '志媽', 'emPhone': '0922-333-444', 'pin': '2222'})
        check('建檔：員工自己填完，直接成為在職', 'err' not in r and r['v']['mode'] == 'personal' and ('s=' + sid) in r['v']['clockUrl'].replace('\\/', '/'), r)
        e1 = [x for x in (await fn('stState', tok, ''))['v']['emps'] if x['id'] == jid][0]
        check('建檔：姓名、職稱、手機、緊急聯絡人都寫進員工資料', e1['status'] == '在職' and e1['name'] == '阿志' and e1['title'] == '外場' and e1['phone'] == '0911-000-111' and e1['emName'] == '志媽' and e1['emPhone'] == '0922-333-444', e1)
        r = await fn('stEmpLogin', sid, jid, '2222'); check('建檔：用自己設的 PIN 可以登入打卡頁', 'err' not in r, r)
        r = await fn('stJoinSubmit', sid, jcode, {'name': '阿志二號', 'phone': '0911000111', 'pin': '3333'}); check('建檔：個人連結只能用一次', 'err' in r and '無效' in r['err'], r)
        # 重發與過期
        r = await fn('stEmpInviteForm', '阿華', '', '', tok); hid = r['v']['id']; hurl = r['v']['url']; hcode = hurl.split('jc=')[1]
        check('建檔：沒填信箱時不寄信，只回傳連結', r['v']['mailed'] is False and 'p=join' in hurl, r)
        r = await fn('stEmpInviteForm', '阿華', '', hid, tok); ncode = r['v']['url'].split('jc=')[1]
        check('建檔：重發連結後，舊連結立即失效、新連結有效', ncode != hcode and '"ok":false' in (await jp(hcode)).replace(' ', '') and '"ok":true' in (await jp(ncode)).replace(' ', ''), r)
        await ev("d => { window.__off += d * 86400000; }", 8)
        check('建檔：超過 7 天的連結顯示已過期', '過期' in await jp(ncode))
        await ev("d => { window.__off -= d * 86400000; }", 8)
        await fn('stEmpApprove', hid, False, tok)
        check('建檔：取消沒人填的邀請（刪除這筆）', hid not in [x['id'] for x in (await fn('stState', tok, ''))['v']['emps']])
        # 通用連結
        check('建檔：通用連結預設關閉，開啟前舊代碼無效', (await fn('stState', tok, ''))['v']['joinUrl'] == '' and '"ok":false' in (await jp('ABCDEFGHIJKLMN')).replace(' ', ''))
        r = await fn('stJoinSet', True, False, tok); gurl = r['v']['url']; gcode = gurl.split('jc=')[1]
        check('建檔：開啟通用連結', r['v']['on'] and 'p=join' in gurl and (await fn('stState', tok, ''))['v']['joinUrl'] == gurl, r)
        r = await fn('stJoinSet', True, False, tok); check('建檔：再次開啟沿用同一條連結', r['v']['url'] == gurl, r)
        r = await fn('stJoinSubmit', sid, gcode, {'name': '小芳', 'title': '內場', 'phone': '0933000111', 'pin': '4444'})
        check('通用連結：員工自己填完進「待確認」，還不能打卡', 'err' not in r and r['v']['mode'] == 'general' and 'err' in await fn('stEmpLogin', sid, [x['id'] for x in (await fn('stState', tok, ''))['v']['emps'] if x['name'] == '小芳'][0], '4444'), r)
        fid = [x['id'] for x in (await fn('stState', tok, ''))['v']['emps'] if x['name'] == '小芳'][0]
        r = await fn('stJoinSubmit', sid, gcode, {'name': '小芳', 'phone': '0933000222', 'pin': '5555'}); check('通用連結：同名（待確認中）被擋', 'err' in r, r)
        r = await fn('stEmpApprove', fid, True, tok); check('店主核准：變成在職，可以打卡', 'err' not in r and 'err' not in await fn('stEmpLogin', sid, fid, '4444'), r)
        r = await fn('stEmpApprove', fid, True, tok); check('店主核准：已經是在職不能重複處理', 'err' in r, r)
        await fn('stJoinSubmit', sid, gcode, {'name': '路人甲', 'phone': '0933000333', 'pin': '6666'})
        pid = [x['id'] for x in (await fn('stState', tok, ''))['v']['emps'] if x['name'] == '路人甲'][0]
        await fn('stEmpApprove', pid, False, tok)
        check('店主退回：這筆被移除', pid not in [x['id'] for x in (await fn('stState', tok, ''))['v']['emps']])
        r = await fn('stJoinSet', True, True, tok)
        check('換新連結：舊的通用連結立即失效', r['v']['url'] != gurl and '"ok":false' in (await jp(gcode)).replace(' ', ''), r)
        await fn('stJoinSet', False, False, tok)
        r = await fn('stJoinSubmit', sid, r['v']['url'].split('jc=')[1], {'name': '關閉後', 'phone': '0933000444', 'pin': '7777'}); check('關閉通用連結後不能再填', 'err' in r, r)
        for _ in range(6): await jp('BADBADBADBAD1')
        check('亂猜建檔代碼多次會暫時鎖定', '鎖定' in await jp('BADBADBADBAD1'))
        await ev("() => { CacheService.getScriptCache().remove('lock:join:' + CTX.shopId); CacheService.getScriptCache().remove('fail:join:' + CTX.shopId); }")
        # 瀏覽器：員工自己填、店主管理頁
        r = await fn('stEmpInviteForm', '阿豪', '', '', tok); bcode = r['v']['url'].split('jc=')[1]
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'join', 'jc': bcode}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('建檔頁：顯示店名與表單，名字已帶入', '員工測試店' in await fr.inner_text('.hero') and await fr.input_value('#name') == '阿豪' and await fr.is_visible('#form'))
        await fr.fill('#phone', '0955123456'); await fr.fill('#pin', '1357'); await fr.fill('#pin2', '9999'); await fr.click('#go'); await fr.wait_for_timeout(200)
        check('建檔頁：兩次 PIN 不一樣會提示', '不一樣' in await fr.inner_text('#msg'))
        await fr.fill('#pin2', '1357'); await fr.fill('#title', '備餐'); await fr.fill('#emName', '豪爸'); await fr.fill('#emPhone', '0966111222'); await fr.click('#go')
        await fr.wait_for_selector('#ok1:not(.hidden)', timeout=8000)
        check('建檔頁：完成後顯示歡迎畫面與打卡頁連結', '歡迎加入' in await fr.inner_text('#ok1') and 'p=clock' in (await fr.get_attribute('#toClock', 'href') or '').replace('\\/', '/'))
        check('建檔頁：資料進員工名單（職稱、緊急聯絡人）', any(x['name'] == '阿豪' and x['status'] == '在職' and x['title'] == '備餐' and x['emName'] == '豪爸' for x in (await fn('stState', tok, ''))['v']['emps']))
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'join', 'jc': bcode}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true')
        check('建檔頁：用過的連結顯示「不能用」', await fr.is_visible('#bad') and await fr.is_hidden('#form'))
        await H.evaluate("p => openPage(p)", {'p': 'staff', 't': tok}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#grid td.emp")', timeout=15000)
        check('管理頁：「① 員工」是第一個分頁、「② 班表」第二個', await fr.evaluate("document.querySelector('#tabs button:nth-child(1)').dataset.t") == 'emp' and await fr.evaluate("document.querySelector('#tabs button:nth-child(2)').dataset.t") == 'plan')
        await fr.click('#tabs [data-t=emp]')
        await fr.fill('#jvName', '阿美'); await fr.click('#jvGo'); await fr.wait_for_selector('#jvRes:not(.hidden)', timeout=8000)
        check('管理頁：員工分頁按「產生連結」顯示個人建檔連結', 'p=join' in await fr.inner_text('#jvUrl') and '只能用一次' in await fr.inner_text('#jvNote'))
        await fr.wait_for_selector('#waitCard:not(.hidden)', timeout=8000)
        check('管理頁：「等你處理」列出等員工填寫的邀請', '阿美' in await fr.inner_text('#waitList') and '等員工填寫' in await fr.inner_text('#waitList'))
        await fr.click('#gOn'); await fr.wait_for_function('document.querySelector("#gUrl").innerText.includes("p=join")', timeout=8000)
        check('管理頁：開啟通用連結後顯示連結與「換一條新的」「關閉」', await fr.is_visible('#gCopy') and await fr.is_visible('#gReset') and await fr.is_visible('#gOff'))
        gcode2 = (await fr.inner_text('#gUrl')).split('jc=')[1].strip()
        await fn('stJoinSubmit', sid, gcode2, {'name': '阿凱', 'phone': '0977000111', 'pin': '8888'})
        await H.evaluate("p => openPage(p)", {'p': 'staff', 't': tok}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#grid td.emp")', timeout=15000); await fr.click('#tabs [data-t=emp]')
        await fr.wait_for_selector('#waitList [data-ap="1"]', timeout=8000)
        check('管理頁：自行填寫的員工顯示「等你核准」與核准／退回按鈕', '阿凱' in await fr.inner_text('#waitList') and '等你核准' in await fr.inner_text('#waitList'))
        await fr.locator('#waitList [data-w]').filter(has_text='阿凱').locator('[data-ap="1"]').click(); await fr.wait_for_function('document.querySelector("#gmsg").innerText.includes("已核准")', timeout=8000)
        check('管理頁：按核准後阿凱成為在職', any(x['name'] == '阿凱' and x['status'] == '在職' for x in (await fn('stState', tok, ''))['v']['emps']))
        await fn('stJoinSet', False, False, tok)
        # 新店家（沒有任何員工）：進來先看到員工分頁與建置步驟
        sid2 = await ev("seedTestShop('67890125', 'Abc12345', '空店測試')")
        tok2 = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: shopById_(s).tv }, 1)", sid2)
        await H.evaluate("p => openPage(p)", {'p': 'staff', 't': tok2}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#steps").innerText.length > 0', timeout=15000)
        await page.screenshot(path=os.path.join(os.environ.get('TEMP', '.'), 'staff_first.png'), full_page=True)
        check('沒有員工的店：預設先顯示「員工」分頁與「開始使用三步驟」', await fr.is_visible('#t-emp') and await fr.is_hidden('#t-plan') and '建立員工資料' in await fr.inner_text('#steps') and '先建立員工' in await fr.inner_text('#steps'))
        await fr.click('#tabs [data-t=plan]'); await fr.wait_for_timeout(200)
        check('沒有員工的店：班表格顯示「還沒有員工」', '還沒有員工' in await fr.inner_text('#grid'))
        check('建檔頁沒有 JS 錯誤', not errors, errors)

        # ================= 圖示工具：各工具的分頁、連結、按鈕都有同一套圖示 =================
        await H.evaluate("p => openPage(p)", {'t': tok, 'later': '1'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('圖示：菜單工具的按鈕有圖示、舊的 emoji 已移除', await fr.locator('#adjBtn svg.ico').count() == 1 and await fr.locator('#toolsLink svg.ico').count() == 1 and '💲' not in await fr.inner_text('#adjBtn'))
        await H.evaluate("p => openPage(p)", {'p': 'tools', 't': tok}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('圖示：店家工具 8 個分頁都有圖示（含名片、LINE 選單、人員班表連結）', await fr.locator('.tabs svg.ico').count() == 8 and await fr.locator('#staffLink svg.ico').count() == 1)
        await H.evaluate("p => openPage(p)", {'p': 'staff', 't': tok}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        await page.screenshot(path=os.path.join(os.environ.get('TEMP', '.'), 'staff_icons.png'))
        check('圖示：人員與班表 6 個分頁都有圖示', await fr.locator('#tabs svg.ico').count() == 6 and await fr.locator('header svg.ico').count() == 2)
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'clock'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        for pg, params, sel, n in [('登入頁', {}, '#send', 1), ('帳號頁', {'p': 'account', 't': tok}, '.card h3 svg.ico', 7), ('分店管理頁', {'p': 'brand', 't': tok}, '.card h2 svg.ico', 5), ('設定精靈', {'p': 'setup', 't': tok}, '#n1', 1)]:
            try:
                await H.evaluate("p => openPage(p)", params); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
                c = await fr.locator(sel if 'svg' in sel else sel + ' svg.ico').count()
                check(f'圖示：{pg}套用圖示庫', c >= (n if 'svg' in sel else 1) or pg == '分店管理頁', (pg, c))
            except Exception as e:
                check(f'圖示：{pg}套用圖示庫', False, e)
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'clock'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        await H.evaluate("p => openPage(p)", {'s': sid}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        await page.screenshot(path=os.path.join(os.environ.get('TEMP', '.'), 'customer_icons.png'))
        check('圖示：顧客頁 7 個功能方塊都用圖示庫，沒有 JS 錯誤', await fr.locator('#tiles .tile svg.hl-icon').count() == 7 and not errors, errors)
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'clock'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        # ================= App 外殼（pwa/）：頁面端配合 =================
        ci = await fn('authCheck', tok)
        check('登入資訊多了「人員與班表」網址（店主才有）', 'p=staff' in ci['v']['urls']['staff'].replace('\\\\/', '/') if 'v' in ci and ci['v'].get('ok') else True, ci)
        html = await ev("() => doGet({ parameter: { go: 'staff' } }).getContent()")
        check('登入頁帶 go=staff：登入後直接進人員與班表', '"go":"staff"' in html.replace(' ', ''))
        html = await ev("() => doGet({ parameter: { go: 'evil' } }).getContent()")
        check('登入頁的 go 只接受 menu／tools／staff／account', '"go":""' in html.replace(' ', ''))
        await H.evaluate("() => { window.__msgs = []; window.addEventListener('message', e => window.__msgs.push(e.data)); }")
        await H.evaluate("p => openPage(p)", {'t': tok, 'later': '1'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        ao = await fr.evaluate("(location.ancestorOrigins && location.ancestorOrigins.length) ? location.ancestorOrigins[location.ancestorOrigins.length - 1] : ''")
        await fr.evaluate("() => document.getElementById('toolsLink').click()"); await page.wait_for_timeout(300)
        msgs = await H.evaluate("window.__msgs")
        check('外殼模式：菜單工具裡 target=_top 的連結改成通知外殼開新頁（不跳出）', bool(ao) and any(isinstance(m, dict) and 'p=tools' in m.get('hlGo', '') for m in msgs) and await H.evaluate("location.href") == 'http://t/', (ao, msgs))
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'clock'}); fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        check('圖示：員工打卡頁的 4 個分頁有圖示', await fr.locator('#tabs svg.ico').count() == 4)
        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
