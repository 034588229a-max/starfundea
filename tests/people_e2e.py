"""人事新功能測試：專屬入口（個人連結）、入職填寫與證件上傳、登陸完成信、補打卡原因、今日出勤與未打卡提醒、特休（勞基法）。
執行：python tests/people_e2e.py
日期固定在週三 2026-10-07，避免在週日、週一等週界日跑出不同結果。
"""
import asyncio, base64, json, os, re, sys
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T, SRC = os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'src')
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:600]))

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

JPG = base64.b64encode(b'\xff\xd8\xff\xe0fakejpg').decode()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 420, 'height': 900})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
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
        async def at(hhmm, day='2026-10-07'):
            await ev("([t, d]) => { window.__off = new Date(d + 'T' + t + ':00+08:00').getTime() - window.__real.call(Date); }", [hhmm, day])
        async def mails(): return await ev("__store.mails.slice()")

        await ev("setupCenter()")
        sid = await ev("createTestShop()")
        tok = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: shopById_(s).tv }, 1)", sid)
        await ev("s => { CTX = { shopId: s, ssId: shopById_(s).ssId, shop: shopById_(s) }; _spMap = null; props_().setProperty('cfg', JSON.stringify({ name: '人事測試店', notifyEmail: 'boss@example.com' })); }", sid)
        await at('05:50')
        today = await ev("stToday_()")
        check('測試日期固定在週三', today == '2026-10-07', today)
        wk = await ev("t => stWeekStart_(t)", today)

        # ================= 員工資料：到職日、地址 =================
        r = await fn('stEmpSave', {'name': '小明', 'pin': '1234', 'hired': '2025-13-40'}, tok); check('員工：到職日格式不對被擋', 'err' in r and '到職日' in r['err'], r)
        r = await fn('stEmpSave', {'name': '小明', 'title': '外場', 'pin': '1234', 'hired': '2023-03-01', 'addr': '桃園市中壢區（示範）', 'email': 'ming@example.com'}, tok)
        em = [x for x in r['v'] if x['name'] == '小明'][0]
        check('員工：存到職日與地址', em['hired'] == '2023-03-01' and em['addr'].startswith('桃園') and em['id'] == 'E001', r)
        r = await fn('stEmpSave', {'id': 'E001', 'name': '小明', 'title': '外場', 'email': 'ming@example.com'}, tok)
        check('員工：只改職稱時，到職日與地址保留', [x for x in r['v'] if x['id'] == 'E001'][0]['hired'] == '2023-03-01', r)

        # ================= 專屬入口（個人連結） =================
        lk = (await fn('stEmpLink', 'E001', tok))['v']
        check('專屬連結：網址含店家編號與 jc 通行證', lk['url'] and ('s=' + sid) in lk['url'] and '&jc=' in lk['url'] and 'p=clock' in lk['url'], lk)
        jc = lk['url'].split('jc=')[1]
        home = await fn('stEmpHome', jc)
        check('專屬連結：通行證打開就是本人（小明）', 'err' not in home and home['v']['emp']['name'] == '小明' and home['v']['emp']['hired'] == '2023-03-01', home)
        html = await ev("(a) => doGet({ parameter: { s: a[0], p: 'clock', jc: a[1] } }).getContent()", [sid, jc])
        check('專屬連結：打卡頁把通行證帶進頁面，而且沒有員工名單', ('"tok":"' + jc.replace('/', '\\/')) in html.replace(' ', '') or jc[:30] in html, html[:200])
        check('打卡頁的資料裡沒有任何員工姓名', '小明' not in html)
        r = await fn('stEmpLink', 'E001', 'garbage'); check('專屬連結：沒有店主通行證拿不到', 'err' in r, r)
        r = await fn('stEmpLinkReset', 'E001', tok)
        check('專屬連結：重設後舊連結立刻失效、新連結可用', 'err' in await fn('stEmpHome', jc) and 'err' not in await fn('stEmpHome', r['v']['url'].split('jc=')[1]), r)
        jc = r['v']['url'].split('jc=')[1]
        r = await fn('stEmpLink', 'E999', tok); check('專屬連結：找不到員工被擋', 'err' in r, r)

        # ================= 入職邀請 → 填寫（含證件上傳）→ 登陸完成信 =================
        n0 = len(await mails())
        r = await fn('stEmpInviteForm', '陳小花', 'xiaohua@example.com', '', tok, '2024-10-07')
        check('邀請：寄出邀請信（附到職日）', 'err' not in r and r['v']['mailed'] and len(await mails()) == n0 + 1, r)
        m = (await mails())[-1]
        check('邀請信提到證件與存摺、登陸完成信', '證件' in m['body'] and '登陸完成' in m['body'], m['body'][:200])
        code = re.search(r'jc=([A-Z0-9]+)', m['body'].replace('\\/', '/')).group(1)
        bad = {'idF': {'name': 'a.exe', 'b64': JPG}}
        r = await fn('stJoinSubmit', sid, code, {'name': '陳小花', 'phone': '0912-000-111', 'email': 'xiaohua@example.com', 'emName': '陳大明', 'emPhone': '0922-111-222', 'pin': '2468', 'addr': '桃園市中壢區（示範）', 'files': bad})
        check('入職：不支援的檔案類型被擋', 'err' in r and 'JPG' in r['err'], r)
        big = {'idF': {'name': 'a.jpg', 'b64': base64.b64encode(b'x' * (4 * 1024 * 1024 + 10)).decode()}}
        r = await fn('stJoinSubmit', sid, code, {'name': '陳小花', 'phone': '0912-000-111', 'pin': '2468', 'files': big})
        check('入職：檔案超過 4MB 被擋', 'err' in r and '太大' in r['err'], r)
        n1 = len(await mails())
        r = await fn('stJoinSubmit', sid, code, {'name': '陳小花', 'phone': '0912-000-111', 'email': 'xiaohua@example.com', 'emName': '陳大明', 'emPhone': '0922-111-222', 'pin': '2468', 'addr': '桃園市中壢區（示範）',
                                                 'files': {'idF': {'name': 'id1.jpg', 'b64': JPG}, 'idB': {'name': 'id2.jpg', 'b64': JPG}, 'bank': {'name': 'bank.pdf', 'b64': JPG}}})
        check('入職：員工自己填完，三個檔案都存下來並回傳專屬入口', 'err' not in r and r['v']['ok'] and sorted(r['v']['uploaded']) == ['bank', 'idB', 'idF'] and 'jc=' in r['v']['portalUrl'], r)
        ms = (await mails())[n1:]
        done = [x for x in ms if x['to'] == 'xiaohua@example.com']
        check('入職：寄出「登陸完成」信給員工，內含專屬入口與加到主畫面說明', len(done) == 1 and '登陸完成' in done[0]['subject'] and 'jc=' in done[0]['body'].replace('\\/', '/') and '加入主畫面' in done[0]['body'], done)
        check('品牌信件：員工入口信用店家名義代寄（店名頁首、店家強調色按鈕）', done[0].get('html') and '打開我的員工入口' in done[0]['html'] and '代「' in done[0]['html'] and done[0]['name'].endswith('（SFD 代寄）') and not done[0]['imgs'], {k: done[0].get(k) for k in ('name', 'imgs')})
        check('入職：店主也收到完成通知', any(x['to'] == 'boss@example.com' for x in ms), ms)
        st = (await fn('stState', tok, ''))['v']
        hua = [x for x in st['emps'] if x['name'] == '陳小花'][0]
        check('入職：員工成為在職，到職日、地址、三個檔案連結都在（只有店主看得到）', hua['status'] == '在職' and hua['hired'] == '2024-10-07' and hua['addr'].startswith('桃園') and all(hua['files'][k].startswith('https://drive.google.com/file/d/') for k in ['idF', 'idB', 'bank']) and hua['dir'].startswith('https://drive.google.com/drive/folders/'), hua)
        r = await fn('stEmpHome', jc)
        check('入職：員工首頁不會洩漏證件連結', 'idF' not in json.dumps(r.get('v', {})) and 'drive.google' not in json.dumps(r.get('v', {})), r)
        r = await fn('stJoinSubmit', sid, code, {'name': '陳小花', 'phone': '0912-000-111', 'pin': '2468'})
        check('入職：同一個連結只能用一次', 'err' in r, r)

        # 通用連結：自行填寫 → 待確認（只寄「已收到」），核准後才寄登陸完成信
        j = (await fn('stJoinSet', True, False, tok))['v']; gcode = j['url'].split('jc=')[1]
        n2 = len(await mails())
        r = await fn('stJoinSubmit', sid, gcode, {'name': '阿凱', 'phone': '0933-222-111', 'email': 'kai@example.com', 'pin': '1357', 'files': {'bank': {'name': 'b.png', 'b64': JPG}}})
        ms = (await mails())[n2:]
        kai_mail = [x for x in ms if x['to'] == 'kai@example.com']
        check('通用連結：填完先寄「已收到」，還沒有專屬入口', len(kai_mail) == 1 and '已收到' in kai_mail[0]['subject'] and 'jc=' not in kai_mail[0]['body'].replace('\\/', '/'), kai_mail)
        kai = [x for x in (await fn('stState', tok, ''))['v']['emps'] if x['name'] == '阿凱'][0]
        n3 = len(await mails())
        r = await fn('stEmpApprove', kai['id'], True, tok)
        ms = (await mails())[n3:]
        check('通用連結：店主核准後寄出「登陸完成」信與專屬入口', any(x['to'] == 'kai@example.com' and '登陸完成' in x['subject'] and 'jc=' in x['body'].replace('\\/', '/') for x in ms), ms)

        # ================= 排班與打卡：補打卡原因、今日出勤 =================
        await fn('stEmpSave', {'name': '小美', 'pin': '1111', 'email': 'mei@example.com', 'hired': '2025-02-15'}, tok)
        emps = {x['name']: x['id'] for x in (await fn('stState', tok, ''))['v']['emps']}
        rows = [{'d': today, 'e': emps['小明'], 'n': '早班', 's': '06:00', 't': '13:00'}, {'d': today, 'e': emps['小美'], 'n': '早班', 's': '06:00', 't': '13:00'}, {'d': today, 'e': emps['陳小花'], 'n': '晚班', 's': '13:00', 't': '20:00'}]
        await fn('stShiftSave', wk, rows, tok)
        tm = (await fn('stEmpLink', emps['小明'], tok))['v']['url'].split('jc=')[1]
        tmei = (await fn('stEmpLink', emps['小美'], tok))['v']['url'].split('jc=')[1]
        await at('05:58')
        h = (await fn('stEmpHome', tm))['v']
        check('打卡：上班前，今日狀態是「還沒打卡」且不需要原因', h['status']['state'] == 'none' and not h['status']['needReason'], h['status'])
        r = await fn('stPunch', tm, '')
        check('打卡：不用選上班或下班，第一次按就是上班', 'err' not in r and r['v']['kind'] == 'in' and r['v']['time'] == '05:58' and not r['v']['reason'], r)
        h = (await fn('stEmpHome', tm))['v']
        check('打卡：狀態變成上班中', h['status']['state'] == 'working' and h['status']['in'] == '05:58', h['status'])
        await at('06:20')
        h2 = (await fn('stEmpHome', tmei))['v']
        check('補打卡：超過上班時間 20 分鐘，要選原因（回報遲到分鐘）', h2['status']['needReason'] and h2['status']['lateMins'] == 20 and '交通延誤' in h2['reasons'], h2['status'])
        r = await fn('stPunch', tmei, ''); check('補打卡：沒選原因被擋', 'err' in r and '需要原因' in r['err'], r)
        r = await fn('stPunch', tmei, '', '客人臨時叫貨，車子卡在路上'); check('補打卡：自己填的原因最多 30 字，收下', 'err' not in r and r['v']['reason'].startswith('客人臨時叫貨') and r['v']['late'] == 20, r)
        pl = (await fn('stPunchList', today, today, tok))['v']
        mine = [x for x in pl if x['e'] == emps['小美']][0]
        check('補打卡：店主看得到原因與遲到分鐘', mine['reason'].startswith('客人臨時叫貨') and mine['late'] == 20, mine)
        # 未打卡提醒
        await at('13:20')
        att = (await fn('stState', tok, ''))['v']['att']
        names = {o['name']: o for o in att['list']}
        check('今日出勤：列出今天有班的人與狀態', set(names) == {'小明', '小美', '陳小花'} and names['小美']['reason'].startswith('客人臨時叫貨'), att)
        check('今日出勤：小明上班打卡後沒下班，陳小花超過 15 分鐘沒打卡被標「尚未打卡」', names['小明']['state'] == 'in' and names['陳小花']['state'] == 'none' and names['陳小花']['missing'] and att['missing'] == 1, att)
        n4 = len(await mails())
        r = await fn('stRemindMissing_')
        ms = (await mails())[n4:]
        check('未打卡提醒：寄給陳小花本人，再寄一封彙整給店主', r['v']['sent'] == ['陳小花'] and any(x['to'] == 'xiaohua@example.com' and '還沒打卡' in x['subject'] for x in ms) and any(x['to'] == 'boss@example.com' and '未打卡' in x['subject'] for x in ms), (r, ms))
        n5 = len(await mails())
        r = await fn('stRemindMissing_')
        check('未打卡提醒：同一個人同一天不重複寄', r['v']['sent'] == [] and len(await mails()) == n5, r)
        r = await fn('stRemindNow', emps['陳小花'], tok); check('店主手動提醒：寄得出去', 'err' not in r and r['v']['sent'], r)
        r = await fn('stRemindNow', emps['小明'], tok); check('店主手動提醒：沒有電子郵件被擋', 'err' not in r or '電子郵件' in r['err'], r)
        await ev("() => { CacheService.getScriptCache().removeAll && CacheService.getScriptCache().removeAll(); }")
        r = await fn('stCfgSave', {'shifts': [{'n': '早班', 's': '06:00', 'e': '13:00'}], 'grace': 5, 'missRemind': False}, tok)
        n6 = len(await mails()); await fn('stRemindMissing_')
        check('未打卡提醒：店主可以關閉自動提醒', 'err' not in r and r['v']['missRemind'] is False and len(await mails()) == n6, r)
        await fn('stCfgSave', {'shifts': [{'n': '早班', 's': '06:00', 'e': '13:00'}], 'grace': 5, 'missRemind': True, 'reasons': ['交通延誤', '忘記打卡', '臨時支援', '身體不舒服']}, tok)
        clr = "() => { CacheService.getScriptCache().removeAll && CacheService.getScriptCache().removeAll(); }"
        await ev(clr); await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", ['missEmp'])
        n7 = len(await mails()); r = await fn('stRemindMissing_'); ms = (await mails())[n7:]
        check('通知信開關：關掉「未打卡寄給員工」→ 只寄彙整給店主', r['v']['sent'] == [] and [x['to'] for x in ms] == ['boss@example.com'], (r, ms))
        await ev(clr); await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", ['miss', 'missEmp'])
        n8 = len(await mails()); r = await fn('stRemindMissing_')
        check('通知信開關：兩個都關 → 完全不寄', len(await mails()) == n8 and r['v']['owner'] is False, r)
        await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", [])
        check('補打卡原因：店主可以自訂選項', '身體不舒服' in (await fn('stEmpHome', tm))['v']['reasons'])
        r = await fn('sfdTick'); check('每小時掃描 sfdTick 跑得起來', 'err' not in r, r)

        # ================= 特休（勞基法第 38 條） =================
        cases = [('2026-05-01', 0), ('2026-03-01', 3), ('2025-10-07', 7), ('2024-10-07', 10), ('2023-03-01', 14), ('2021-10-07', 15), ('2016-10-07', 16), ('1990-01-01', 30), ('2025-10-08', 3)]
        for hired, want in cases:
            got = await ev("([h, d]) => stAnnualDays_(h, d)", [hired, today])
            check(f'特休天數：到職 {hired} → {want} 天', got == want, got)
        an = (await fn('stEmpHome', tm))['v']['annual']
        check('特休：小明（2023-03-01 到職，今天年資 3 年 7 個月）14 天、已休 0、剩 14', an['ok'] and an['days'] == 14 and an['used'] == 0 and an['left'] == 14 and an['from'] == '2026-03-01' and an['to'] == '2027-03-01', an)
        d3 = await ev("t => stAdd_(t, 3)", today)
        r = await fn('stLeaveSubmit', tm, {'type': '特休', 'start': d3, 'end': await ev("t => stAdd_(t, 2)", d3), 'reason': '旅遊'})
        check('特休：申請 3 天（待審）成功', 'err' not in r, r)
        r = await fn('stLeaveSubmit', tm, {'type': '特休', 'start': await ev("t => stAdd_(t, 20)", today), 'end': await ev("t => stAdd_(t, 33)", today)})
        check('特休：待審 3 天 + 再申請 14 天，超過剩餘 14 天被擋', 'err' in r and '特休不夠' in r['err'], r)
        pend = (await fn('stState', tok, ''))['v']['pending']
        n7 = len(await mails())
        r = await fn('stLeaveDecide', pend[0]['id'], True, '玩得開心', tok)
        ms = (await mails())[n7:]
        check('特休：核准後寄信通知員工，並告知剩餘天數', 'err' not in r and any(x['to'] == 'ming@example.com' and '已核准' in x['subject'] and '剩 11 天' in x['body'] for x in ms), ms)
        check('特休：核准後剩餘天數扣掉 3 天', (await fn('stEmpHome', tm))['v']['annual']['left'] == 11)
        an2 = (await fn('stEmpHome', tmei))['v']['annual']
        check('特休：小美（2025-02-15 到職）滿 1 年 7 天', an2['days'] == 7 and an2['years'] == 1, an2)
        await fn('stEmpSave', {'name': '阿豪', 'pin': '3333'}, tok)
        tok_hao = (await fn('stEmpLink', [x for x in (await fn('stState', tok, ''))['v']['emps'] if x['name'] == '阿豪'][0]['id'], tok))['v']['url'].split('jc=')[1]
        r = await fn('stLeaveSubmit', tok_hao, {'type': '特休', 'start': d3, 'end': d3})
        check('特休：沒填到職日算不出特休，請員工先找店長', 'err' in r and '到職日' in r['err'], r)
        r = await fn('stLeaveSubmit', tok_hao, {'type': '事假', 'start': d3, 'end': d3}); check('請假：事假不受到職日影響', 'err' not in r, r)

        # ================= 預期排班與班表輸出 =================
        per_id = 'm:2026-11'
        r = await fn('stCfgSave', {'avail': {'on': True, 'mode': 'month', 'day': 7}}, tok)
        check('預期排班：只改提醒設定不會動到班別', 'err' not in r and r['v']['avail']['on'] and r['v']['avail']['day'] == 7 and r['v']['shifts'], r)
        n8 = len(await mails())
        r = await fn('stAvailRemind_')
        ms = (await mails())[n8:]
        check('預期排班：今天是設定的日子，寄給有信箱的在職員工（含本人的專屬連結）', 'err' not in r and '小美' in r['v']['sent'] and any(x['to'] == 'xiaomei@example.com' or x['to'].startswith('xiao') for x in ms) and any('p=avail' in x['body'] for x in ms), (r, ms))
        n9 = len(await mails()); r = await fn('stAvailRemind_')
        check('預期排班：同一個期間只自動提醒一次', r['v']['sent'] == [] and len(await mails()) == n9, r)
        url = (await ev("([e, p]) => stAvailUrl_(stEmps_().filter(x => x.id === e)[0], stPeriodById_(p))", [emps['小美'], per_id]))
        atok = url.split('jc=')[1]
        info = (await fn('stAvailInfo', atok))['v']
        check('預期排班：夥伴打開連結，期間是下個月（11 月）且只看到自己', info['name'] == '小美' and info['period']['from'] == '2026-11-01' and info['period']['to'] == '2026-11-30' and info['days'] == [] and info['open'], info)
        r = await fn('stAvailSubmit', atok, ['2026-11-03', '2026-11-04', '2026-12-01', '2026-10-30', 'bad'], '18 號考試')
        check('預期排班：送出時只收期間內的合法日期', 'err' not in r and r['v']['count'] == 2, r)
        r = await fn('stAvailSubmit', atok, ['2026-11-05'], '')
        info = (await fn('stAvailInfo', atok))['v']
        check('預期排班：再送一次是覆蓋，不重複', r['v']['count'] == 1 and info['days'] == ['2026-11-05'] and info['replied'], info)
        r = await fn('stAvailSubmit', tm, ['2026-11-05'], ''); check('預期排班：一般打卡通行證不能當填寫連結', 'err' in r, r)
        lst = (await fn('stAvailList', tok, per_id))['v']
        check('預期排班：店主看得到全部回覆與沒填的人', [x['name'] for x in lst['rows']] == ['小美'] and lst['rows'][0]['note'] == '' and any(x['name'] == '陳小花' for x in lst['missing']) and all(x['name'] != '小美' for x in lst['missing']), lst)
        n10 = len(await mails()); r = await fn('stAvailRemindNow', tok)
        ms = (await mails())[n10:]
        check('預期排班：店主手動提醒只寄給還沒填的人', 'err' not in r and '小美' not in r['v']['sent'] and ms and all(x['to'] != 'xiaomei@example.com' for x in ms), (r, ms))
        r = await fn('stAvailList', tm); check('預期排班：員工不能看全部回覆', 'err' in r, r)
        sd = (await fn('stScheduleData', 'month', '2026-10-15', tok))['v']
        check('班表輸出：月範圍＝整個 10 月，含員工與班', sd['from'] == '2026-10-01' and sd['to'] == '2026-10-31' and sd['emps'] and 'shifts' in sd, sd)
        n11 = len(await mails())
        r = await fn('stScheduleSend', 'week', today, [], {'png': {'b64': JPG}, 'pdf': {'b64': JPG}}, tok)
        ms = (await mails())[n11:]
        check('班表輸出：一鍵寄出，附 PDF 與 1:1 圖檔兩個附件', 'err' not in r and r['v']['attached'] == 2 and len(r['v']['sent']) >= 1 and len(ms) == len(r['v']['sent']), (r, ms))
        r = await fn('stScheduleSend', 'week', today, [], {'png': {'b64': JPG}}, tid if (tid := None) else 'bad-key')
        check('班表輸出：沒有權限不能寄', 'err' in r, r)
        await H.evaluate("p => openPage(p)", {'p': 'staff', 't': tok}); fs = H.child_frames[0]
        await fs.wait_for_function('window.__hlEnd === true', timeout=10000); await fs.wait_for_selector('#avCard', timeout=8000)
        await fs.wait_for_function("document.getElementById('avSum').textContent.length > 0", timeout=8000)
        check('頁面：班表分頁有預期排班卡，顯示期間與回覆人數', '11 月' in await fs.inner_text('#avSum') and '已回覆 1' in await fs.inner_text('#avSum'), await fs.inner_text('#avSum'))
        pdfhead = await fs.evaluate("async () => { const D = await run('stScheduleData', 'week', ST.week, TOKEN); const u = makePdf(D); const p = makePng(D); return [String.fromCharCode(...u.slice(0, 5)), u.length, p[1], p[2], p[3]]; }")
        check('班表輸出：瀏覽器端真的產生 PDF（%PDF）與 PNG 檔', pdfhead[0] == '%PDF-' and pdfhead[1] > 5000 and pdfhead[2:] == [80, 78, 71], pdfhead)
        dl = await fs.evaluate("async () => { const D = await run('stScheduleData', 'month', ST.week, TOKEN); const u = makePdf(D); const t = new TextDecoder('latin1').decode(u); return [t.indexOf('startxref') > 0, t.endsWith('%%EOF')]; }")
        check('班表輸出：PDF 結尾完整（xref 與 EOF）', dl == [True, True], dl)
        # ================= 交接：急／一般／緩、指定人、隔天提醒 =================
        r = await fn('tAddHandover', {'day': today, 'shift': '早班', 'who': '店長', 'text': '冰箱門要修', 'todo': True, 'prio': '緩', 'to': ''}, tok)
        r = await fn('tAddHandover', {'day': today, 'shift': '早班', 'who': '店長', 'text': '客人訂的蛋糕明早要取', 'todo': True, 'prio': '急', 'to': '小明'}, tok)
        r = await fn('tAddHandover', {'day': today, 'shift': '早班', 'who': '店長', 'text': '零用金剩 2000', 'todo': False, 'prio': '怪', 'to': ''}, tok)
        hl = r['v']['handover']
        check('交接：急排在最前面，沒指定的標籤預設「一般」', [h['prio'] for h in hl if h['status'] == '待處理'] == ['急', '緩'] and [h for h in hl if h['text'].startswith('零用金')][0]['prio'] == '一般' and hl[0]['to'] == '小明', hl)
        n12 = len(await mails()); r = await fn('tHandRemind_')
        check('交接：當天寫的不算「隔天」，不提醒', r['v']['sent'] == 0 and len(await mails()) == n12, r)
        await ev("() => { tSetJson_('hand_last', ''); }")
        old = (await ev("() => tAddDays_(tToday_(), -1)"))
        await ev("d => { var sh = tHandSheet_(); var n = sh.getLastRow(); for (var i = 2; i <= n; i++) sh.getRange(i, 3).setValue(d); }", old)
        await at('10:00')
        n13 = len(await mails()); r = await fn('tHandRemind_'); ms = (await mails())[n13:]
        check('交接：隔天 9 點後，把沒處理的寄給店主（急在前），再寄給被指定的人', r['v']['sent'] >= 2 and any('boss@example.com' == x['to'] and x['body'].index('【急】') < x['body'].index('【緩】') for x in ms) and any(x['to'] == 'ming@example.com' and '交接' in x['subject'] for x in ms), (r, ms))
        n14 = len(await mails()); r = await fn('tHandRemind_')
        check('交接：同一天只提醒一次', r['v']['sent'] == 0 and len(await mails()) == n14, r)
        await ev("() => { tSetJson_('hand_last', ''); }"); await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", ['handEmp'])
        n15 = len(await mails()); r = await fn('tHandRemind_'); ms = (await mails())[n15:]
        check('通知信開關：關掉「交接寄給員工」→ 只寄給店主', [x['to'] for x in ms] == ['boss@example.com'], ms)
        await ev("() => { tSetJson_('hand_last', ''); }"); await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", ['hand', 'handEmp'])
        n16 = len(await mails()); r = await fn('tHandRemind_')
        check('通知信開關：交接兩個都關 → 不寄信', len(await mails()) == n16 and r['v']['sent'] == 0, r)
        await ev("o => { var c = JSON.parse(props_().getProperty('cfg') || '{}'); c.notifyOff = o; props_().setProperty('cfg', JSON.stringify(c)); }", [])
        eh = (await fn('stEmpHome', tm))['v']
        check('交接：員工入口看得到待處理，指定給他的標「mine」', len(eh['hand']) == 2 and [x for x in eh['hand'] if x['text'].startswith('客人')][0]['mine'] and eh['hand'][0]['prio'] in ('急', '緩'), eh['hand'])
        r = await fn('stHandDone', tm, eh['hand'][0]['id'])
        eh2 = (await fn('stEmpHome', tm))['v']
        check('交接：員工按「處理完成」後不再列出，並記下是誰完成', 'err' not in r and len(eh2['hand']) == 1, (r, eh2['hand']))
        r = await fn('stHandDone', 'bad-token', eh2['hand'][0]['id']); check('交接：沒有員工通行證不能完成', 'err' in r, r)
        # ================= 工作守則・教育訓練・文件：必讀與進度 =================
        PDFB = base64.b64encode(b'%PDF-1.4 test').decode()
        r = await fn('stDocAdd', PDFB, 'open.pdf', '開店流程', '工作守則', '員工', tok); check('文件：新增「工作守則」分類', 'err' not in r and any(d['cat'] == '工作守則' for d in r['v']), r)
        r = await fn('stDocAdd', PDFB, 'train.pdf', '新人基本訓練', '教育訓練', '員工', tok); did2 = [d for d in r['v'] if d['cat'] == '教育訓練'][0]['id']
        did1 = [d for d in r['v'] if d['cat'] == '工作守則'][0]['id']
        r = await fn('stDocMust', did1, True, tok); check('文件：店主可設為必讀', 'err' not in r and [d for d in r['v'] if d['id'] == did1][0]['must'], r)
        r = await fn('stDocMust', did1, True, tm); check('文件：員工不能改必讀', 'err' in r, r)
        eh = (await fn('stEmpHome', tm))['v']
        check('員工入口：文件帶必讀標示與自己的進度（都還沒看）', [d for d in eh['docs'] if d['id'] == did1][0]['must'] and not any(d['read'] for d in eh['docs']), eh['docs'])
        r = await fn('stDocRead', tm, did2); r2 = await fn('stDocRead', tm, did2)
        eh = (await fn('stEmpHome', tm))['v']
        check('員工按「我看完了」：記下進度、重按不重複', 'err' not in r and 'err' not in r2 and [d for d in eh['docs'] if d['id'] == did2][0]['read'] and not [d for d in eh['docs'] if d['id'] == did1][0]['read'], eh['docs'])
        stt = (await fn('stState', tok, ''))['v']
        check('店主看得到每份文件幾位員工看完', [d for d in stt['docs'] if d['id'] == did2][0]['readN'] == 1 and [d for d in stt['docs'] if d['id'] == did1][0]['readN'] == 0, stt['docs'])
        r = await fn('stDocRead', 'bad-token', did2); check('文件：沒有員工通行證不能標看完', 'err' in r, r)

        # ================= 頁面：專屬連結在瀏覽器裡真的是本人 =================
        await at('05:55')
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'clock', 'jc': jc}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000); await fr.wait_for_selector('#home:not(.hidden)', timeout=8000)
        check('頁面：用專屬連結打開，直接顯示本人的打卡畫面（小明）', '小明' in await fr.inner_text('#who') and await fr.is_hidden('#login'), await fr.inner_text('#who'))
        check('頁面：特休卡片顯示剩餘天數與依據', '14' in await fr.inner_text('#annual') or '特休剩餘' in await fr.inner_text('#annual'), await fr.inner_text('#annual'))
        await H.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        await H.evaluate("p => openPage(p)", {'s': sid, 'p': 'clock'}); fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true', timeout=10000)
        body_txt = await fr.inner_text('body')
        check('頁面：沒有連結時是員工編號＋PIN 登入，畫面上沒有任何同事的名字', all(n not in body_txt for n in ['小明', '小美', '陳小花', '阿凱']))
        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
