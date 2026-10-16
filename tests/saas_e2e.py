"""線上服務模式測試：授權中心、統編＋密碼＋Email 驗證碼登入、夥伴邀請、授權到期（寬限／唯讀／停用）、
店家資料隔離、管理後台、收款通知、單店轉入、登入頁／管理後台／帳號頁（真的在瀏覽器裡操作）。
執行：python tests/saas_e2e.py
"""
import asyncio, json, os, re, sys, tempfile
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T, SRC = os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'src')
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:500]))

NAMES = ['Page', 'Customer', 'Tools', 'Login', 'Admin', 'Account', 'Setup', 'Brand']
def files_json():
    return json.dumps({n: open(os.path.join(SRC, n + '.html'), encoding='utf-8').read() for n in NAMES}).replace('</', '<\\/')

SEED = """
(function () {
  __store.props.ssId = 'test';
  var p = __ss.insertSheet('價格表');
  p.data = [['弘林'], [''], [''], [''], ['代碼']];
  ITEMS.slice(0, 20).forEach(function (it) { p.data.push([it[0], it[1], it[2], it[3], it[4], it[4], false, !!it[5], '']); });
  __store.props.t_shop = JSON.stringify({ name: '弘林早午餐', tagline: '中壢好味道' });
  __store.props.ver = '7';
  var real = Date.now; window.__off = 0; Date.now = function () { return real.call(Date) + window.__off; };
})();
"""
HOST = """<!doctype html><html><head><meta charset="utf-8">
<script>window.__REAL_CODE = true;</script>
<script src="/mock.js"></script><script src="/Code.gs.js"></script><script src="/Tools.gs.js"></script><script src="/Tenant.gs.js"></script><script src="/Mail.gs.js"></script><script src="/Auth.gs.js"></script><script src="/Billing.gs.js"></script><script src="/Provision.gs.js"></script><script src="/Shop.gs.js"></script><script src="/BrandServer.gs.js"></script><script src="/saas_mock.js"></script>
<script>window.__FILES = %s;</script><script src="/seed.js"></script>
<script>
function openPage(params) {
  if (params.t && !params.p && !params.wizard) params.later = '1';
  var html = doGet({ parameter: params }).getContent();
  html = html.replace('<head>', '<head><script>window.google = parent.google;<\\/script>');
  return new Promise(function (res) { var f = document.getElementById('f'); f.onload = function () { setTimeout(function () { res(true); }, 400); }; f.srcdoc = html; });
}
</script></head><body style="margin:0"><iframe id="f" style="width:420px;height:900px;border:0"></iframe></body></html>"""

OTP = re.compile(r'驗證碼：(\d{6})')

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
            m = re.search(r'/(Tenant|Mail|Auth|Billing|Provision|Shop|BrandServer)\.gs\.js$', u)
            if m: return await r.fulfill(path=os.path.join(SRC, m.group(1) + '.gs'), content_type='text/javascript')
            if u.endswith('/seed.js'): return await r.fulfill(body=SEED, content_type='text/javascript')
            return await r.abort()
        await page.route('**/*', route)
        await page.goto('http://t/')
        H = page.main_frame
        check('所有指令碼載入無錯誤', not errors, errors)

        async def ev(js, arg=None):
            return await H.evaluate(js, arg)
        async def link_of(to=None):
            body = await ev("(to) => { var m = __store.mails.filter(x => !to || x.to === to); return m.length ? m[m.length - 1].body : ''; }", to)
            m = re.search(r'\?ml=([0-9a-f]+)', body or ''); return m.group(1) if m else ''
        async def otp_of(to=None):
            # 登入／註冊／設定密碼的信只有連結（信裡沒有驗證碼）；直接呼叫 authVerify 等 API 的測試，從連結紀錄拿出背後那組驗證碼
            mid = await link_of(to)
            if mid:
                raw = await ev("id => CacheService.getScriptCache().get('ml:' + id)", mid)
                return json.loads(raw)['c'] if raw else ''
            body = await ev("(to) => { var m = __store.mails.filter(x => !to || x.to === to); return m.length ? m[m.length - 1].body : ''; }", to)
            m = OTP.search(body or ''); return m.group(1) if m else ''
        async def advance(days):
            await ev("d => { window.__off += d * 86400000; }", days)
        async def fn(name, *args):
            return await ev("([n, a]) => { try { var r = window[n].apply(null, a); return { v: r === undefined ? null : r }; } catch (e) { return { err: String(e.message || e) }; } }", [name, list(args)])

        # ================= 1. 建立授權中心、轉入弘林 =================
        await ev("setupCenter()")
        check('授權中心建立：有 centerId、四個分頁、每日觸發', await ev("!!__store.props.centerId && ['店家','夥伴','登入紀錄','付款'].every(n => !!__store.books[__store.props.centerId].sheets[n]) && __store.triggers.indexOf('dailyJob') >= 0"))
        check('預設管理員＝部署者信箱', await ev("__store.props.adminEmails") == 'owner@example.com')
        await ev("__store.props.adminEmails = 'boss@example.com'")
        await ev("adoptLegacyShop()")
        check('弘林轉成第一家店 S0001（試算表＝原本那份）', await ev("shopById_('S0001').ssId") == 'test' and await ev("__store.props.legacyShopId") == 'S0001')
        check('原本的設定搬進這家店的「系統設定」（版本號、店家資料）', await ev("(CTX = { shopId: 'S0001', ssId: 'test', shop: shopById_('S0001') }, props_().getProperty('ver') === '7' && JSON.parse(props_().getProperty('t_shop')).tagline === '中壢好味道')"))
        check('舊鑰匙網址轉入後仍可使用', (await fn('getData', 'hl7q2x9m'))['v'] is not None)
        await ev("disableLegacyKey()")
        r = await fn('getData', 'hl7q2x9m')
        check('關掉舊鑰匙後，舊網址失效', 'err' in r, r)

        # ================= 2. 註冊（統編檢查、密碼規則、Email 驗證）=================
        reg = lambda **k: ev("f => regCreate(f)", dict(dict(company='小確幸早餐店', taxId='22099131', owner='王小明', email='shop1@example.com', password='abc12345', plan='trial', agree=True), **k))
        r = await reg(taxId='12345678'); check('註冊：統編檢查碼錯誤被擋', not r['ok'] and '統編' in r['msg'], r)
        r = await reg(password='abcdefgh'); check('註冊：密碼沒有數字被擋', not r['ok'] and '數字' in r['msg'], r)
        r = await reg(agree=False); check('註冊：沒勾同意被擋', not r['ok'], r)
        r = await reg(email='bad'); check('註冊：Email 格式錯誤被擋', not r['ok'], r)
        r = await reg(); check('註冊：成功並寄出驗證碼', r['ok'] and r['mail'].startswith('sh***'), r)
        sid1 = r['id']
        r2 = await reg(); check('註冊：同統編不能重複註冊', not r2['ok'] and r2['code'] == 'exists', r2)
        pwh = await ev("s => shopById_(s).hash", sid1)
        check('密碼以雜湊儲存，不是明文', pwh and 'abc12345' not in pwh and len(pwh) == 64, pwh)
        r = await ev("authStart('22099131', 'abc12345')"); check('註冊但還沒驗證 Email：不能登入', not r['ok'] and r['code'] == 'unpaid', r)
        r = await ev("regVerify('22099131', '000000')"); check('註冊驗證碼錯誤被擋', not r['ok'], r)
        code = await otp_of('shop1@example.com')
        r = await ev("c => regVerify('22099131', c)", code)
        check('註冊驗證成功：試用 14 天開始', r['ok'] and r['status'] == 'trial' and r['expires'] == await ev("addDaysStr_(todayStr_(), 14)"), r)

        # ================= 3. 登入：統編＋密碼＋驗證碼 =================
        r = await ev("authStart('22099131', 'WRONGpass1')"); check('登入：密碼錯誤', not r['ok'] and r['code'] == 'bad' and '不正確' in r['msg'], r)
        mails0 = await ev("__store.mails.length")
        r = await ev("authStart('99999999', 'abc12345')"); check('登入：不存在的統編，回應跟密碼錯誤一樣（不洩漏）', r['msg'] == '統編或密碼不正確', r)
        check('登入：密碼錯誤不會寄出驗證碼', await ev("__store.mails.length") == mails0)
        for _ in range(4): await ev("authStart('22099131', 'WRONGpass1')")
        r = await ev("authStart('22099131', 'abc12345')")
        check('登入：連續錯 5 次後鎖定，連正確密碼也先擋', not r['ok'] and r['code'] == 'locked', r)
        await advance(0.02)   # 約 29 分鐘，鎖定 15 分鐘已過
        r = await ev("authStart('22099131', 'abc12345')"); check('登入：鎖定 15 分鐘後解除，寄出驗證碼', r['ok'], r)
        check('驗證碼寄到註冊信箱', await ev("__store.mails[__store.mails.length - 1].to") == 'shop1@example.com')
        r = await ev("authVerify('22099131', '123456', 'dev1')"); check('登入：驗證碼錯誤', not r['ok'] and r['code'] == 'badcode', r)
        code = await otp_of('shop1@example.com')
        r = await ev("c => authVerify('22099131', c, 'dev1')", code)
        check('登入成功：拿到通行證與三個網址', r['ok'] and r['token'] and 't=' in r['urls']['menu'] and r['urls']['customer'].endswith('?s=' + sid1), r)
        tok1 = r['token']
        r = await ev("c => authVerify('22099131', c, 'dev1')", code); check('驗證碼只能用一次', not r['ok'], r)
        s1 = await ev("s => shopById_(s)", sid1)
        check('第一次登入自動建立試算表與資料夾，並分享給店主（唯讀）', s1['ssId'] and s1['folderId'] and await ev("__store.shares.some(x => x.to === 'shop1@example.com' && x.role === 'viewer')"), s1)
        check('新店家的價格表是空的，不會看到弘林的品項', (await fn('getData', tok1))['v']['rows'] == [])
        r = await fn('getData', tok1 + 'x'); check('通行證被竄改：拒絕', 'err' in r, r)
        r = await fn('getData', 'garbage'); check('亂填通行證：拒絕', 'err' in r, r)
        r = await fn('getData', ''); check('沒有通行證：拒絕', 'err' in r, r)

        # ================= 4. 資料隔離 =================
        r = await fn('addItem', {'sid': 'main', 'cat': '主餐', 'name': '招牌便當', 'cols': [{'spec': '', 'price': '90'}]}, tok1)
        check('小確幸新增品項', 'err' not in r and len(r['v']['rows']) == 1, r)
        check('小確幸的品項寫進它自己的試算表', await ev("s => Object.keys(__store.books).length > 1 && __store.books[s].sheets['價格表'].data.some(r => r[2] === '招牌便當')", s1['ssId']))
        d0 = await fn('getData', 'hl7q2x9m'); check('弘林用舊鑰匙關掉後看不到', 'err' in d0)
        # 弘林用帳號登入：先用後台重設密碼（拿不到信的情況用 evaluate 直接設）
        await ev("(() => { var s = shopById_('S0001'); s.taxId = '04595257'; s.salt = 's'; s.hash = pwHash_('hongling1', 's'); saveShop_(s, ['taxId', 'salt', 'hash']); })()")
        await ev("authStart('04595257', 'hongling1')"); c = await otp_of('patricia3194299@yahoo.com.tw')
        r = await ev("c => authVerify('04595257', c, 'devH')", c)
        check('弘林用統編＋密碼＋驗證碼登入（驗證碼寄到原本的 MENU_EMAIL）', r['ok'], r)
        tokH = r['token']
        dh = (await fn('getData', tokH))['v']
        check('弘林看到自己的 20 筆品項、看不到小確幸的', len(dh['rows']) == 20 and all(x['name'] != '招牌便當' for x in dh['rows']) and dh['ver'] == 7, (len(dh['rows']), dh['ver']))
        ver1 = (await fn('reserveVersion', 'menu', tok1))['v']['no']; verH = (await fn('reserveVersion', 'menu', tokH))['v']['no']
        check('版本號各店各算各的（小確幸 V1、弘林 V8）', ver1 == 1 and verH == 8, (ver1, verH))

        # ================= 5. 授權狀態：試用 → 寬限 → 唯讀 → 停用 =================
        await ev("(() => { var s = shopById_('%s'); s.expires = addDaysStr_(todayStr_(), -3); saveShop_(s, ['expires']); })()" % sid1)
        r = await fn('setPrices', {'main|招牌便當|0': '95'}, tok1)
        check('到期 3 天內（寬限）：照常可以改價', 'err' not in r, r)
        lic = await ev("licOf_(shopById_('%s'))" % sid1); check('寬限期有提醒文字', lic['grace'] and '寬限' in lic['msg'], lic)
        await ev("(() => { var s = shopById_('%s'); s.expires = addDaysStr_(todayStr_(), -10); saveShop_(s, ['expires']); })()" % sid1)
        r = await fn('setPrices', {'main|招牌便當|0': '99'}, tok1)
        check('寬限結束後（唯讀）：不能改價，訊息說明原因', 'err' in r and '只能查看' in r['err'], r)
        r = await fn('getData', tok1); check('唯讀：仍然可以查看菜單', 'err' not in r and r['v']['rows'][0]['p'] == '95', r)
        r = await fn('addItem', {'sid': 'main', 'cat': '主餐', 'name': 'X', 'cols': [{'spec': '', 'price': '1'}]}, tok1); check('唯讀：不能新增品項', 'err' in r, r)
        r = await fn('tSaveShop', {'name': 'x'}, tok1); check('唯讀：店家工具也不能寫入', 'err' in r, r)
        r = await fn('tGetState', tok1); check('唯讀：店家工具可以查看', 'err' not in r, r)
        html = await ev("t => doGet({ parameter: { t, later: '1' } }).getContent()", tok1); check('唯讀：菜單頁仍可打開，並帶出提示', 'BRAND' in html and '只能查看' in html, html[:100])
        await ev("(() => { var s = shopById_('%s'); s.expires = addDaysStr_(todayStr_(), -120); saveShop_(s, ['expires']); })()" % sid1)
        r = await fn('getData', tok1); check('過期太久（停用）：連查看也不行', 'err' in r, r)
        html = await ev("t => doGet({ parameter: { t } }).getContent()", tok1); check('停用：開菜單頁會回到登入頁並說明', '登入' in html and 'mode":"login"' in html.replace(' ', ''), html[:80])
        r = await ev("authStart('22099131', 'abc12345')"); check('停用：不再寄驗證碼', not r['ok'] and r['code'] == 'blocked', r)

        # ================= 6. 管理後台 =================
        r = await ev("admStart('hacker@example.com')"); mails_n = await ev("__store.mails.filter(m => m.to === 'hacker@example.com').length")
        check('非管理員 Email：看起來一樣，但不會寄驗證碼', r['ok'] and mails_n == 0)
        r = await ev("admStart('boss@example.com')"); c = await otp_of('boss@example.com')
        r = await ev("c => admVerify('boss@example.com', c)", c); check('管理員驗證碼登入', r['ok'] and r['token'], r)
        adm = r['token']
        r = await fn('admOverview', tok1); check('店家通行證不能進後台', 'err' in r, r)
        ov = (await fn('admOverview', adm))['v']; check('後台列出所有店家與各狀態數量', len(ov['shops']) == 2 and sum(ov['counts'].values()) == 2, ov['counts'])
        r = (await fn('admExtend', adm, sid1, 30))['v']
        check('後台延長 30 天：停用的店家立刻恢復（改價不再被擋）', r['ok'] and (await fn('setPrices', {'main|招牌便當|0': '100'}, tok1)).get('err') is None, r)
        r = (await fn('admSetStatus', adm, sid1, 'suspended'))['v']
        check('後台停權：立刻生效', 'err' in await fn('getData', tok1))
        await fn('admSetStatus', adm, sid1, 'active')
        check('後台恢復：立刻生效', 'err' not in await fn('getData', tok1))
        r = (await fn('admSaveShop', adm, {'id': sid1, 'name': '改名店', 'owner': '王小明', 'email': 'shop1@example.com', 'plan': 'basic'}))['v']
        check('公司名稱 180 天內不能改（沒有審核說明）', not r['ok'] and r['code'] == 'locked', r)
        r = (await fn('admSaveShop', adm, {'id': sid1, 'name': '改名店', 'owner': '王小明', 'email': 'shop1@example.com', 'plan': 'basic', 'reason': '已審核變更登記'}))['v']
        check('附審核說明後可以改名，並留下紀錄', r['ok'] and await ev("cRows_('logs').some(l => l['動作'] === '改公司名稱' && String(l['備註']).indexOf('已審核變更登記') >= 0)"), r)
        r = (await fn('admSaveShop', adm, {'id': sid1, 'name': '改名店', 'owner': 'x', 'email': 'shop1@example.com', 'taxId': '04595257'}))['v']
        check('統編不同視為新客戶：不能直接改統編', not r['ok'] and '新客戶' in r['msg'], r)
        r = (await fn('admSaveShop', adm, {'name': '新開的店', 'taxId': '04595257', 'owner': 'a', 'email': 'n@example.com', 'plan': 'pro'}))['v']
        check('後台新增店家：統編已存在擋下', not r['ok'] and r['code'] == 'exists', r)
        r = (await fn('admSaveShop', adm, {'name': '新開的店', 'taxId': '53212539', 'owner': 'a', 'email': 'n@example.com', 'plan': 'pro'}))['v']
        check('後台新增店家：不產生暫時密碼、狀態待啟用', r['ok'] and 'tempPassword' not in r and r['shop']['status'] == 'pending', r)
        actm = await ev("() => { var m = __store.mails.filter(x => x.to === 'n@example.com'); return m.length ? m[m.length - 1] : null; }")
        check('後台新增店家：寄開通信（連到 ?p=activate，信裡沒有任何密碼）', r['mailed'] and actm and '?p=activate' in actm['body'] and '首次開通' in actm['body'] and '暫時密碼' not in actm['body'], actm)
        check('品牌信件：開通信有 HTML 版（官方 Logo 內嵌、按鈕），純文字版照舊', bool(actm.get('html')) and 'cid:sfdLogo' in actm['html'] and '設定密碼並登入' in actm['html'] and 'sfdLogo' in actm['imgs'] and '?p=activate' in actm['body'] and actm['name'] == '星樂創意 StarFunDea', {k: actm.get(k) for k in ('name', 'imgs')})
        check('品牌信件：HTML 版不含 <script>、寬度 600px、有頁尾說明', '<script' not in actm['html'] and 'max-width:600px' in actm['html'] and '你收到這封信' in actm['html'])
        r0 = await ev("authStart('53212539', 'anything1')"); check('首次開通前：用任何密碼都不能登入', not r0['ok'] and r0['code'] == 'bad', r0)
        await ev("pwResetStart('53212539')"); m = await ev("() => __store.mails[__store.mails.length - 1].body")
        check('首次開通：驗證碼信說明是「首次開通」、要自己設定密碼', '首次開通' in m and '客服不會知道' in m, m)
        mm = await ev("() => __store.mails[__store.mails.length - 1]")
        mlink = re.search(r'(\?ml=[0-9a-f]+)', mm['body'])
        check('品牌信件：設定密碼信是一顆「設定密碼」按鈕（連到信件連結），沒有驗證碼', mm['html'] and mlink and mlink.group(1) in mm['html'] and '設定密碼' in mm['html'] and not re.search(r'\b\d{6}\b', mm['body']), mm['body'])
        c = await otp_of('n@example.com')
        r0 = await ev("c => actDone('53212539', c, 'short', 'devN')", c); check('首次開通：密碼太簡單被擋', not r0['ok'], r0)
        c = await otp_of('n@example.com')
        r0 = await ev("c => actDone('53212539', c, 'newShop88', 'devN')", c)
        check('首次開通（待付款）：密碼設好但還不能登入，提示付款', r0['ok'] and r0.get('set') and not r0.get('token') and '付款' in r0['msg'], r0)
        check('首次開通：密碼只存雜湊', await ev("cRows_('shops').filter(x => String(x['統編']) === '53212539')[0]['密碼雜湊'] !== 'newShop88'"))
        r0 = await ev("actDone('99999998', '123456', 'newShop88', 'devN')"); check('首次開通：不存在的統編回「驗證碼不正確」（不洩漏）', not r0['ok'] and r0['code'] == 'badcode', r0)
        r = (await fn('admMarkPaid', adm, r['shop']['id'], {'plan': 'pro', 'cycle': 'month'}))['v']
        check('人工收款：開通並延長 30 天，付款紀錄＝599 元', r['ok'] and r['shop']['status'] == 'active' and r['shop']['daysLeft'] == 30 and await ev("cRows_('pays').some(p => p['金額'] === 599 && p['狀態'] === '已付款')"), r)
        r0 = await ev("authStart('53212539', 'newShop88')"); check('付款開通後：用自己設定的密碼登入（寄驗證碼）', r0['ok'], r0)

        # ================= 2b. 試營運（後台開通 30 天，全功能、不加浮水印）=================
        r = (await fn('admSaveShop', adm, {'name': '試營運小館', 'taxId': '11223344', 'owner': 'b', 'email': 'pilot@example.com', 'plan': 'pro', 'skipTaxCheck': True, 'start': 'pilot'}))['v']
        sidP = r['shop']['id']
        check('後台新增店家（試營運）：狀態試營運、到期日＝今天＋30 天', r['ok'] and r['shop']['status'] == 'pilot' and r['shop']['statusLabel'] == '試營運' and r['shop']['expires'] == await ev("addDaysStr_(todayStr_(), 30)"), r)
        check('試營運：全功能、輸出不加浮水印', await ev("s => { var l = licOf_(shopById_(s)); return l.mode === 'full' && l.watermark === false && l.label === '試營運'; }", sidP))
        m = await ev("() => __store.mails.filter(x => x.to === 'pilot@example.com').pop().body"); check('試營運開通信寫明試營運到期日', '試營運到' in m and await ev("addDaysStr_(todayStr_(), 30)") in m, m)
        await ev("pwResetStart('11223344')"); c = await otp_of('pilot@example.com')
        r0 = await ev("c => actDone('11223344', c, 'pilot2026a', 'devP')", c)
        check('試營運首次開通：設好密碼直接登入（店主通行證）', r0['ok'] and r0.get('token') and r0['role'] == 'owner' and r0['lic']['label'] == '試營運', r0)
        tokP = r0['token']
        check('試營運首次開通：自動建立店家試算表', await ev("s => !!shopById_(s).ssId", sidP))
        r0 = await ev("authStart('11223344', 'pilot2026a')"); c = await otp_of('pilot@example.com'); r0 = await ev("c => authVerify('11223344', c, 'devP2')", c)
        check('試營運：之後用統編＋密碼＋驗證碼登入', r0['ok'] and r0['role'] == 'owner', r0)
        await ev("(() => { var s = shopById_('%s'); s.expires = addDaysStr_(todayStr_(), 7); saveShop_(s, ['expires']); })()" % sidP)
        n0 = await ev("__store.mails.length"); await ev("dailyJob()")
        rm = await ev("() => __store.mails.filter(m => m.to === 'pilot@example.com').pop()")
        check('品牌信件：到期提醒有大數字天數與訂閱按鈕', rm['html'] and '試營運還有 7 天' in rm['html'] and '選方案並訂閱' in rm['html'], rm['subject'])
        check('試營運到期前 7 天提醒：寫「試營運」、資料沿用', await ev("n => __store.mails.slice(n).some(m => m.to === 'pilot@example.com' && m.body.indexOf('試營運將在 7 天後') >= 0 && m.body.indexOf('資料會直接沿用') >= 0)", n0))
        check('每日工作不會把試營運改成使用中', await ev("s => shopById_(s).status", sidP) == 'pilot')
        await ev("(() => { var s = shopById_('%s'); s.expires = addDaysStr_(todayStr_(), -1); saveShop_(s, ['expires']); })()" % sidP)
        check('試營運到期後：照一般規則進入寬限（照常使用）', await ev("s => { var l = licOf_(shopById_(s)); return l.mode === 'full' && l.grace; }", sidP))
        r = (await fn('admPilot', adm, sidP))['v']
        check('後台「開始試營運 30 天」：重新給 30 天', r['ok'] and r['shop']['status'] == 'pilot' and r['shop']['daysLeft'] == 30, r)
        r = (await fn('admSetStatus', adm, sidP, 'pilot'))['v']; check('後台改狀態可選試營運', r['ok'], r)
        r = (await fn('admMarkPaid', adm, sidP, {'plan': 'pro', 'cycle': 'year'}))['v']
        check('試營運後付款：轉成使用中，期間接在試營運之後', r['ok'] and r['shop']['status'] == 'active' and r['shop']['expires'] == await ev("addDaysStr_(addDaysStr_(todayStr_(), 30), 365)"), r)

        # ================= 2c. 後台「要求重設密碼」：不寄暫時密碼 =================
        r = (await fn('admResetPw', adm, sidP))['v']
        m = await ev("() => __store.mails.filter(x => x.to === 'pilot@example.com').pop().body")
        check('後台要求重設密碼：信裡沒有密碼、附重新設定連結', r['ok'] and '暫時密碼' not in m and '?p=activate' in m and '原本的密碼已失效' in m, m)
        r0 = await ev("authStart('11223344', 'pilot2026a')"); check('後台要求重設後：舊密碼失效', not r0['ok'], r0)
        r0 = await ev("t => authCheck(t)", tokP); check('後台要求重設後：舊裝置全部登出', not r0['ok'], r0)
        r = (await fn('admActMail', adm, sidP))['v']; check('後台重寄開通信', r['ok'] and r['mail'].startswith('p'), r)

        # ================= 7. 夥伴邀請 =================
        inv = (await fn('ownInvite', tok1, '小美'))['v']; check('店主產生邀請連結', inv['ok'] and '?invite=' in inv['link'], inv)
        r = (await fn('authInvite', 'WRONGCODE123', 'devX'))['v']; check('邀請碼錯誤被擋', not r['ok'], r)
        r = (await fn('authInvite', inv['code'], 'devMei'))['v']; check('夥伴用邀請碼加入（綁定手機）', r['ok'] and r['role'] == 'staff', r)
        tokS = r['token']
        r = (await fn('authInvite', inv['code'], 'devOther'))['v']; check('邀請碼只能用一次', not r['ok'], r)
        r = await fn('setPrices', {'main|招牌便當|0': '101'}, tokS); check('夥伴可以改價', 'err' not in r, r)
        r = await fn('ownInvite', tokS, 'x'); check('夥伴不能再邀請別人', 'err' not in r and not r['v']['ok'], r)
        r = (await fn('ownPartners', tok1))['v']; pid = r['partners'][0]['id']; check('店主看得到夥伴清單', r['ok'] and r['partners'][0]['name'] == '小美' and r['partners'][0]['status'] == '使用中', r)
        await fn('ownPartnerSet', tok1, pid, '停用')
        r = await fn('setPrices', {'main|招牌便當|0': '102'}, tokS); check('停用夥伴後，該手機「立即」不能寫入', 'err' in r and '停用' in r['err'], r)
        r = await fn('getData', tokS); check('停用夥伴後，連查看也不行', 'err' in r, r)
        await fn('ownPartnerSet', tok1, pid, '使用中')
        check('重新啟用後恢復', 'err' not in await fn('setPrices', {'main|招牌便當|0': '103'}, tokS))
        r = (await fn('ownRevokeAll', tok1))['v']
        check('「登出所有手機」：店主通行證失效，夥伴不受影響', 'err' in await fn('getData', tok1) and 'err' not in await fn('getData', tokS), r)
        await ev("authStart('22099131', 'abc12345')"); c = await otp_of('shop1@example.com')
        tok1 = (await ev("c => authVerify('22099131', c, 'dev1')", c))['token']

        # ================= 8. 通行證過期 =================
        await advance(31)
        r = await fn('getData', tok1); check('店主通行證 30 天後過期', 'err' in r and '過期' in r['err'], r)
        r = await fn('getData', tokS); check('夥伴通行證 365 天內仍有效', 'err' not in r or '到期' in r.get('err', ''), r)
        await advance(-31)

        # ================= 9. 顧客頁（?s=店家編號）=================
        html = await ev("s => doGet({ parameter: { s } }).getContent()", sid1)
        check('顧客頁顯示店家名稱、帶出店家編號', '改名店' in html and ('"sid":"%s"' % sid1) in html.replace(' ', ''), html[:100])
        check('顧客頁不含別家店（弘林）的資料', '藍綿羊' not in html and '廣州路' not in html and 'hl7q2x9m' not in html)
        r = await fn('submitWish', {'sid': sid1, 'item': '炸雞', 't0': 0}); check('顧客許願寫進小確幸的試算表', 'err' not in r and await ev("s => __store.books[s].sheets['許願池'].data.length", s1['ssId']) == 2, r)
        check('顧客許願沒寫進弘林', await ev("!__ss.sheets['許願池']"))
        r = await fn('submitWish', {'sid': 'S9999', 'item': 'x', 't0': 0}); check('店家編號不存在：拒絕', 'err' in r, r)
        r = await fn('submitWish', {'item': 'x', 't0': 0}); check('沒帶店家編號：拒絕', 'err' in r, r)
        r = await fn('getCatalog', sid1); check('顧客頁菜單只含該店品項', 'err' not in r and r['v']['cats'][0]['items'][0]['name'] == '招牌便當', r)
        html = await ev("() => doGet({ parameter: { s: 'S9999' } }).getContent()"); check('不存在的店家：顯示提示頁', '找不到' in html)
        await fn('admSetStatus', adm, sid1, 'suspended')
        html = await ev("s => doGet({ parameter: { s } }).getContent()", sid1); check('停用的店家：顧客頁顯示暫停服務', '暫時停止服務' in html and '招牌便當' not in html)
        await fn('admSetStatus', adm, sid1, 'active')

        # ================= 10. 頁面分流 =================
        html = await ev("() => doGet({ parameter: {} }).getContent()"); check('沒帶參數 → 登入頁', 'mode":"login"' in html.replace(' ', '') and '星樂創意 StarFunDea' in html)
        html = await ev("t => doGet({ parameter: { t, later: '1' } }).getContent()", tok1); check('?t=通行證 → 菜單工具（帶店名、通行證）', 'const BRAND' in html and '改名店' in html and tok1 in html)
        html = await ev("t => doGet({ parameter: { p: 'tools', t } }).getContent()", tok1); check('?p=tools&t=通行證 → 店家工具', '<h1>店家工具</h1>' in html)
        html = await ev("t => doGet({ parameter: { p: 'account', t } }).getContent()", tok1); check('?p=account&t=通行證 → 帳號頁', '帳號與夥伴' in html)
        html = await ev("() => doGet({ parameter: { invite: 'ABC' } }).getContent()"); check('?invite= → 夥伴加入頁', 'mode":"invite"' in html.replace(' ', ''))
        html = await ev("() => doGet({ parameter: { p: 'admin' } }).getContent()"); check('?p=admin → 管理後台頁', '管理後台' in html)
        html = await ev("() => doGet({ parameter: { t: 'bad.token' } }).getContent()"); check('通行證無效 → 回登入頁並顯示原因', '請重新登入' in html)

        # ================= 11. 收款通知（測試金流）=================
        await ev("__store.props.billProvider = 'test'; __store.props.testPaySecret = 'sek'")
        pay = (await fn('ownPayStart', tok1, 'pro', 'year'))['v']
        check('續訂：建立待付款，年繳＝599×10', pay['ok'] and pay['amount'] == 5990 and pay['provider'] == 'test', pay)
        sig = lambda pid, amt, st: ev("([p, a, s]) => hmacHex_([p, a, s].join('|'), 'sek')", [pid, amt, st])
        exp0 = (await ev("s => shopById_(s).expires", sid1))
        r = (await fn('payNotify', 'test', {'payId': pay['payId'], 'amount': 5990, 'status': 'paid', 'sig': 'forged'}))['v']
        check('付款通知：簽章錯誤不處理', not r['ok'] and await ev("s => shopById_(s).expires", sid1) == exp0, r)
        r = (await fn('payNotify', 'test', {'payId': pay['payId'], 'amount': 1, 'status': 'paid', 'sig': await sig(pay['payId'], 1, 'paid')}))['v']
        check('付款通知：金額不符不處理', not r['ok'] and r['msg'] == 'amount mismatch', r)
        r = (await fn('payNotify', 'test', {'payId': pay['payId'], 'amount': 5990, 'status': 'paid', 'sig': await sig(pay['payId'], 5990, 'paid')}))['v']
        exp1 = await ev("s => shopById_(s).expires", sid1)
        check('付款通知：簽章正確 → 延長 365 天、方案改為專業版', r['ok'] and r['paid'] and exp1 > exp0 and await ev("s => daysBetween_(arguments[0], arguments[1])", None) is None if False else (r['ok'] and r['paid'] and await ev("([a, b]) => daysBetween_(a, b)", [exp0, exp1]) == 365 and await ev("s => shopById_(s).plan", sid1) == 'pro'), (r, exp0, exp1))
        r = (await fn('payNotify', 'test', {'payId': pay['payId'], 'amount': 5990, 'status': 'paid', 'sig': await sig(pay['payId'], 5990, 'paid')}))['v']
        check('付款通知重複送達：只算一次', r['ok'] and r['already'] and await ev("s => shopById_(s).expires", sid1) == exp1, r)
        check('寄出收款確認信', await ev("__store.mails.some(m => m.to === 'shop1@example.com' && m.subject.indexOf('收到款項') >= 0)"))
        pm = await ev("() => __store.mails.filter(m => m.to === 'shop1@example.com' && m.subject.indexOf('收到款項') >= 0).pop()")
        check('品牌信件：收款確認列出金額（含稅）與付款編號', 'NT$' in pm['html'] and '含稅' in pm['html'] and '付款編號' in pm['html'], pm['subject'])
        r = await ev("() => doPost({ postData: { contents: JSON.stringify({ action: 'login', taxId: '22099131', password: 'bad' }) } }).getContent()")
        check('doPost JSON API：登入失敗回 JSON', json.loads(r)['ok'] is False)

        # ================= 12. 每日工作：到期提醒 =================
        await ev("(() => { var s = shopById_('%s'); s.expires = addDaysStr_(todayStr_(), 7); saveShop_(s, ['expires']); })()" % sid1)
        n0 = await ev("__store.mails.length"); await ev("dailyJob()")
        check('到期前 7 天寄提醒信', await ev("n => __store.mails.slice(n).some(m => m.to === 'shop1@example.com' && m.body.indexOf('7 天') >= 0)", n0))
        n1 = await ev("__store.mails.length"); await ev("dailyJob()")
        check('同一天重跑不會重複寄', await ev("__store.mails.length") == n1)

        # ================= 13. 忘記密碼 =================
        await ev("pwResetStart('22099131')"); c = await otp_of('shop1@example.com')
        r = await ev("c => pwResetDone('22099131', c, 'short')", c); check('重設密碼：新密碼太簡單被擋', not r['ok'], r)
        c = await otp_of('shop1@example.com')
        r = await ev("c => pwResetDone('22099131', c, 'newpass99')", c)
        check('重設密碼成功，舊密碼失效、新密碼可用', r['ok'] and (await ev("authStart('22099131', 'abc12345')"))['ok'] is False and (await ev("authStart('22099131', 'newpass99')"))['ok'] is True, r)

        # ================= 14. 瀏覽器操作：登入頁 → 管理後台 → 帳號頁 =================
        await H.evaluate("p => openPage(p)", {})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true')
        await fr.fill('#taxId', '22099131'); await fr.fill('#pw', 'wrongpw1'); await fr.click('#send')
        await fr.wait_for_function("document.querySelector('#msg').textContent.includes('不正確')")
        check('登入頁：密碼錯誤顯示提示', True)
        await ev("failClear_('t22099131')")
        await fr.fill('#pw', 'newpass99'); await fr.click('#send')
        await fr.wait_for_selector('#s2:not(.hide)')
        check('登入頁：密碼正確後顯示「登入信已寄到」與遮罩信箱，沒有驗證碼欄位', 'sh***' in await fr.inner_text('#mailTo') and await fr.locator('#otp').count() == 0)
        body = await ev("__store.mails[__store.mails.length - 1].body")
        check('登入信：只有「確認登入」連結，信裡沒有驗證碼', '?ml=' in body and not re.search(r'\b\d{6}\b', body), body)
        await fr.evaluate("window.__go = []; goTop = u => window.__go.push(u); true")
        mid = await link_of('shop1@example.com')
        r = await ev("id => mlUse(id, 'devPhone')", mid)          # 店主在手機上按了信裡的按鈕
        check('信件連結：按下就登入（不用輸入驗證碼）', r['ok'] and r['kind'] == 'login' and r['token'], r)
        await fr.wait_for_function("window.__go.length > 0", timeout=15000)
        go = await fr.evaluate("window.__go[0]")
        check('登入頁：連結按下後，原本的頁面自動登入並跳到主畫面', 'p=home' in go and 't=' in go, go)
        saved = await fr.evaluate("localStorage.getItem('hl-token')")
        check('登入頁：通行證存在手機（下次自動續登）', bool(saved))
        await H.evaluate("p => openPage(p)", {})
        fr = H.child_frames[0]
        await fr.wait_for_selector('#v-back:not(.hide)', timeout=8000)
        check('再次打開登入頁：自動續登，不用再輸入', '改名店' in await fr.inner_text('#backName'))

        # 夥伴加入頁
        inv2 = (await fn('ownInvite', saved, '阿華'))['v']
        await H.evaluate("p => openPage(p)", {'invite': inv2['code']})
        fr = H.child_frames[0]; await fr.evaluate("localStorage.removeItem('hl-token')")
        await H.evaluate("p => openPage(p)", {'invite': inv2['code']})
        fr = H.child_frames[0]
        await fr.wait_for_selector('#v-join:not(.hide)'); await fr.click('#join')
        await fr.wait_for_selector('#v-back:not(.hide)')
        check('夥伴加入頁：按「加入」就綁定這支手機', '夥伴' in await fr.inner_text('#backMsg') and await fr.is_hidden('#goAcct'))

        # 帳號頁
        await H.evaluate("p => openPage(p)", {'p': 'account', 't': saved})
        fr = H.child_frames[0]
        await fr.wait_for_function("document.querySelector('#lic').textContent.includes('改名店')")
        await fr.fill('#pName', '小王'); await fr.click('#inv')
        await fr.wait_for_selector('#invBox:not(.hide)')
        check('帳號頁：產生邀請連結並顯示', '?invite=' in await fr.inner_text('#invBox'))
        check('帳號頁：夥伴清單列出夥伴', '阿華' in await fr.inner_text('#pts') and '小王' in await fr.inner_text('#pts'))
        await fr.click('#pts [data-id][data-st="停用"]')
        await fr.wait_for_function("document.querySelector('#pts').textContent.includes('停用')")
        check('帳號頁：按「停用」夥伴立刻停用', True)
        await fr.wait_for_selector('#nfBox:not([hidden])')
        check('帳號頁：通知信開關分成「馬上寄」7 種與「定時寄」4 種，定時的可分開設定寄給我／寄給員工', await fr.locator('#nfNow .nf-row').count() == 7 and await fr.locator('#nfAuto .nf-row').count() == 4 and await fr.locator('#nfAuto [data-nf=handEmp]').count() == 1 and await fr.locator('#nfBox input:not(:checked)').count() == 0)
        await fr.uncheck('#nfBox [data-nf=knock]'); await fr.uncheck('#nfBox [data-nf=orderEmp]'); await fr.click('#cSave')
        await fr.wait_for_function("document.querySelector('#mC').textContent.includes('已儲存')")
        g = (await fn('ownCfgGet', saved))['v']
        check('帳號頁：取消勾選後儲存，那兩類就關掉', sorted(g['cfg']['notifyOff']) == ['knock', 'orderEmp'], g['cfg'].get('notifyOff'))
        await fr.check('#nfBox [data-nf=knock]'); await fr.check('#nfBox [data-nf=orderEmp]'); await fr.click('#cSave'); await page.wait_for_timeout(800)
        check('帳號頁：再勾回來就恢復', (await fn('ownCfgGet', saved))['v']['cfg']['notifyOff'] == [])

        # 管理後台頁
        await H.evaluate("p => openPage(p)", {'p': 'admin'})
        fr = H.child_frames[0]
        await fr.fill('#aMail', 'boss@example.com'); await fr.click('#aSend')
        await fr.wait_for_selector('#aVerify:not(.hide)')
        await fr.fill('#aOtp', await otp_of('boss@example.com')); await fr.click('#aVerify')
        await fr.wait_for_selector('#main:not(.hide)')
        try:
            await fr.wait_for_function("document.querySelectorAll('#rows tr.shop').length >= 3", timeout=8000)
        except Exception:
            print('DBGADMIN', (await fr.inner_text('body'))[:600].replace(chr(10), ' | '))
            raise
        check('管理後台頁：登入後列出所有店家', '改名店' in await fr.inner_text('#rows') and '弘林早午餐' in await fr.inner_text('#rows'))
        for _try in range(3):
            await fr.click('#rows tr.shop >> text=改名店')
            await page.wait_for_timeout(1200)
            if '改名店' in await fr.inner_text('#dName'): break
        try:
            await fr.wait_for_function("document.querySelector('#dName').textContent.includes('改名店')", timeout=8000)
        except Exception:
            print('DBGADMIN', await fr.inner_text('#dMsg'), '|', await fr.inner_text('#dName'), '|', await fr.inner_text('#rows'))
            raise
        await fr.click('[data-ext="30"]')
        await fr.wait_for_function("document.querySelector('#dMsg').textContent.includes('完成')")
        check('管理後台頁：按「延長 30 天」成功', True)
        await fr.fill('#q', '弘林')
        check('管理後台頁：搜尋店名', await fr.locator('#rows tr.shop').count() == 1)

        # ================= 15. 店家資料與自訂分類（新店家的菜單不是弘林的）=================
        await ev("authStart('22099131', 'newpass99')"); c = await otp_of('shop1@example.com')
        tok1 = (await ev("c => authVerify('22099131', c, 'dev1')", c))['token']
        r = (await fn('ownCfgSave', tok1, {'name': '小確幸', 'address': '台北市信義路 1 號', 'phone': '02-1234', 'hours': '07:00–14:00', 'openDays': [1, 2, 3, 4, 5], 'lineUrl': 'https://lin.ee/abcdef', 'minDays': 2, 'channels': ['Uber Eats', '現場']}))['v']
        check('店家資料：儲存營業日、LINE 網址、預訂天數', r['ok'] and r['cfg']['openDays'] == [1, 2, 3, 4, 5] and r['cfg']['minDays'] == 2, r)
        r = await fn('ownCfgSave', tok1, {'name': 'x', 'openDays': []}); check('店家資料：沒有營業日被擋', 'err' in r, r)
        r = await fn('ownCfgSave', tok1, {'name': 'x', 'openDays': [1], 'lineUrl': 'javascript:alert(1)'}); check('店家資料：網址只接受 https', 'err' in r, r)
        r = await fn('ownCfgSave', tokS, {'name': 'x', 'openDays': [1]}); check('店家資料：夥伴不能改', 'err' in r or not r['v']['ok'], r)
        # 通知信開關：關掉的那一類就不寄；沒填通知信箱就寄登入信箱
        base = {'name': '小確幸', 'address': '台北市信義路 1 號', 'phone': '02-1234', 'hours': '07:00–14:00', 'openDays': [1, 2, 3, 4, 5], 'lineUrl': 'https://lin.ee/abcdef', 'minDays': 2, 'channels': ['Uber Eats', '現場']}
        g = (await fn('ownCfgGet', tok1))['v']
        check('通知信：店主看得到 11 種通知（顧客、人員、排程）', len(g['notifyTypes']) == 11 and g['cfg']['notifyOff'] == [] and any(x.get('emp') == 'orderEmp' for x in g['notifyTypes']), g.get('notifyTypes'))
        r = (await fn('ownCfgSave', tok1, dict(base, notifyOff=['wish', 'bogus', 'handEmp', 'wish'])))['v']
        check('通知信：只存認得的類別、不重複', r['cfg']['notifyOff'] == ['wish', 'handEmp'], r['cfg'].get('notifyOff'))
        nm = await ev("__store.mails.length")
        r = await fn('submitWish', {'sid': sid1, 'item': '蛋餅', 't0': 0})
        check('通知信：關掉「顧客許願」→ 許願照樣收到，但不寄信', 'err' not in r and await ev("__store.mails.length") == nm, r)
        r = (await fn('ownCfgSave', tok1, base))['v']
        check('通知信：沒帶開關的儲存不會清掉原本的設定', r['cfg']['notifyOff'] == ['wish', 'handEmp'], r['cfg'].get('notifyOff'))
        await fn('ownCfgSave', tok1, dict(base, notifyOff=[]))
        nm = await ev("__store.mails.length")
        await fn('submitWish', {'sid': sid1, 'item': '蛋餅', 't0': 0})
        ms = await ev("n => __store.mails.slice(n)", nm)
        check('通知信：打開後寄出；沒填通知信箱就寄到登入信箱，主旨用自己的店名', len(ms) == 1 and ms[0]['to'] == 'shop1@example.com' and '【小確幸】' in ms[0]['subject'] and '弘林' not in ms[0]['subject'], ms)
        html = await ev("s => doGet({ parameter: { s } }).getContent()", sid1)
        check('顧客頁帶出新店的地址、營業日設定', '台北市信義路 1 號' in html and '"openDays":[1,2,3,4,5]' in html.replace(' ', ''))
        secs = (await fn('saveSections', [{'id': 'main', 't': '便當', 'cols': ['價格']}, {'id': 'drink', 't': '飲料', 'cols': ['中杯', '大杯']}], tok1))['v']
        check('自訂分類：改名、刪掉「點心」（沒有品項可以刪）', secs['ok'] and [s['t'] for s in secs['sections']] == ['便當', '飲料'], secs)
        r = await fn('saveSections', [{'id': 'drink', 't': '飲料', 'cols': ['中杯']}], tok1)
        check('自訂分類：分類裡還有品項不能刪（招牌便當在 main）', 'err' in r and '品項' in r['err'], r)
        r = await fn('saveSections', [{'id': 'main', 't': '便當', 'cols': ['價格']}, {'id': 'main', 't': '重複', 'cols': ['價格']}], tok1); check('自訂分類：代碼重複被擋', 'err' in r, r)
        r = await fn('saveSections', [{'id': 'main', 't': '便當', 'cols': []}], tok1); check('自訂分類：沒有規格欄被擋', 'err' in r, r)
        r = await fn('saveSections', [{'id': 'main', 't': '便當', 'cols': ['價格']}], tokS); check('自訂分類：夥伴不能改', 'err' in r, r)

        await H.evaluate("p => openPage(p)", {'t': tok1})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        names = await fr.evaluate("[...document.querySelectorAll('.sec .sec-h h2')].map(x => x.textContent)")
        check('菜單工具：用新店的分類，不是弘林的', names == ['便當', '飲料'], names)
        check('菜單工具：顯示新店的店名', '小確幸' in await fr.inner_text('#brandTop') or '改名店' in await fr.inner_text('#brandTop'))
        sh = await fr.evaluate("sheetHTML('menu', 'V1')")
        check('A3 菜單：只有新店的品項與資料，沒有弘林字樣', '招牌便當' in sh and '台北市信義路 1 號' in sh and '弘林' not in sh and '藍綿羊' not in sh and 'class="qri"' in sh, sh[:100])
        check('A3 菜單：LINE QR 由新店的網址產生（自寫編碼器）', await fr.evaluate("(() => { const s = qrSvg('https://lin.ee/abcdef'); return s.indexOf('<path') > 0 && s.length > 500; })()"))
        check('菜單工具：店長看得到「分類」「帳號」按鈕', await fr.is_visible('#secLink') and await fr.is_visible('#acctLink'))
        await fr.click('#secLink')
        await fr.wait_for_selector('#secModal.open')
        await fr.fill('#secList [data-i="1"] .s-t', '冰飲')
        await fr.click('#secAdd')
        await fr.fill('#secList [data-i="2"] .s-t', '甜點'); await fr.fill('#secList [data-i="2"] .s-c', '價格')
        await fr.click('#secSave')
        await page.wait_for_timeout(600)
        saved = await ev("s => JSON.parse(CTX.shopId ? '[]' : '[]') && 1", None)
        got = (await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('sections')); }", tok1))
        check('菜單工具：分類編輯視窗可改名、新增，儲存後存到伺服器', [s['t'] for s in got] == ['便當', '冰飲', '甜點'], got)
        await fn('ownPartnerSet', tok1, pid, '使用中')
        await H.evaluate("p => openPage(p)", {'t': tokS})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('夥伴開菜單工具：看不到「分類」「帳號」按鈕', await fr.is_hidden('#secLink') and await fr.is_hidden('#acctLink'))

        # ================= 16. 測試帳號（免驗證碼）=================
        sid_t = await ev("createTestShop()")
        check('建立測試店家：統編 90039370、使用中、已建好試算表', await ev("s => { var x = shopById_(s); return x.taxId === '90039370' && x.status === 'active' && !!x.ssId && x.verified; }", sid_t))
        check('測試帳號清單已開啟（只有這一個統編）', await ev("__store.props.testAccounts") == '90039370')
        n0 = await ev("__store.mails.length")
        r = await ev("authStart('90039370', 'Wrong12345')"); check('測試帳號：密碼錯誤仍然擋', not r['ok'], r)
        r = await ev("authVerify('90039370', '000000', 'devT')"); check('測試帳號：沒先通過密碼就直接驗證，仍然擋', not r['ok'], r)
        r = await ev("authStart('90039370', 'Test90039370')"); check('測試帳號：密碼正確直接通過、不寄信', r['ok'] and r.get('bypass') and await ev("__store.mails.length") == n0, r)
        r = await ev("authVerify('90039370', '', 'devT')"); check('測試帳號：驗證碼隨便填（空白也行）就登入成功', r['ok'] and r['token'], r)
        tokT = r['token']; check('測試帳號登入後可以讀寫自己的菜單', 'err' not in await fn('addItem', {'sid': 'main', 'cat': '主餐', 'name': '測試品', 'cols': [{'spec': '', 'price': '10'}]}, tokT))
        await ev("authStart('22099131', 'newpass99')"); r = await ev("authVerify('22099131', '000000', 'devY')")
        check('其他店家不受影響：仍然要真的驗證碼', not r['ok'] and r['code'] == 'badcode', r)
        await ev("disableTestMode()")
        nb = await ev("__store.mails.length")
        r = await ev("authStart('90039370', 'Test90039370')"); check('關閉測試模式後：恢復寄驗證碼', r['ok'] and not r.get('bypass') and await ev("__store.mails.length") == nb + 1, r)

        # ================= 16b. 弘林早午餐專用帳號 =================
        check('弘林專用帳號：預設統編 00000000、負責人「弘林早午餐」', await ev("HONGLING_ACCOUNT.taxId === '00000000' && HONGLING_ACCOUNT.owner === '弘林早午餐' && !HONGLING_ACCOUNT.email && taxIdOk_('00000000')"))
        tx = await ev("(() => { for (var n = 27182800; n < 27183100; n++) { var s = String(n); if (taxIdOk_(s) && !shopByTaxId_(s)) return s; } })()")
        r = await ev("t => seedHonglingShop({ taxId: t, owner: HONGLING_ACCOUNT.owner, email: HONGLING_ACCOUNT.email })", tx)   # 00000000 後面的測試要用，這裡換一個統編跑同一套預設
        d = await ev("s => { var x = shopById_(s); return { owner: x.owner, email: x.email }; }", r['id'])
        check('弘林專用帳號：登入 Email 沒填時用 MENU_EMAIL（原本收菜單 PDF 的信箱）', d['owner'] == '弘林早午餐' and d['email'] == await ev("MENU_EMAIL.toLowerCase()") and r['added'] > 100 and not r['legacy'], (r, d))
        r = await ev("seedHonglingShop({ taxId: '04595257', owner: '林老闆', email: 'legacy@example.com' })")
        check('弘林專用帳號：統編是已轉入的原單店時，沿用那家店、不重匯菜單', r['id'] == 'S0001' and r['legacy'] and r['added'] == 0 and r['updated'] == 0 and await ev("shopById_('S0001').email") == 'legacy@example.com', r)
        n0 = await ev("__store.mails.length")
        r = await ev("seedHonglingShop({ taxId: '24536806', owner: '林先生', email: 'Hongling@Example.com', skipTaxCheck: true })")
        sid_h = r['id']
        info = await ev("""s => { var x = shopById_(s); return withShop_(x, function () {
            var cfg = JSON.parse(props_().getProperty('cfg') || '{}'), d = getData_();
            return { taxId: x.taxId, name: x.name, status: x.status, plan: x.plan, email: x.email, owner: x.owner, ss: !!x.ssId, folder: !!x.folderId, hash: x.hash,
              cfgName: cfg.name, addr: cfg.address, line: cfg.lineId, onb: props_().getProperty('onboarded'), rows: d.rows.length,
              star: d.rows.filter(function (q) { return q.star; }).length, priced: d.rows.filter(function (q) { return q.p !== '' && q.p != null; }).length }; }); }""", sid_h)
        print('  [弘林專用帳號]', info, r)
        check('弘林專用帳號：建立正式店家（使用中、專業版、Email 轉小寫）', info['taxId'] == '24536806' and info['name'] == '弘林早午餐' and info['status'] == 'active' and info['plan'] == 'pro' and info['email'] == 'hongling@example.com' and info['owner'] == '林先生', info)
        check('弘林專用帳號：建好資料夾與試算表，程式裡不放密碼', info['ss'] and info['folder'] and not info['hash'], info)
        check('弘林專用帳號：店家資料用原本的弘林設定，略過設定精靈', info['cfgName'] == '弘林早午餐' and '廣州路' in info['addr'] and info['line'] == '@322kwvxu' and info['onb'] == '1', info)
        nitems = await ev("ITEMS.length"); ndish = await ev("new Set(ITEMS.map(function (x) { return x[0].split('|').slice(0, 2).join('|'); })).size")
        check('弘林專用帳號：匯入全部菜單品項（每一格價格、還沒定價的格子、推薦都在）', info['rows'] == nitems and r['added'] == ndish and info['star'] > 0 and info['priced'] > nitems * 0.8, (info['rows'], nitems, r))
        check('弘林專用帳號：寄出開通信（請店主自己設定密碼）', r['mailed'] and any(m.get('to') == 'hongling@example.com' and '設定登入密碼' in m.get('subject', '') for m in await ev("__store.mails.slice(%d)" % n0)), await ev("__store.mails.slice(%d)" % n0))
        check('弘林專用帳號：不是測試帳號（登入仍要驗證碼）', '24536806' not in (await ev("__store.props.testAccounts || ''")))
        r2 = await ev("seedHonglingShop({ taxId: '24536806', owner: '林先生', email: 'hongling@example.com', skipTaxCheck: true })")
        check('弘林專用帳號：重複執行不會建第二家店、不會重複匯入品項、不動已有的價格', r2['id'] == sid_h and r2['added'] == 0 and r2['updated'] == 0 and await ev("allShops_().filter(function (x) { return x.taxId === '24536806'; }).length") == 1, r2)

        # ================= 16c. 信件連結：登入／註冊／設定密碼都不用輸入驗證碼 =================
        await ev("failClear_('t22099131')")
        r = await ev("authStart('22099131', 'newpass99')"); poll = r['poll']
        check('連結登入：寄信後回傳輪詢編號', r['ok'] and len(poll) == 32, r)
        m1 = await link_of('shop1@example.com')
        r = await ev("authStart('22099131', 'newpass99')"); poll2 = r['poll']; m2 = await link_of('shop1@example.com')
        r = await ev("id => mlUse(id, 'devA')", m1); check('連結登入：再寄一次後，舊連結失效', not r['ok'] and '重新寄' in r['msg'], r)
        r = await ev("p => mlPoll(p, 'devB')", poll2); check('連結登入：還沒按連結時，原頁面繼續等', r['ok'] and r.get('wait'), r)
        r = await ev("id => mlUse(id, 'devA')", m2); check('連結登入：按下最新的連結就登入', r['ok'] and r['token'] and r['kind'] == 'login', r)
        r = await ev("id => mlUse(id, 'devA')", m2); check('連結登入：同一個連結只能用一次', not r['ok'], r)
        r = await ev("p => mlPoll(p, 'devB')", poll); check('連結登入：別的頁面（舊的輪詢編號）拿不到通行證', r.get('wait'), r)
        r = await ev("p => mlPoll(p, 'devB')", poll2); check('連結登入：原頁面拿到自己的通行證', r['ok'] and r['token'] and r['shop']['name'], r)
        r = await ev("p => mlPoll(p, 'devB')", poll2); check('連結登入：原頁面的通行證只發一次', r.get('wait'), r)
        r = await ev("mlUse('', 'x')"); check('連結登入：亂填連結被擋', not r['ok'] and r['code'] == 'gone', r)
        r = await ev("authStart('22099131', 'newpass99')"); m3 = await link_of('shop1@example.com')
        await advance(0.0075)   # 約 11 分鐘
        await ev("Object.keys(__store.cache).forEach(k => { if (k.indexOf('ml') === 0 || k.indexOf('otp:') === 0) delete __store.cache[k]; })")   # 模擬快取過期
        r = await ev("id => mlUse(id, 'devA')", m3); check('連結登入：超過 10 分鐘連結失效，提示重新寄', not r['ok'] and '10 分鐘' in r['msg'], r)
        # 註冊：按信裡的連結完成 Email 驗證，原頁面也會往下一步
        rtax = await ev("(() => { for (var n = 31415900; n < 31416200; n++) { var s = String(n); if (taxIdOk_(s) && !shopByTaxId_(s)) return s; } })()")
        r = await reg(taxId=rtax, email='link@example.com', company='連結測試店')
        rb = await ev("__store.mails[__store.mails.length - 1]")
        check('註冊：寄出「完成 Email 驗證」連結，信裡沒有驗證碼', rb['to'] == 'link@example.com' and '?ml=' in rb['body'] and not re.search(r'\\b\\d{6}\\b', rb['body']), rb)
        r2 = await ev("id => mlUse(id, 'devR')", await link_of('link@example.com'))
        check('註冊：按連結就完成驗證，試用開始', r2['ok'] and r2['kind'] == 'reg' and r2['status'] == 'trial', r2)
        r3 = await ev("p => mlPoll(p, 'devR2')", r['poll'])
        check('註冊：原本的註冊頁也收到「驗證完成」', r3['ok'] and r3['kind'] == 'reg' and r3['status'] == 'trial' and r3['taxId'] == rtax, r3)
        # 設定密碼：連結打開先要新密碼，設好才作廢
        r = await ev("pwResetStart('22099131')"); pp = r['poll']; mr = await link_of('shop1@example.com')
        r = await ev("id => mlUse(id, 'devC')", mr); check('設定密碼連結：先請使用者輸入新密碼', r['ok'] and r['need'] == 'pw' and r['name'], r)
        r = await ev("id => mlResetDone(id, 'short', 'devC')", mr); check('設定密碼連結：密碼太簡單被擋，連結還能用', not r['ok'] and r['code'] == 'bad', r)
        r = await ev("id => mlResetDone(id, 'linkPass77', 'devC')", mr); check('設定密碼連結：設好就登入', r['ok'] and r['token'], r)
        r = await ev("id => mlResetDone(id, 'linkPass88', 'devC')", mr); check('設定密碼連結：用過就失效', not r['ok'], r)
        r = await ev("p => mlPoll(p, 'devD')", pp); check('設定密碼：原頁面也自動登入', r['ok'] and r['token'], r)
        check('設定密碼：新密碼生效', (await ev("authStart('22099131', 'linkPass77')"))['ok'] and not (await ev("authStart('22099131', 'newpass99')"))['ok'])

        # ================= 17. AI 協助建立菜單初稿 =================
        sid_n = (await fn('admSaveShop', adm, {'name': 'AI 小吃店', 'taxId': '04595257'.replace('04595257', '16078503'), 'owner': 'a', 'email': 'ai@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_n, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_n)
        tokN = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_n)
        PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN); check('AI 預留功能：預設關閉（還沒開放）', 'err' in r and '還沒開放' in r['err'], r)
        r = await fn('aiMenuApply', {'sections': [{'title': 'x', 'columns': ['價格'], 'items': [{'name': 'y', 'prices': [1]}]}]}, tokN); check('AI 預留功能：關閉時套用也被擋', 'err' in r and '還沒開放' in r['err'], r)
        await ev("__store.props.aiEnabled = '1'")
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN); check('AI：沒設定金鑰時，提示管理員要先設定', 'err' in r and 'anthropicKey' in r['err'], r)
        await ev("__store.props.anthropicKey = 'sk-test-key'")
        DRAFT = {'sections': [
            {'title': '飲料', 'columns': ['中杯', '大杯'], 'note': '', 'items': [
                {'name': '紅茶', 'prices': [25, 30], 'star': False}, {'name': '鮮奶茶|特調', 'prices': [45.6, None], 'star': True},
                {'name': '紅茶', 'prices': [1, 1]}, {'name': '<b>壞</b>', 'prices': [-5, 99999]}]},
            {'title': '便當', 'columns': ['價格'], 'note': '附湯', 'items': [{'name': '排骨便當', 'prices': [100]}, {'name': '新品便當', 'prices': [None]}]}],
            'warnings': ['鮮奶茶大杯的價格看不清楚']}
        await ev("d => { __store.fetchReply = { code: 200, body: { stop_reason: 'tool_use', content: [{ type: 'text', text: 'ok' }, { type: 'tool_use', name: 'menu_draft', input: d }] } }; }", DRAFT)
        r = await fn('aiMenuDraft', {'mime': 'image/gif', 'b64': PNG}, tokN); check('AI：不支援的檔案格式被擋', 'err' in r, r)
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': ''}, tokN); check('AI：空檔案被擋', 'err' in r, r)
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokS); check('AI：夥伴不能用', 'err' in r, r)
        r = (await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN))['v']
        d = r['draft']
        check('AI：回傳初稿（2 個分類），並清理資料（取整數、負數與過大價格歸 null、去掉 <>、重複品項合併、| 換成 ／）',
              r['ok'] and len(d['sections']) == 2 and [i['name'] for i in d['sections'][0]['items']] == ['紅茶', '鮮奶茶／特調', 'b壞/b'] and d['sections'][0]['items'][1]['prices'] == [46, None]
              and d['sections'][0]['items'][2]['prices'] == [None, 9999] and d['warnings'] == ['鮮奶茶大杯的價格看不清楚'], d)
        log = await ev("__store.fetchLog[__store.fetchLog.length - 1]")
        body = json.loads(log['opts']['payload'])
        check('AI：呼叫 Claude API（網址、金鑰、版本、模型、強制使用工具、圖片 base64、繁中指示）',
              log['url'] == 'https://api.anthropic.com/v1/messages' and log['opts']['headers']['x-api-key'] == 'sk-test-key' and log['opts']['headers']['anthropic-version'] == '2023-06-01'
              and body['model'] == 'claude-sonnet-5-5' and body['tool_choice']['name'] == 'menu_draft' and body['messages'][0]['content'][0]['source']['data'] == PNG and '新台幣' in body['messages'][0]['content'][1]['text'], log['url'])
        check('AI：金鑰只在伺服器，不會出現在回傳給前端的資料裡', 'sk-test-key' not in json.dumps(r))
        await ev("__store.fetchReply = { code: 401, body: { error: { message: 'invalid x-api-key' } } }")
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN); check('AI：金鑰無效時顯示好懂的訊息', 'err' in r and '金鑰無效' in r['err'], r)
        await ev("__store.fetchReply = { code: 529, body: {} }")
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN); check('AI：服務忙碌時提示稍後再試', 'err' in r and '忙碌' in r['err'], r)
        await ev("__store.fetchReply = { code: 200, body: { content: [{ type: 'text', text: 'sorry' }] } }")
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN); check('AI：沒辨識出內容時提示換照片', 'err' in r and '更清楚' in r['err'], r)
        await ev("d => { __store.fetchReply = { code: 200, body: { content: [{ type: 'tool_use', name: 'menu_draft', input: d }] } }; }", DRAFT)
        await ev("(() => { var c = CacheService.getScriptCache(); c.put('ai:%s:' + todayStr_(), '30', 600); })()" % sid_n)
        r = await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN); check('AI：每家店每天有辨識次數上限', 'err' in r and '用完' in r['err'], r)
        await ev("(() => CacheService.getScriptCache().remove('ai:%s:' + todayStr_()))()" % sid_n)

        # 套用
        draft = (await fn('aiMenuDraft', {'mime': 'image/png', 'b64': PNG}, tokN))['v']['draft']
        r = await fn('aiMenuApply', {'sections': []}, tokN); check('AI 套用：沒有分類被擋', 'err' in r, r)
        r = await fn('aiMenuApply', draft, tokS); check('AI 套用：夥伴不能用', 'err' in r, r)
        r = (await fn('aiMenuApply', draft, tokN))['v']
        check('AI 套用（空菜單）：用初稿的分類取代預設分類，建立 5 個品項', r['ok'] and r['added'] == 5 and [s['t'] for s in r['sections']] == ['飲料', '便當'], r)
        rows = await ev("s => { var sh = __store.books[shopById_(s).ssId].sheets['價格表']; return sh.data.slice(5).filter(r => r[0]); }", sid_n)
        keys = [x[0] for x in rows]
        check('AI 套用：價格表列正確（多規格沒價格＝不建立；單一價格沒價格＝建立空白列；推薦星號）',
              'sa|紅茶|0' not in keys and any(k.endswith('|紅茶|0') for k in keys) and not any(k.endswith('|鮮奶茶／特調|1') for k in keys)
              and any(x[2] == '鮮奶茶／特調' and x[4] == 46 and x[7] is True for x in rows) and any(x[2] == '新品便當' and x[4] in ('', None) for x in rows) and any(x[2] == '排骨便當' and x[4] == 100 and x[3] == '' for x in rows), rows)
        dn = (await fn('getData', tokN))['v']
        check('AI 套用：菜單工具讀得到新品項', len(dn['rows']) == len(rows) and any(x['name'] == '排骨便當' for x in dn['rows']), len(dn['rows']))
        draft2 = json.loads(json.dumps(draft)); draft2['sections'].append({'title': '甜點', 'columns': ['價格'], 'note': '', 'items': [{'name': '布丁', 'prices': [60]}]})
        r = (await fn('aiMenuApply', draft2, tokN))['v']
        check('AI 套用（已有品項）：重複的品項略過、只新增新的分類與品項', r['added'] == 1 and r['skipped'] == 5 and [s['t'] for s in r['sections']] == ['飲料', '便當', '甜點'], r)
        check('AI 套用：寫入修改紀錄', await ev("s => __store.books[shopById_(s).ssId].sheets['修改紀錄'].data.some(r => String(r[4]).indexOf('AI 匯入菜單') >= 0)", sid_n))
        r = await fn('aiMenuApply', draft, tokN); check('AI 套用：再套一次同樣的初稿不會重複建立', r['v']['added'] == 0 and r['v']['skipped'] == 5, r)

        # 瀏覽器操作：上傳 → 檢視初稿 → 修改 → 儲存
        sid_u = (await fn('admSaveShop', adm, {'name': 'UI 測試店', 'taxId': '53212539'.replace('53212539', '82756911'), 'owner': 'a', 'email': 'u@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_u, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_u)
        tokU = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_u)
        await ev("d => { __store.fetchReply = { code: 200, body: { content: [{ type: 'tool_use', name: 'menu_draft', input: d }] } }; }", DRAFT)
        await ev("__store.props.aiEnabled = '0'")
        await H.evaluate("p => openPage(p)", {'t': tokU})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('AI 預留功能：關閉時菜單工具看不到按鈕', await fr.is_hidden('#aiBtn'))
        await ev("__store.props.aiEnabled = '1'")
        await H.evaluate("p => openPage(p)", {'t': tokU})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('AI 介面：開放後店長看得到「上傳菜單」按鈕', await fr.is_visible('#aiBtn'))
        png = os.path.join(tempfile.gettempdir(), 'menu_up.png')
        from PIL import Image as _I
        _I.new('RGB', (300, 200), (255, 250, 240)).save(png)
        await fr.click('#aiBtn'); await fr.wait_for_selector('#aiModal.open')
        await fr.set_input_files('#aiFile', png)
        await fr.click('#aiRun')
        await fr.wait_for_selector('#ai2', state='visible', timeout=15000)
        check('AI 介面：辨識後顯示可編輯的初稿（2 個分類、警告提示）', await fr.locator('#aiList [data-s]').count() == 2 and '看不清楚' in await fr.inner_text('#aiWarn'))
        sent = json.loads((await ev("__store.fetchLog[__store.fetchLog.length - 1].opts.payload")))['messages'][0]['content'][0]['source']
        check('AI 介面：圖片先在手機縮小成 JPEG 再送出', sent['media_type'] == 'image/jpeg' and len(sent['data']) > 100, sent['media_type'])
        await fr.fill('#aiList [data-s="1"] [data-i="0"] .a-p0', '120')
        await fr.fill('#aiList [data-s="0"] .a-t', '冰飲')
        await fr.click('#aiList [data-s="0"] [data-i="0"] [data-act="delit"]')
        check('AI 介面：可以改分類名稱、價格、刪除品項', await fr.locator('#aiList [data-s="0"] [data-i]').count() == 2)
        await fr.click('#aiApply')
        await page.wait_for_timeout(2500)
        got = await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('sections')).map(s => s.t); }", tokU)
        rows = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", sid_u)
        check('AI 介面：按「確認並儲存」後，修改過的內容才寫進去（冰飲、排骨便當 120、紅茶已刪除）', got == ['冰飲', '便當'] and any(x[2] == '排骨便當' and x[4] == 120 for x in rows) and not any(x[2] == '紅茶' for x in rows), (got, rows))
        await H.evaluate("p => openPage(p)", {'t': tokU})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('AI 介面：重新載入後菜單工具顯示新建的分類與品項', await fr.evaluate("[...document.querySelectorAll('.sec .sec-h h2')].map(x => x.textContent).join()") == '冰飲,便當' and await fr.locator('.it').count() >= 4)

        # ================= 18. 外觀：店家顏色（即時預覽）與分類區分色 =================
        sid_e = (await fn('admSaveShop', adm, {'name': '色彩測試店', 'taxId': '23456781', 'owner': 'a', 'email': 'c@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_e, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_e)
        tokE = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_e)
        r = await fn('ownThemeSave', tokE, {'primary': 'red', 'accent': '#E8762A'}); check('外觀：顏色格式錯誤被擋', not r['v']['ok'], r)
        r = await fn('ownThemeSave', tokS, {'primary': '#112233', 'accent': '#E8762A'}); check('外觀：夥伴不能改', 'err' in r or not r['v']['ok'], r)
        await H.evaluate("p => openPage(p)", {'t': tokE})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('外觀：預設是經典藍橘；店長看得到「外觀」按鈕', await fr.is_visible('#thLink') and await fr.evaluate("THEME.primary") == '#1B4F8A')
        await fr.click('#thLink'); await fr.wait_for_selector('#thModal.open')
        await fr.wait_for_selector('#thInner .sheet')
        check('外觀：打開就有預覽（菜單還沒有品項，用範例品項示意）', await fr.locator('#thInner .r:not(.h)').count() >= 4 and '範例品項' in await fr.inner_text('#thInner') and '範例' in await fr.inner_text('#thNote'))
        sv = lambda: fr.evaluate("(() => { const e = document.querySelector('#thInner .sheet'); const cs = getComputedStyle(e); return [cs.getPropertyValue('--sp').trim(), cs.getPropertyValue('--sa').trim(), cs.getPropertyValue('--sop').trim()]; })()")
        check('外觀：預覽用目前的顏色', (await sv())[:2] == ['#1B4F8A', '#E8762A'], await sv())
        await fr.click('#thPresets [data-p="1"]')
        await fr.wait_for_function("getComputedStyle(document.querySelector('#thInner .sheet')).getPropertyValue('--sp').trim() === '#2E6B4F'")
        heroBg = await fr.evaluate("getComputedStyle(document.querySelector('#thInner .hero')).backgroundColor")
        check('外觀：按「森林綠」配色，預覽馬上換色（標題區背景變綠）', heroBg == 'rgb(46, 107, 79)', heroBg)
        await fr.evaluate("(() => { const el = document.getElementById('thP'); el.value = '#ffe9a8'; el.dispatchEvent(new Event('input', { bubbles: true })); })()")
        await fr.wait_for_function("getComputedStyle(document.querySelector('#thInner .sheet')).getPropertyValue('--sp').trim() === '#FFE9A8'")
        check('外觀：自己選很淺的主色時，標題區文字自動改深色', (await sv())[2] == '#16233A', await sv())
        check('外觀：淺色主色搭深色字，不需要提醒', await fr.locator('#thWarn .warn').count() == 0)
        await fr.evaluate("(() => { const el = document.getElementById('thP'); el.value = '#7a7a9a'; el.dispatchEvent(new Event('input', { bubbles: true })); })()")
        await fr.wait_for_function("getComputedStyle(document.querySelector('#thInner .sheet')).getPropertyValue('--sp').trim() === '#7A7A9A'")
        check('外觀：不深不淺的主色（字看不清楚）會顯示提醒', await fr.is_visible('#thWarn .warn'))
        await fr.evaluate("(() => { const el = document.getElementById('thP'); el.value = '#8c2f39'; el.dispatchEvent(new Event('input', { bubbles: true })); })()")
        await fr.wait_for_function("getComputedStyle(document.querySelector('#thInner .sheet')).getPropertyValue('--sp').trim() === '#8C2F39'")
        check('外觀：深色主色時文字是白色、提醒消失', (await sv())[2] == '#FFFFFF' and await fr.locator('#thWarn .warn').count() == 0, await sv())
        firstId = await fr.evaluate("SECTIONS[0].id")
        await fr.click(f'#thCats [data-c="{firstId}"] [data-col="#2E7D4F"]')
        await fr.wait_for_function("getComputedStyle(document.querySelector('#thInner .s h2 .bar')).backgroundColor === 'rgb(46, 125, 79)'")
        check('外觀：替分類選區分色，預覽裡該分類的色條馬上變色', True)
        await fr.click('#thCancel')
        check('外觀：按取消不會改動（主色回到藍色）', await fr.evaluate("THEME.primary") == '#1B4F8A' and await fr.evaluate("THEME.colors[SECTIONS[0].id] || ''") == '')
        await fr.click('#thLink'); await fr.wait_for_selector('#thModal.open')
        await fr.click('#thPresets [data-p="2"]')
        await fr.wait_for_function("getComputedStyle(document.querySelector('#thInner .sheet')).getPropertyValue('--sp').trim() === '#8C2F39'")
        await fr.click(f'#thCats [data-c="{firstId}"] [data-col="#8E44AD"]')
        await fr.click('#thSave'); await page.wait_for_timeout(2000)
        saved = await ev("t => { authGuard_(t, false); return [JSON.parse(props_().getProperty('cfg')), JSON.parse(props_().getProperty('sections'))]; }", tokE)
        check('外觀：按「儲存」後顏色存在伺服器（主色、強調色、分類色）', saved[0]['primary'] == '#8C2F39' and saved[0]['accent'] == '#D9A441' and saved[1][0]['color'] == '#8E44AD', saved)
        await H.evaluate("p => openPage(p)", {'t': tokE})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        sh = await fr.evaluate("(() => { rebuildFromRows([{ k: SECTIONS[0].id + '|測|0', cat: 'x', name: '測', spec: '', p: '50', l: '50', hidden: false, star: true, side: '' }]); prices[SECTIONS[0].id + '|測|0'] = '50'; return sheetHTML('menu', 'V1'); })()")
        check('外觀：重新載入後，正式菜單與 PDF 用新顏色（含分類色條）', '--sp:#8C2F39' in sh and '--sa:#D9A441' in sh and '--bar:#8E44AD' in sh, sh[:200])
        html = await ev("s => doGet({ parameter: { s } }).getContent()", sid_e)
        check('外觀：顧客頁也帶出新顏色', '"primary":"#8C2F39"' in html.replace(' ', ''))
        r = (await fn('ownCfgSave', tokE, {'name': '色彩測試店', 'openDays': [1, 2]}))['v']
        check('外觀：之後改店家資料不會洗掉顏色', r['ok'] and r['cfg']['primary'] == '#8C2F39', r)
        check('外觀：店家工具海報的預設顏色跟著店家主色', await ev("t => { authGuard_(t, false); var s = tDefaultShop_(); return s.primary + s.accent; }", tokE) == '#8C2F39#D9A441')

        # ================= 19. 分類範本（協助店主建立分類）=================
        sid_t2 = (await fn('admSaveShop', adm, {'name': '範本測試店', 'taxId': '34567892', 'owner': 'a', 'email': 't@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_t2, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_t2)
        tokT2 = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_t2)
        await H.evaluate("p => openPage(p)", {'t': tokT2})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        await fr.click('#secLink'); await fr.wait_for_selector('#secModal.open')
        await fr.click('#secTpl [data-tpl="飲料店"]')
        check('分類範本：點「飲料店」帶入 5 個分類與規格欄', await fr.locator('#secList [data-i]').count() == 5 and await fr.input_value('#secList [data-i="0"] .s-c') == '中杯,大杯')
        await fr.fill('#secList [data-i="4"] .s-t', '加購配料')
        await fr.click('#secSave'); await page.wait_for_timeout(2000)
        got = await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('sections')); }", tokT2)
        check('分類範本：儲存後分類存到伺服器（代碼自動產生、不重複），可再改名', [s['t'] for s in got] == ['茗茶', '奶茶', '果汁／冰沙', '咖啡', '加購配料'] and len({s['id'] for s in got}) == 5, got)

        # ================= 20. 空菜單：要能新增第一個品項 =================
        sid_z = (await fn('admSaveShop', adm, {'name': '空菜單店', 'taxId': '45678903', 'owner': 'a', 'email': 'z@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_z, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_z)
        tokZ = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_z)
        await H.evaluate("p => openPage(p)", {'t': tokZ})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('空菜單：每個分類都顯示，並有「＋ 新增品項」按鈕（3 個預設分類）', await fr.locator('.sec:visible .addbtn:visible').count() == 3)
        check('空菜單：顯示「從這裡開始」操作提示', await fr.is_visible('#emptyHint') and '＋ 新增品項' in await fr.inner_text('#emptyHint'))
        await fr.click('#emptyGo')
        await fr.wait_for_selector('#addModal.open')
        await fr.fill('#addName', '第一個品項'); await fr.fill('#addCols input >> nth=0', '88'); await fr.click('#addOk')
        await fr.wait_for_function("!document.querySelector('#addModal').classList.contains('open')")
        check('空菜單：從提示按鈕新增第一個品項成功，寫進試算表', await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.some(r => r[2] === '第一個品項' && r[4] === 88)", sid_z))
        check('空菜單：新增後提示消失，品項出現在列表', not await fr.is_visible('#emptyHint') and await fr.locator('.it[data-name="第一個品項"]').count() == 1)
        await fr.fill('#q', '不存在的東西')
        check('空菜單：搜尋不到時仍會隱藏空分類、顯示「找不到」', await fr.is_visible('#none'))

        # ================= 21. 設定精靈：第一次進來先設定店家資料、Logo、配色 =================
        sid_w = (await fn('admSaveShop', adm, {'name': '精靈測試店', 'taxId': '56789014', 'owner': 'a', 'email': 'w@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_w, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_w)
        tokW = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_w)
        html = await ev("t => doGet({ parameter: { t } }).getContent()", tokW)
        check('精靈：店主第一次進來（還沒設定）先看到設定精靈，不是菜單工具', '先設定你的店' in html and 'const BRAND' not in html)
        inv = (await fn('ownInvite', tokW, '夥伴甲'))['v']; tokWS = (await fn('authInvite', inv['code'], 'devW'))['v']['token']
        html = await ev("t => doGet({ parameter: { t } }).getContent()", tokWS); check('精靈：夥伴不用走精靈，直接進菜單工具', 'const BRAND' in html)
        html = await ev("t => doGet({ parameter: { t, later: '1' } }).getContent()", tokW); check('精靈：「先跳過」可以直接進菜單工具', 'const BRAND' in html)
        html = await ev("t => doGet({ parameter: { t, p: 'tools' } }).getContent()", tokW); check('精靈：店家工具不受影響', '<h1>店家工具</h1>' in html)
        check('正式授權：店家工具輸出不加浮水印（boot.wm=0）', '"wm":0' in html.replace(' ', ''))
        sid_t = (await fn('admSaveShop', adm, {'name': '浮水印試用店', 'taxId': '67890123', 'owner': 'a', 'email': 'wm@example.com', 'plan': 'trial', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admProvision', adm, sid_t)
        await fn('admSetStatus', adm, sid_t, 'trial')
        tokT = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_t)
        html = await ev("t => doGet({ parameter: { t, p: 'tools' } }).getContent()", tokT)
        check('試用版：店家工具輸出會加浮水印（boot.wm=1）', '"wm":1' in html.replace(' ', ''), str(await ev("s => { var l = licOf_(shopById_(s)); return l.status + '|' + l.watermark + '|' + l.mode; }", sid_t)) + ' | ' + str(len(html)) + ' | ' + str('wm' in html))
        html = await ev("t => doGet({ parameter: { t } }).getContent()", tokWS)
        await H.evaluate("p => openPage(p)", {'t': tokW, 'wizard': '1'})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true')
        check('精靈步驟 1：店名預設帶入公司名稱', await fr.input_value('#cName') == '精靈測試店')
        await fr.fill('#cName', ''); await fr.click('#n1')
        check('精靈步驟 1：沒填店名不能繼續', '請填店名' in await fr.inner_text('#m1'))
        check('精靈步驟 1：公司名稱與統編顯示在這裡（註冊時已登錄，唯讀、有說明）', await fr.input_value('#cCompany') == '精靈測試店' and await fr.input_value('#cTax') == '56789014' and await fr.evaluate("document.getElementById('cCompany').readOnly && document.getElementById('cTax').readOnly") and '不能自行修改' in await fr.inner_text('#coNote'))
        check('精靈步驟 1：縣市有 22 個，選了縣市才出現該縣市的區', await fr.locator('#aCity option').count() == 23 and await fr.locator('#aDist option').count() == 1)
        await fr.select_option('#aCity', '桃園市')
        check('精靈步驟 1：選「桃園市」自動帶出 13 個區（中壢區在內）', await fr.locator('#aDist option').count() == 14 and '中壢區' in await fr.inner_text('#aDist'))
        await fr.select_option('#aCity', '台北市')
        check('精靈步驟 1：換縣市，區清單跟著換、不會殘留', await fr.locator('#aDist option').count() == 13 and '中壢區' not in await fr.inner_text('#aDist'))
        await fr.select_option('#aDist', '大安區'); await fr.fill('#aRoad', '中山路 8 號 1 樓')
        check('精靈步驟 1：地址即時預覽（縣市＋區＋路號）', '台北市大安區中山路 8 號 1 樓' in await fr.inner_text('#addrPv'))
        await fr.fill('#cName', '阿福早餐'); await fr.fill('#cTag', '一天的好開始'); await fr.fill('#cHours', '週一至週五 06:30–13:00'); await fr.fill('#cClosed', '公休：週六、週日')
        await fr.select_option('#tArea', '02'); await fr.fill('#tNum', '22223333'); await fr.fill('#tMob', '0912345678')
        check('精靈步驟 1：電話即時預覽，市話與手機格式統一（02-2222-3333／0912-345-678）', '02-2222-3333／0912-345-678' in await fr.inner_text('#telPv'), await fr.inner_text('#telPv'))
        await fr.fill('#tMob', '12345'); await fr.click('#n1')
        check('精靈步驟 1：手機格式錯誤不能繼續', '手機號碼要 10 碼' in await fr.inner_text('#m1'))
        await fr.fill('#tMob', '0912345678'); await fr.fill('#tNum', '123'); await fr.click('#n1')
        check('精靈步驟 1：市話號碼長度不對不能繼續', '7～8 碼' in await fr.inner_text('#m1'))
        await fr.fill('#tNum', '22223333')
        await fr.fill('#cLineId', 'a b'); await fr.click('#n1')
        check('精靈步驟 1：LINE ID 格式錯誤不能繼續，並顯示提示', 'LINE ID 格式不正確' in await fr.inner_text('#linePv') or 'LINE ID 格式不正確' in await fr.inner_text('#m1'))
        await fr.fill('#cLineId', 'afu123')
        check('精靈步驟 1：填 LINE ID 就自動產生官方網址（自動補 @、@ 編成 %40）', 'https://line.me/R/ti/p/%40afu123' in await fr.inner_text('#linePv'), await fr.inner_text('#linePv'))
        for d in ['6', '0']: await fr.uncheck(f'#cDays [data-d="{d}"]')
        await fr.click('#n1'); await fr.wait_for_selector('#s2:not(.hide)')
        cfg = await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('cfg')); }", tokW)
        check('精靈步驟 1：資料存到伺服器（地址、電話、LINE 網址、營業日）', cfg['name'] == '阿福早餐' and cfg['address'] == '台北市大安區中山路 8 號 1 樓' and cfg['addrCity'] == '台北市' and cfg['phone'] == '02-2222-3333／0912-345-678'
              and cfg['lineId'] == '@afu123' and cfg['lineUrl'] == 'https://line.me/R/ti/p/%40afu123' and cfg['openDays'] == [1, 2, 3, 4, 5], cfg)
        r = (await fn('ownCompanySave', tokW, {'company': '偷改公司', 'taxId': '10458575'}))['v']
        check('公司名稱與統編：已登錄的店家不能自己改', not r['ok'] and r['code'] == 'locked', r)
        sid_ph = (await fn('admSaveShop', adm, {'name': '佔位公司', 'taxId': '00000000', 'owner': 'a', 'email': 'ph@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_ph, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_ph)
        tokPH = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_ph)
        r = (await fn('ownCompanySave', tokPH, {'company': '', 'taxId': '10458575'}))['v']; check('公司登錄：沒填公司名稱被擋', not r['ok'], r)
        r = (await fn('ownCompanySave', tokPH, {'company': '新公司', 'taxId': '12345678'}))['v']; check('公司登錄：統編檢查碼錯誤被擋', not r['ok'] and '統編' in r['msg'], r)
        r = (await fn('ownCompanySave', tokPH, {'company': '新公司', 'taxId': '22099131'}))['v']; check('公司登錄：統編已被別的帳號用過被擋', not r['ok'] and r['code'] == 'exists', r)
        await H.evaluate("p => openPage(p)", {'t': tokPH, 'wizard': '1'})
        fr2 = H.child_frames[0]; await fr2.wait_for_function('window.__hlEnd === true')
        check('公司登錄：統編還是佔位時，欄位可以填寫、提示會登錄一次', not await fr2.evaluate("document.getElementById('cCompany').readOnly") and '登錄後不能自行修改' in await fr2.inner_text('#coNote'))
        await fr2.fill('#cCompany', '阿福股份有限公司'); await fr2.fill('#cTax', '10458575'); await fr2.click('#n1'); await fr2.wait_for_selector('#s2:not(.hide)')
        ph = await ev("s => { var x = shopById_(s); return [x.name, x.taxId, x.nameLock > todayStr_()]; }", sid_ph)
        check('公司登錄：精靈裡填公司名稱與統編，存進授權中心並開始 180 天名稱鎖定', ph == ['阿福股份有限公司', '10458575', True], ph)
        await H.evaluate("p => openPage(p)", {'t': tokW, 'wizard': '1'})
        fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true')
        await fr.click('#n1'); await fr.wait_for_selector('#s2:not(.hide)')
        from PIL import Image as _I, ImageDraw as _D
        small = os.path.join(tempfile.gettempdir(), 'logo_small.png'); _I.new('RGBA', (300, 200), (200, 30, 40, 255)).save(small)
        good = os.path.join(tempfile.gettempdir(), 'logo_good.png'); im = _I.new('RGBA', (1600, 1600), (0, 0, 0, 0)); _D.Draw(im).ellipse([160, 160, 1440, 1440], fill=(200, 30, 40, 255)); im.save(good)
        await fr.set_input_files('#logoFile', small)
        await fr.wait_for_selector('#checks li.bad')
        check('精靈步驟 2：Logo 解析度太小會被擋下，並說明原因', '太小' in await fr.inner_text('#checks') and await fr.is_disabled('#logoSave'))
        await fr.set_input_files('#logoFile', good)
        await fr.wait_for_function("!document.querySelector('#logoSave').disabled")
        check('精靈步驟 2：合格的去背 Logo 通過檢查並顯示預覽', '符合標準' in await fr.inner_text('#checks') and '去背' in await fr.inner_text('#checks') and await fr.locator('#logoTile img').count() == 1)
        await fr.click('#logoSave'); await fr.wait_for_function("document.querySelector('#m2').textContent.includes('已上傳')")
        lm = await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('t_logo')); }", tokW)
        check('精靈步驟 2：Logo 存進這家店（含網頁小圖）', lm['w'] == 1600 and lm['bgMode'] == 'transparent' and bool(lm['fileId']) and bool(lm['webId']), lm)
        await fr.click('#n2'); await fr.wait_for_selector('#s3:not(.hide)')
        pvt = await fr.inner_text('#pv')
        check('精靈步驟 3：預覽顯示店名、地址、電話、Logo、LINE 區塊', all(x in pvt for x in ['阿福早餐', '台北市大安區中山路 8 號 1 樓', '02-2222-3333', '點餐掃碼']) and await fr.locator('#pv img').count() == 1, pvt)
        await fr.click('#pres [data-p="2"]')
        hero = await fr.evaluate("getComputedStyle(document.querySelector('#pv .hero')).backgroundColor")
        check('精靈步驟 3：按「酒紅金」預覽馬上換色', hero == 'rgb(140, 47, 57)', hero)
        await fr.evaluate("(() => { const el = document.getElementById('cP'); el.value = '#ffe9a8'; el.dispatchEvent(new Event('input', { bubbles: true })); })()")
        col = await fr.evaluate("getComputedStyle(document.querySelector('#pv .hero')).color")
        check('精靈步驟 3：淺色主色時，標題區文字自動變深色', col == 'rgb(22, 35, 58)', col)
        await fr.click('#pres [data-p="2"]'); await fr.click('#n3'); await fr.wait_for_selector('#s4:not(.hide)')
        saved = await ev("t => { authGuard_(t, false); var c = JSON.parse(props_().getProperty('cfg')); return [c.primary, c.accent, props_().getProperty('onboarded')]; }", tokW)
        check('精靈步驟 3：配色存到伺服器，並標記設定完成', saved == ['#8C2F39', '#D9A441', '1'], saved)
        href = await fr.get_attribute('#goMenu', 'href')
        check('精靈完成：「進入菜單工具」連結帶通行證', 't=' in href and 'later=1' in href, href)
        html = await ev("t => doGet({ parameter: { t } }).getContent()", tokW)
        check('精靈完成後：店主下次進來直接是菜單工具', 'const BRAND' in html and '阿福早餐' in html)
        check('帶入各功能：菜單工具用新店名、新顏色、上傳的 Logo', '"primary":"#8C2F39"' in html.replace(' ', '') and '"nameA":"阿福早餐"' in html.replace(' ', '') and 'data:image' in html)
        cust = await ev("s => doGet({ parameter: { s } }).getContent()", sid_w)
        check('帶入各功能：顧客頁用新店名、地址、營業時間、顏色與 Logo', '阿福早餐' in cust and '台北市大安區中山路 8 號 1 樓' in cust and '02-2222-3333' in cust and '"primary":"#8C2F39"' in cust.replace(' ', '') and 'data:image' in cust)
        check('帶入各功能：店家工具海報預設用新店名與顏色', await ev("t => { authGuard_(t, false); var s = tDefaultShop_(); return [s.name, s.primary, s.hours]; }", tokW) == ['阿福早餐', '#8C2F39', '週一至週五 06:30–13:00'])
        await H.evaluate("p => openPage(p)", {'p': 'setup', 't': tokW})
        fr = H.child_frames[0]; await fr.wait_for_function('window.__hlEnd === true')
        check('精靈：之後可以從「?p=setup」再回來修改（地址、電話、LINE 都已帶入）', await fr.input_value('#cName') == '阿福早餐' and await fr.input_value('#aCity') == '台北市' and await fr.input_value('#aDist') == '大安區' and await fr.input_value('#tMob') == '0912345678' and await fr.input_value('#cLineId') == '@afu123' and '修改店家資料' in await fr.inner_text('#sub'))
        html = await ev("t => doGet({ parameter: { p: 'account', t } }).getContent()", tokW); check('帳號頁有「店家設定精靈」入口', '開啟設定精靈' in html and 'p=setup' in html.replace('\\/', '/'))
        check('弘林轉入後視為已設定（不會跳精靈）', await ev("(() => { CTX = { shopId: 'S0001', ssId: 'test', shop: shopById_('S0001') }; return props_().getProperty('onboarded'); })()") == '1')

        # ================= 22. 菜單範本：下載、填寫、上傳（批量設定）=================
        sid_i = (await fn('admSaveShop', adm, {'name': '匯入測試店', 'taxId': '67890125', 'owner': 'a', 'email': 'i@example.com', 'plan': 'pro', 'skipTaxCheck': True}))['v']['shop']['id']
        await fn('admMarkPaid', adm, sid_i, {'plan': 'pro', 'cycle': 'month'}); await fn('admProvision', adm, sid_i)
        tokI = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: 1 }, 1)", sid_i)
        await H.evaluate("p => openPage(p)", {'t': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('範本匯入：店長看得到「菜單範本」按鈕', await fr.is_visible('#impBtn'))
        await fr.click('#impBtn'); await fr.wait_for_selector('#impModal.open')
        async with page.expect_download() as dl:
            await fr.click('#impTpl')
        tpl_path = os.path.join(tempfile.gettempdir(), 'tpl_dl.csv'); await (await dl.value).save_as(tpl_path)
        raw = open(tpl_path, 'rb').read(); txt = raw.decode('utf-8-sig')
        check('範本下載：CSV（UTF-8 含 BOM，Excel 開啟中文不亂碼），有標題列與說明、範例', raw[:3] == b'\xef\xbb\xbf' and '分類,價格欄,品項,價格1' in txt and txt.count('#') >= 5 and '#飲料,中杯|大杯,紅茶' in txt, txt[:200])
        await fr.set_input_files('#impFile', tpl_path)
        await page.wait_for_timeout(500)
        check('範本上傳：沒填內容（只有範例）會提示，不會匯入', '沒有任何品項' in await fr.inner_text('#impMsg'), await fr.inner_text('#impMsg'))
        bad = os.path.join(tempfile.gettempdir(), 'bad.csv'); open(bad, 'w', encoding='utf-8').write('名稱,金額\n紅茶,25\n')
        await fr.set_input_files('#impFile', bad); await page.wait_for_timeout(400)
        check('範本上傳：不是範本格式（沒有標題列）會說明原因', '找不到標題列' in await fr.inner_text('#impMsg'))
        body = (txt.split('#下面三列是範例')[0].split('\n')[0:0])
        csv1 = ('\ufeff分類,價格欄,品項,價格1,價格2,價格3,價格4,價格5,價格6,推薦,標示,附餐說明,隱藏\r\n'
                '飲料,中杯|大杯,紅茶,25,30,,,,,,,,\r\n'
                '飲料,,"鮮奶茶, 特調",45,,,,,,是,奶、蛋奶素、不明,,\r\n'
                '飲料,,冬季熱湯,60,abc,,,,,,,小心燙,是\r\n'
                '飲料,,紅茶,1,1,,,,,,,,\r\n'
                '主餐,價格,招牌便當,$100元,,,,,,是,蛋、麩質、辣,附湯,\r\n'
                ',,素食便當,95,,,,,,,素,,\r\n'
                '主餐,,,99,,,,,,,,,\r\n'
                '#註解列,,忽略我\r\n'
                ',,,,,,,,,,,,\r\n'
                '甜點,,布丁,60,,,,,,,,,\r\n')
        f1 = os.path.join(tempfile.gettempdir(), 'menu1.csv'); open(f1, 'w', encoding='utf-8', newline='').write(csv1)
        await fr.set_input_files('#impFile', f1)
        await fr.wait_for_selector('#ai2', state='visible', timeout=8000)
        check('範本上傳：解析成 3 個分類（飲料、主餐、甜點）、6 個品項，直接顯示在檢查畫面', await fr.locator('#aiList [data-s]').count() == 3 and await fr.locator('#aiList [data-i]').count() == 6, await fr.locator('#aiList [data-i]').count())
        w = await fr.inner_text('#aiWarn')
        check('範本上傳：列出問題（價格看不懂、重複品項、標示不認識、沒有品項名稱），並指出是第幾列', '「abc」看不懂' in w and '重複' in w and '「不明」不認識' in w and '沒有品項名稱' in w and '第 ' in w, w)
        check('範本上傳：標題換成「檢查匯入的菜單」', '檢查匯入' in await fr.inner_text('#aiTitle'))
        await fr.fill('#aiList [data-s="0"] [data-i="0"] .a-p1', '32')
        await fr.click('#aiApply'); await page.wait_for_timeout(2500)
        rows = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", sid_i)
        by = {r[0].split('|', 1)[1]: r for r in rows}
        secs = await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('sections')); }", tokI)
        check('範本匯入：分類以範本為準（取代預設分類）、規格欄正確', [(s['t'], s['cols']) for s in secs] == [('飲料', ['中杯', '大杯']), ('主餐', ['價格']), ('甜點', ['價格'])], secs)
        check('範本匯入：價格、檢查畫面上修改的價格（紅茶大杯 32）、多規格留白不建立列', by['紅茶|0'][4] == 25 and by['紅茶|1'][4] == 32 and '鮮奶茶, 特調|1' not in by and by['鮮奶茶, 特調|0'][4] == 45, list(by)[:6])
        check('範本匯入：推薦、標示（中文對應成代碼）、附餐說明、隱藏', by['鮮奶茶, 特調|0'][7] is True and by['鮮奶茶, 特調|0'][9] == 'milk,veg' and by['招牌便當|0'][4] == 100 and by['招牌便當|0'][9] == 'egg,gluten,spicy' and by['招牌便當|0'][8] == '附湯' and by['冬季熱湯|0'][6] is True and by['冬季熱湯|0'][8] == '小心燙' and by['素食便當|0'][9] == 'veg' and by['素食便當|0'][4] == 95, by.get('招牌便當|0'))
        check('範本匯入：沒填分類的列沿用上一列分類（素食便當在主餐）、空白列與 # 列忽略', by['素食便當|0'][1] == '主餐' and '忽略我' not in json.dumps(rows, ensure_ascii=False) and len(rows) == 7, len(rows))
        check('範本匯入：寫入修改紀錄', await ev("s => __store.books[shopById_(s).ssId].sheets['修改紀錄'].data.some(r => String(r[4]).indexOf('範本匯入菜單') >= 0)", sid_i))
        # 匯出目前菜單 → 修改 → 再上傳（批量改價）
        await H.evaluate("p => openPage(p)", {'t': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        await fr.click('#impBtn'); await fr.wait_for_selector('#impModal.open')
        async with page.expect_download() as dl2:
            await fr.click('#impExp')
        ex_path = os.path.join(tempfile.gettempdir(), 'menu_export.csv'); await (await dl2.value).save_as(ex_path)
        ex = open(ex_path, encoding='utf-8-sig').read()
        check('匯出目前菜單：包含所有品項、價格欄、標示（中文）、推薦、附餐說明、隱藏', '飲料,中杯|大杯,紅茶,25,32' in ex and '鮮奶茶, 特調' in ex.replace('"', '') and '奶、素' in ex and '蛋、麩質、辣' in ex and '附湯' in ex and ex.count('是') >= 3, ex[:400])
        edited = ex.replace('飲料,中杯|大杯,紅茶,25,32', '飲料,中杯|大杯,紅茶,28,35').replace('招牌便當,100', '招牌便當,120')
        f2 = os.path.join(tempfile.gettempdir(), 'menu2.csv'); open(f2, 'w', encoding='utf-8-sig', newline='').write(edited)
        before_last = by['紅茶|0'][5]
        await fr.set_input_files('#impFile', f2)
        await fr.wait_for_selector('#ai2', state='visible', timeout=8000)
        check('批量改價：上傳匯出檔，檢查畫面說明「已經在菜單裡，會更新」', '已經在菜單裡' in await fr.inner_text('#aiMsg') and '會更新' in await fr.inner_text('#aiMsg'), await fr.inner_text('#aiMsg'))
        await fr.click('#aiApply'); await page.wait_for_timeout(2500)
        rows2 = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", sid_i)
        by2 = {r[0].split('|', 1)[1]: r for r in rows2}
        check('批量改價：只有改過的價格被更新（紅茶 28/35、招牌便當 120），其他不變、沒有新增重複', by2['紅茶|0'][4] == 28 and by2['紅茶|1'][4] == 35 and by2['招牌便當|0'][4] == 120 and by2['素食便當|0'][4] == 95 and len(rows2) == len(rows), (by2['紅茶|0'][4], len(rows2), len(rows)))
        check('批量改價：「上次印製」欄不動（之後輸出菜單才能標出變動的價格）', by2['紅茶|0'][5] == before_last, by2['紅茶|0'])
        check('批量改價：標示、推薦、附餐說明、隱藏維持原樣（匯出檔帶著）', by2['鮮奶茶, 特調|0'][9] == 'milk,veg' and by2['冬季熱湯|0'][6] is True and by2['招牌便當|0'][8] == '附湯', by2['鮮奶茶, 特調|0'])
        # Excel 另存的 CSV 可能是 Big5
        f3 = os.path.join(tempfile.gettempdir(), 'menu_big5.csv')
        open(f3, 'wb').write('分類,價格欄,品項,價格1\r\n甜點,價格,布丁,65\r\n甜點,,奶酪,70\r\n'.encode('big5'))
        await H.evaluate("p => openPage(p)", {'t': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        await fr.click('#impBtn'); await fr.wait_for_selector('#impModal.open'); await fr.set_input_files('#impFile', f3)
        await fr.wait_for_selector('#ai2', state='visible', timeout=8000)
        check('Big5 編碼的 CSV（舊版 Excel 另存）也能正確讀取中文', '布丁' in await fr.input_value('#aiList [data-s] [data-i="0"] .a-n') and await fr.locator('#aiList [data-i]').count() == 2)
        await fr.click('#aiApply'); await page.wait_for_timeout(2000)
        rows3 = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", sid_i)
        check('Big5 匯入：既有分類（甜點）併入，布丁更新為 65、新增奶酪', any(r[2] == '布丁' and r[4] == 65 for r in rows3) and any(r[2] == '奶酪' and r[4] == 70 for r in rows3) and len(rows3) == len(rows2) + 1, len(rows3))
        r = await fn('menuImportApply', {'sections': []}, tokWS); check('範本匯入：夥伴不能匯入', 'err' in r, r)
        r = await fn('menuImportApply', {'sections': []}, tokI); check('範本匯入：沒有分類被擋', 'err' in r, r)
        r = (await fn('menuImportApply', {'sections': [{'title': 'x' * 40, 'columns': ['a'] * 9, 'items': [{'name': 'n|<b>', 'prices': [1e9, -4, 'x'], 'tags': ['egg', 'hack'], 'side': 's' * 99}]}]}, tokI))['v']
        check('範本匯入：伺服器再驗一次（過長截斷、價格上限 9999、不合法標示過濾）', r['ok'] and await ev("s => { var r = __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(x => x[0] && x[2].indexOf('n／b') === 0)[0]; return [r[4], r[9], r[8].length, r[1].length]; }", sid_i) == [9999, 'egg', 30, 14], r)

        # ================= 23. 多門市第一階段：分店清單批量建立、品牌主進入分店、菜單套用到分店 =================
        import base64 as _b64, io as _io
        from PIL import Image as _PI, ImageDraw as _PD
        _im = _PI.new('RGBA', (1600, 1600), (0, 0, 0, 0)); _PD.Draw(_im).ellipse([160, 160, 1440, 1440], fill=(30, 100, 60, 255)); _bf = _io.BytesIO(); _im.save(_bf, 'PNG')
        logo_b64 = _b64.b64encode(_bf.getvalue()).decode()
        HQ = sid_i
        await fn('ownThemeSave', tokI, {'primary': '#2E6B4F', 'accent': '#E8A33D'})
        await fn('ownCfgSave', tokI, {'name': '匯入測試店', 'tagline': '品牌好味道', 'openDays': [1, 2, 3, 4, 5, 6, 0], 'hours': '07:00–14:00', 'lineId': '@brandhq'})
        await ev("([t, b]) => tSaveLogo({ b64: b, origW: 1600, origH: 1600, origType: 'image/png', origBytes: 5000, bgMode: 'transparent', bg: null, bgManual: '' }, t)", [tokI, logo_b64])
        hq_rows = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0]).length", HQ)
        ROW1 = {'name': '中壢店', 'city': '桃園市', 'dist': '中壢區', 'road': '廣州路 11 號', 'land': '03-458-8229', 'mobile': '0912-345-678', 'days': '週一至週五', 'hours': '06:00–13:00', 'closed': '公休：週六、日', 'lineId': 'zhongli', 'email': 'Boss.Zhongli@Example.com', 'note': '直營'}
        ROW2 = {'name': '平鎮店', 'city': '臺北市', 'dist': '大安區', 'road': '中山路 8 號', 'land': '', 'mobile': '', 'days': '', 'hours': '', 'closed': '', 'lineId': '', 'email': '', 'note': ''}
        chk = (await fn('brandBranchCheck', tokI, [ROW1, ROW2, {'name': '', 'city': '桃園市'}, {'name': 'X店', 'land': '12345'}, {'name': 'Y店', 'mobile': '123'}, {'name': 'Z店', 'days': '週九'}, {'name': 'W店', 'city': '桃園市'}, dict(ROW1)]))['v']
        rs = chk['rows']
        check('分店清單檢查：正確的列整理成統一格式（臺→台、營業日、市話、手機、LINE、名稱加品牌）', rs[0]['ok'] and rs[0]['data']['fullName'] == '匯入測試店 中壢店' and rs[0]['data']['openDays'] == [1, 2, 3, 4, 5] and rs[0]['data']['phoneLandArea'] == '03' and rs[0]['data']['phoneLandNum'] == '4588229' and rs[0]['data']['phoneMobile'] == '0912345678' and rs[0]['data']['lineId'] == '@zhongli' and rs[0]['data']['email'] == 'boss.zhongli@example.com' and rs[1]['data']['city'] == '台北市', rs[0])
        check('分店清單檢查：沒有名稱、市話沒區碼、手機格式錯、營業日看不懂、縣市沒填區、名稱重複，各自標出錯誤', not rs[2]['ok'] and '沒有分店名稱' in rs[2]['errors'][0] and not rs[3]['ok'] and not rs[4]['ok'] and '10 碼' in ' '.join(rs[4]['errors']) and not rs[5]['ok'] and '營業日看不懂' in ' '.join(rs[5]['errors']) and not rs[6]['ok'] and '一起填' in ' '.join(rs[6]['errors']) and not rs[7]['ok'] and '重複' in ' '.join(rs[7]['errors']), [r['errors'] for r in rs])
        r = await fn('brandBranchCheck', tokWS, [ROW1]); check('分店：夥伴不能管理分店', 'err' in r, r)
        await ev("__store.props.branchMax = '2'")
        c1 = (await fn('brandBranchCreate', tokI, ROW1, {'copyMenu': True}))['v']; c2 = (await fn('brandBranchCreate', tokI, ROW2, {'copyMenu': True}))['v']
        check('分店建立：兩家都成功，各自有顧客網址；寄出店長邀請（只有填 Email 的那家）', c1['ok'] and c2['ok'] and c1['invited'] and not c2['invited'] and c1['customerUrl'].endswith('?s=' + c1['id']), (c1, c2))
        c3 = (await fn('brandBranchCreate', tokI, {'name': '第三店'}, {}))['v']; check('分店建立：超過數量上限被擋', not c3['ok'] and c3['code'] == 'limit', c3)
        r = (await fn('brandBranchCreate', tokI, ROW1, {}))['v']; check('分店建立：同名分店不能重複建立', not r['ok'], r)
        b1 = await ev("s => shopById_(s)", c1['id']); b2 = await ev("s => shopById_(s)", c2['id']); hq_s = await ev("s => shopById_(s)", HQ)
        check('分店資料：品牌編號指向總店、角色＝分店、同統編、各有獨立試算表與資料夾', b1['brandId'] == HQ and b1['role'] == '分店' and b1['taxId'] == hq_s['taxId'] and b1['ssId'] and b1['ssId'] != b2['ssId'] != hq_s['ssId'] and b1['folderId'] != b2['folderId'], (b1['brandId'], b1['ssId'], b2['ssId']))
        check('分店：不能用統編登入（統編只對應總店）', (await ev("t => shopByTaxId_(t).id", hq_s['taxId'])) == HQ)
        cfg1 = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')); }", c1['id'])
        check('分店店家資料：用清單上的地址、電話、營業日、營業時間、LINE，其餘繼承總店（標語、顏色）', cfg1['name'] == '匯入測試店 中壢店' and cfg1['address'] == '桃園市中壢區廣州路 11 號' and cfg1['phone'] == '03-458-8229／0912-345-678' and cfg1['openDays'] == [1, 2, 3, 4, 5] and cfg1['hours'] == '06:00–13:00' and cfg1['lineUrl'] == 'https://line.me/R/ti/p/%40zhongli' and cfg1['tagline'] == '品牌好味道' and cfg1['primary'] == '#2E6B4F' and cfg1['accent'] == '#E8A33D' and cfg1['notifyEmail'] == 'boss.zhongli@example.com', cfg1)
        cfg2 = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')); }", c2['id'])
        check('分店店家資料：沒填的欄位（營業日、營業時間、LINE）沿用總店；地址用台北市', cfg2['openDays'] == [1, 2, 3, 4, 5, 6, 0] and cfg2['hours'] == '07:00–14:00' and cfg2['lineId'] == '@brandhq' and cfg2['address'] == '台北市大安區中山路 8 號', cfg2)
        l1 = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return [props_().getProperty('onboarded'), JSON.parse(props_().getProperty('t_logo'))]; }", c1['id'])
        lh = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('t_logo')); }", HQ)
        check('分店：Logo 複製一份到分店自己的資料夾（檔案編號不同，且檔案存在）、設定精靈視為完成', l1[0] == '1' and bool(l1[1]['fileId']) and l1[1]['fileId'] != lh['fileId'], (l1, lh['fileId']))
        check('分店：Logo 檔案真的存在', await ev("id => !!__store.files[id]", l1[1]['fileId']))
        rows_b1 = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", c1['id'])
        rows_hq = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", HQ)
        key = lambda r: r[2] + '|' + r[3]
        same = sorted([(key(r), r[4], r[6], r[7], r[8], r[9]) for r in rows_b1]) == sorted([(key(r), r[4], r[6], r[7], r[8], r[9]) for r in rows_hq])
        check('分店菜單：複製總店全部品項（價格、推薦、標示、附餐說明、隱藏都一樣）', len(rows_b1) == hq_rows and same, (len(rows_b1), hq_rows))
        secs_b1 = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('sections')).map(x => [x.t, x.cols.join('/')]); }", c1['id'])
        secs_hq = await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('sections')).map(x => [x.t, x.cols.join('/')]); }", tokI)
        check('分店菜單：分類與規格欄跟總店一致（飲料、主餐、甜點）', sorted(map(tuple, secs_b1)) == sorted(map(tuple, secs_hq)), (secs_b1, secs_hq))
        check('分店：寄出店長邀請信（含邀請連結與分店名稱），建立夥伴邀請', await ev("() => __store.mails.some(m => m.to === 'boss.zhongli@example.com' && m.body.indexOf('?invite=') >= 0 && m.body.indexOf('匯入測試店 中壢店') >= 0)") and await ev("s => cRows_('partners').some(p => String(p['店家編號']) === s && p['狀態'] === '邀請中')", c1['id']))
        mgr_code = await ev("() => { var m = __store.mails.filter(x => x.to === 'boss.zhongli@example.com').pop(); return /invite=([A-Z0-9]+)/.exec(m.body)[1]; }")
        mgr = (await fn('authInvite', mgr_code, 'devMgr'))['v']; tokMgr = mgr['token']
        k_tea = [r2[0] for r2 in rows_b1 if r2[2] == '紅茶' and r2[3] == '中杯'][0]
        r = await fn('setPrices', {k_tea: '31'}, tokMgr)
        mgr_tea = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", c1['id'])
        hq_tea0 = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", HQ)
        check('分店店長：用邀請連結加入（夥伴身分），可以改自己分店的價格，不會動到總店', mgr['ok'] and mgr['role'] == 'staff' and 'err' not in r and mgr_tea == 31 and hq_tea0 == 28, (mgr_tea, hq_tea0))
        r = await fn('brandOverview', tokMgr); check('分店店長：不能管理分店清單', 'err' in r, r)
        # 品牌主進入分店
        ov = (await fn('brandOverview', tokI))['v']
        check('分店管理總覽：列出兩家分店（名稱、地址、電話、狀態、各自網址）', ov['ok'] and len(ov['branches']) == 2 and ov['max'] == 2 and ov['branches'][0]['address'] and 't=' in ov['branches'][0]['menuUrl'], ov)
        ob = [b for b in ov['branches'] if b['id'] == c1['id']][0]
        tokB1 = ob['menuUrl'].split('t=')[1]
        d_b1 = (await fn('getData', tokB1))['v']
        check('品牌主進入分店：用「開啟」的通行證讀到分店自己的菜單（不是總店的）', len(d_b1['rows']) == hq_rows and 'err' not in await fn('getData', tokB1))
        r = await fn('setPrices', {k_tea: '40'}, tokB1)
        hq_tea = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", HQ)
        b1_tea = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", c1['id'])
        check('分店資料獨立：改分店價格不會動到總店', b1_tea == 40 and hq_tea == 28, (b1_tea, hq_tea))
        check('品牌主進入分店：不用走設定精靈，直接進菜單工具；有「回總店」連結', 'const BRAND' in (await ev("t => doGet({ parameter: { t } }).getContent()", tokB1)) and '?p=brand\\u0026t=' in (await ev("t => doGet({ parameter: { t } }).getContent()", tokB1)).replace('?p=brand&t=', '?p=brand\\u0026t=').replace('\\/', '/') or 'BRAND_BACK' in (await ev("t => doGet({ parameter: { t } }).getContent()", tokB1)))
        r = await fn('brandOverview', tokB1); check('分店通行證不能管理分店（只有總店）', 'err' in r, r)
        r = await fn('brandApplyDraft', tokI, None, c1['id'])
        b1_tea = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", c1['id'])
        check('把總店菜單套用到分店：分店自己改過的價格（個別價 40）不會被蓋掉，也沒有重複新增', r['v']['ok'] and r['v']['added'] == 0 and r['v']['updated'] == 0 and b1_tea == 40, (r, b1_tea))
        cl = (await fn('brandOverridesClear', tokI, c1['id'], [], True))['v']
        b1_tea = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", c1['id'])
        check('清除個別價並套用：分店的紅茶回到總店價 28', cl['ok'] and cl['cleared'] >= 1 and b1_tea == 28, (cl, b1_tea))
        # 授權跟著總店
        lic_b = await ev("s => licOf_(shopById_(s))", c1['id']); lic_h = await ev("s => licOf_(shopById_(s))", HQ)
        check('分店授權：跟總店相同（狀態、到期日）', lic_b['expires'] == lic_h['expires'] and lic_b['mode'] == lic_h['mode'] == 'full', (lic_b, lic_h))
        await fn('brandBranchSet', tokI, c2['id'], 'suspended')
        tokB2 = [b for b in (await fn('brandOverview', tokI))['v']['branches'] if b['id'] == c2['id']][0]['menuUrl'].split('t=')[1]
        check('單獨停用一家分店：該分店被擋，總店與另一家分店不受影響', 'err' in await fn('getData', tokB2) and 'err' not in await fn('getData', tokB1) and 'err' not in await fn('getData', tokI))
        await fn('brandBranchSet', tokI, c2['id'], 'active')
        check('單獨恢復那家分店', 'err' not in await fn('getData', tokB2))
        await fn('admSetStatus', adm, HQ, 'suspended')
        check('總店被停權：分店也跟著被擋', 'err' in await fn('getData', tokB1), await fn('getData', tokB1))
        await fn('admSetStatus', adm, HQ, 'active')
        check('總店恢復：分店恢復', 'err' not in await fn('getData', tokB1))
        await fn('ownRevokeAll', tokI)
        check('總店「登出所有手機」：品牌主進入分店的通行證一併失效', 'err' in await fn('getData', tokB1))
        await ev("authStart('67890125', 'x')")
        tokI = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: shopById_(s).tv }, 1)", HQ)
        # 每日提醒只寄給總店一次
        await ev("s => { var x = shopById_(s); x.expires = addDaysStr_(todayStr_(), 7); saveShop_(x, ['expires']); }", HQ)
        n0 = await ev("__store.mails.length"); await ev("dailyJob()")
        check('每日提醒：總店到期前 7 天只寄一封（分店不重複寄）', await ev("n => __store.mails.slice(n).filter(m => m.to === 'i@example.com' && m.body.indexOf('7 天') >= 0).length", n0) == 1)
        # 顧客頁
        cust = await ev("s => doGet({ parameter: { s } }).getContent()", c1['id'])
        check('分店顧客頁：用分店名稱、地址、營業日、品牌顏色與 Logo', '匯入測試店 中壢店' in cust and '桃園市中壢區廣州路 11 號' in cust and '"primary":"#2E6B4F"' in cust.replace(' ', '') and 'data:image' in cust)
        # 瀏覽器：分店管理頁
        await ev("__store.props.branchMax = '6'")
        tokI = await ev("s => tokenMake_({ s: s, r: 'owner', u: 'owner', v: shopById_(s).tv }, 1)", HQ)
        await H.evaluate("p => openPage(p)", {'p': 'brand', 't': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function("window.__hlEnd === true && document.querySelectorAll('#list .br').length === 2", timeout=10000)
        check('分店管理頁：列出兩家分店，每家有「開啟菜單工具」「店家工具」「顧客頁」', await fr.locator('#list .br a.btn').count() == 6 and '中壢店' in await fr.inner_text('#list'))
        async with page.expect_download() as dl3:
            await fr.click('#tpl')
        tp = os.path.join(tempfile.gettempdir(), 'branch_tpl.csv'); await (await dl3.value).save_as(tp)
        tx = open(tp, encoding='utf-8-sig').read()
        check('分店清單範本：CSV 有說明、標題列與範例', '分店名,縣市,區,路號,市話,手機,營業日' in tx and '#中壢店' in tx)
        csvb = ('分店名,縣市,區,路號,市話,手機,營業日,營業時間,公休說明,LINE ID,店長Email,備註\r\n'
                '桃園店,桃園市,桃園區,中正路 1 號,03-333-4444,0933-222-111,一二三四五六,08:00–15:00,,,,\r\n'
                '壞資料店,台北市,,忠孝東路,,,,,,,,\r\n'
                '#註解,,,,,,,,,,,\r\n'
                '板橋店,新北市,板橋區,文化路 5 號,02-2222-3333,,週一至週五,,,@banqiao,,\r\n')
        fb = os.path.join(tempfile.gettempdir(), 'branches.csv'); open(fb, 'w', encoding='utf-8-sig', newline='').write(csvb)
        await fr.set_input_files('#file', fb)
        await fr.wait_for_selector('#prev table', timeout=8000)
        pv = await fr.inner_text('#prev')
        check('分店清單上傳：預覽表顯示每家的整理結果，有問題的列標紅並說明（縣市和區要一起填）', '桃園市桃園區中正路 1 號' in pv and '✓ 可建立' in pv and '✗' in pv and '一起填' in pv and '註解' not in pv, pv)
        check('分店清單上傳：統計「2 家可以建立、1 家有問題」，按鈕顯示要建立幾家', '2 家可以建立' in await fr.inner_text('#msg') and '1 家有問題' in await fr.inner_text('#msg') and '建立 2 家分店' in await fr.inner_text('#create'))
        await fr.click('#create')
        await fr.wait_for_function("document.querySelector('#msg').textContent.includes('完成')", timeout=60000)
        check('分店批量建立：逐家建立，完成後列表更新為 4 家', '建立了 2 家分店' in await fr.inner_text('#msg') and await fr.locator('#list .br').count() == 4, await fr.inner_text('#msg'))
        pcs = await ev("s => allShops_().filter(x => x.brandId === s).map(x => x.role + ':' + x.name).length", HQ)
        check('分店批量建立：授權中心多了兩家分店', pcs == 4, pcs)
        # 菜單批量套用（總店 → 勾選的分店）
        await fr.evaluate("document.querySelectorAll('#syncList [data-sync]')[3].checked = true")
        await fr.click('#sync'); await fr.wait_for_function("document.querySelector('#msg2').textContent.includes('同步完成')", timeout=60000)
        newb = [b for b in (await fn('brandOverview', tokI))['v']['branches']][3]
        nrows = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0]).length", newb['id'])
        check('分店管理頁：勾選分店按「套用」，總店菜單同步過去（新建的分店已經有同樣的品項，所以只更新、沒新增）', nrows == hq_rows, (nrows, hq_rows))
        # 菜單範本匯入時，同步套用到勾選的分店
        await H.evaluate("p => openPage(p)", {'t': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('總店菜單工具：有「分店」連結（顯示分店數）', await fr.is_visible('#brandLink') and '分店 4' in await fr.inner_text('#brandLink'), await fr.inner_text('#brandLink'))
        await fr.click('#impBtn'); await fr.wait_for_selector('#impModal.open')
        async with page.expect_download() as dl4:
            await fr.click('#impExp')
        ep = os.path.join(tempfile.gettempdir(), 'hq_export.csv'); await (await dl4.value).save_as(ep)
        edited = open(ep, encoding='utf-8-sig').read().replace('飲料,中杯|大杯,紅茶,28,35', '飲料,中杯|大杯,紅茶,33,38')
        fe = os.path.join(tempfile.gettempdir(), 'hq_edit.csv'); open(fe, 'w', encoding='utf-8-sig', newline='').write(edited)
        await fr.set_input_files('#impFile', fe)
        await fr.wait_for_selector('#ai2', state='visible', timeout=8000)
        check('範本匯入：檢查畫面出現「同時套用到分店」勾選清單（4 家）', await fr.locator('#aiBrList [data-br]').count() == 4)
        await fr.evaluate("document.querySelectorAll('#aiBrList [data-br]')[0].checked = true")
        await fr.click('#aiApply'); await page.wait_for_timeout(4000)
        ids = [b['id'] for b in (await fn('brandOverview', tokI))['v']['branches']]
        teas = [await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", i) for i in [HQ] + ids]
        check('範本匯入到多店：總店與勾選的第一家分店紅茶變 33，其他分店不變（28）', teas[0] == 33 and teas[1] == 33 and teas[2:] == [28, 28, 28], teas)

        # ================= 24. 多門市第二階段：品牌主檔共用（預覽差異、同步、跟隨開關）=================
        import base64 as _b64b, io as _iob
        _im2 = _PI.new('RGBA', (1700, 1700), (0, 0, 0, 0)); _PD.Draw(_im2).rectangle([200, 200, 1500, 1500], fill=(10, 60, 160, 255)); _bf2 = _iob.BytesIO(); _im2.save(_bf2, 'PNG')
        logo2_b64 = _b64b.b64encode(_bf2.getvalue()).decode()
        ovs = (await fn('brandOverview', tokI))['v']['branches']; ids_all = [b['id'] for b in ovs]
        B1, B2 = ids_all[0], ids_all[1]
        check('分店總覽：每家分店帶出「跟隨品牌」設定（預設全部跟隨）', all(all(b['follow'].values()) and len(b['follow']) == 5 for b in ovs), ovs[0]['follow'])
        pr_rows = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", HQ)
        sid_dessert = [r[0].split('|')[0] for r in pr_rows if r[1] == '甜點'][0]
        # 總店做一輪變更
        await fn('ownThemeSave', tokI, {'primary': '#1F6FB2', 'accent': '#F26B5B'})
        await fn('ownCfgSave', tokI, {'name': '匯入測試店', 'tagline': '新標語：一起更好', 'openDays': [1, 2, 3, 4, 5, 6, 0], 'hours': '07:00–14:00', 'lineId': '@brandhq'})
        await ev("([t, b]) => tSaveLogo({ b64: b, origW: 1700, origH: 1700, origType: 'image/png', origBytes: 5000, bgMode: 'transparent', bg: null, bgManual: '' }, t)", [tokI, logo2_b64])
        await fn('menuImportApply', {'sections': [{'title': '湯品', 'columns': ['小', '大'], 'items': [{'name': '玉米濃湯', 'prices': [40, 60], 'star': True, 'tags': ['milk']}, {'name': '蛋花湯', 'prices': [30, 45]}]}]}, tokI)
        k_tea_hq = [r[0] for r in pr_rows if r[2] == '紅茶' and r[3] == '中杯'][0]
        await fn('setPrices', {k_tea_hq: '36'}, tokI)
        await fn('deleteItem', sid_dessert + '|布丁', tokI)
        # 分店 B1 自己多一個品項
        tokB1 = [b for b in (await fn('brandOverview', tokI))['v']['branches'] if b['id'] == B1][0]['menuUrl'].split('t=')[1]
        await fn('addItem', {'sid': sid_dessert, 'cat': '甜點', 'name': '分店限定酥', 'cols': [{'spec': '', 'price': '77'}]}, tokB1)
        ALL = {'theme': True, 'logo': True, 'info': True, 'struct': True, 'menu': True}
        pv = (await fn('brandSyncCheck', tokI, B1, ALL, {}))['v']
        rp = pv['report']
        check('同步預覽：列出外觀、Logo、標語、分類、菜單各自的差異（還沒改動任何東西）',
              rp['theme']['changed'] and rp['logo']['changed'] and rp['info']['changed'] and rp['struct']['changed'] and '新增 1 個分類' in rp['struct']['detail'] and rp['menu']['added'] == 2 and rp['menu']['updated'] >= 1 and rp['menu']['removed'] == 0, rp)
        before = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0]).length", B1)
        check('同步預覽：不會動到分店資料', before == len(rows_b1) + 1 or before > 0 and await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')).primary; }", B1) == '#2E6B4F')
        pv2 = (await fn('brandSyncCheck', tokI, B1, {'menu': True}, {'prune': True}))['v']['report']['menu']
        check('同步預覽：勾選「移除總店沒有的品項」會多出移除數（總店刪掉的布丁、分店自己多的品項）', pv2['removed'] == 2, pv2)
        r = await fn('brandSync', tokI, B1, {}, {}); check('同步：沒選任何項目被擋', 'err' in r or not r['v']['ok'], r)
        r = await fn('brandSync', tokI, 'S9999', ALL, {}); check('同步：找不到的分店被擋', not r['v']['ok'], r)
        r = await fn('brandSync', tokB1, B1, ALL, {}); check('同步：分店通行證不能發動同步（只有總店）', 'err' in r, r)
        r = await fn('brandSync', tokWS, B1, ALL, {}); check('同步：夥伴不能發動同步', 'err' in r, r)
        old_logo_id = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('t_logo')).fileId; }", B1)
        res = (await fn('brandSync', tokI, B1, ALL, {}))['v']
        check('同步（不移除）：回報各項已套用', res['ok'] and all(res['report'][k]['changed'] for k in ['theme', 'logo', 'info', 'struct', 'menu']), res)
        cfgs = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')); }", B1)
        check('同步：外觀、標語更新；分店自己的地址、電話、營業日、營業時間、LINE 不被動到', cfgs['primary'] == '#1F6FB2' and cfgs['accent'] == '#F26B5B' and cfgs['tagline'] == '新標語：一起更好' and cfgs['address'] == '桃園市中壢區廣州路 11 號' and cfgs['phone'] == '03-458-8229／0912-345-678' and cfgs['openDays'] == [1, 2, 3, 4, 5] and cfgs['hours'] == '06:00–13:00' and cfgs['lineUrl'] == 'https://line.me/R/ti/p/%40zhongli', cfgs)
        lg = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; var m = JSON.parse(props_().getProperty('t_logo')); return [m.fileId, m.srcId, m.w]; }", B1)
        hq_logo = await ev("t => { authGuard_(t, false); return JSON.parse(props_().getProperty('t_logo')).fileId; }", tokI)
        check('同步：Logo 換成總店新的（分店有自己的副本、記住來源），舊 Logo 檔丟進垃圾桶', lg[1] == hq_logo and lg[0] != hq_logo and lg[0] != old_logo_id and lg[2] == 1700 and await ev("id => __store.files[id].trashed === true", old_logo_id), (lg, old_logo_id))
        rows_n = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", B1)
        names = {r[2] for r in rows_n}
        tea_n = [r[4] for r in rows_n if r[2] == '紅茶' and r[3] == '中杯'][0]
        check('同步（不移除）：新品項新增（湯品）、價格更新（紅茶 36）、總店刪掉的布丁與分店自己的品項都還在', {'玉米濃湯', '蛋花湯'} <= names and tea_n == 36 and '布丁' in names and '分店限定酥' in names, names)
        sec_n = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('sections')).map(x => x.t + ':' + x.cols.join('/')); }", B1)
        check('同步：分類結構一致（有「湯品：小/大」）', '湯品:小/大' in sec_n, sec_n)
        again = (await fn('brandSyncCheck', tokI, B1, ALL, {}))['v']['report']
        check('同步完成後再預覽：全部「一樣，不用動」（同步可以重複做）', not any(again[k].get('changed') for k in ['theme', 'logo', 'info', 'struct']) and again['menu']['added'] == 0 and again['menu']['updated'] == 0, again)
        res = (await fn('brandSync', tokI, B1, {'menu': True}, {'prune': True}))['v']
        rows_p = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", B1)
        names_p = {r[2] for r in rows_p}
        check('同步（移除）：分店跟總店品項一致——布丁、分店限定酥被移除，其他品項、價格不變', res['report']['menu']['removed'] == 2 and '布丁' not in names_p and '分店限定酥' not in names_p and '玉米濃湯' in names_p and len(rows_p) == len(rows_n) - 2, (res, len(rows_p), len(rows_n)))
        # 跟隨開關
        r = (await fn('brandFollowSet', tokI, B2, {'theme': False, 'logo': True, 'info': True, 'struct': True, 'menu': False}))['v']
        check('跟隨開關：存起來（外觀、菜單不跟隨）', r['ok'] and r['follow']['theme'] is False and r['follow']['menu'] is False and r['follow']['logo'] is True, r)
        res2 = (await fn('brandSync', tokI, B2, ALL, {}))['v']['report']
        cf2 = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')); }", B2)
        rows2 = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.slice(5).filter(r => r[0])", B2)
        check('跟隨開關：不跟隨的項目同步時略過（外觀、菜單沒動），其他照常同步（標語、Logo、分類）', res2['theme'].get('skipped') and res2['menu'].get('skipped') and cf2['primary'] == '#2E6B4F' and cf2['tagline'] == '新標語：一起更好' and res2['logo']['changed'] and res2['struct']['changed'] and not any(r[2] == '玉米濃湯' for r in rows2), (res2, cf2.get('primary')))
        r = await fn('brandFollowSet', tokB1, B2, {}); check('跟隨開關：分店通行證不能改', 'err' in r, r)
        check('授權中心紀錄同步與跟隨設定', await ev("() => cRows_('logs').some(l => l['動作'] === '品牌同步') && cRows_('logs').some(l => l['動作'] === '設定分店跟隨品牌')"))
        # 瀏覽器：分店管理頁
        await fn('ownThemeSave', tokI, {'primary': '#1F6FB2', 'accent': '#2BA89B'})
        await fn('setPrices', {k_tea_hq: '38'}, tokI)
        await H.evaluate("p => openPage(p)", {'p': 'brand', 't': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function("window.__hlEnd === true && document.querySelectorAll('#list .br').length >= 2", timeout=10000)
        check('分店管理頁：每家分店卡片有 5 個「跟隨品牌」勾選，反映目前設定（B2 的外觀、菜單沒勾）', await fr.locator('#list [data-fol] [data-k]').count() == 5 * len(ids_all) and not await fr.evaluate(f"document.querySelector('[data-fol=\"{B2}\"] [data-k=theme]').checked") and await fr.evaluate(f"document.querySelector('[data-fol=\"{B2}\"] [data-k=logo]').checked"))
        await fr.evaluate(f"(() => {{ const c = document.querySelector('[data-fol=\"{B2}\"] [data-k=menu]'); c.checked = true; c.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()")
        await page.wait_for_timeout(700)
        check('分店管理頁：勾選「菜單」跟隨，立刻存到伺服器', (await ev("s => followOf_(shopById_(s))", B2))['menu'] is True)
        await fr.evaluate("document.querySelectorAll('#syncList [data-sync]').forEach(x => { x.checked = true; })")
        await fr.click('#check'); await fr.wait_for_function("document.querySelector('#msg2').textContent.includes('預覽')", timeout=60000)
        rep = await fr.inner_text('#synRep')
        check('分店管理頁：預覽差異，每家分店列出各項目前後差異與「一樣，不用動」', rep.count('外觀') >= 2 and '一樣，不用動' in rep and '紅茶' not in rep and ('更新' in rep), rep[:300])
        pre = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')).accent; }", B1)
        check('分店管理頁：預覽不會改動分店', pre == '#F26B5B', pre)
        await fr.click('#sync'); await fr.wait_for_function("document.querySelector('#msg2').textContent.includes('同步完成')", timeout=90000)
        post = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')).accent; }", B1)
        post2 = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return JSON.parse(props_().getProperty('cfg')).accent; }", B2)
        tea2 = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]", B1)
        check('分店管理頁：按「開始同步」——跟隨的分店換成新強調色與新價格（B1 紅茶 38）；B2 外觀仍不跟隨', post == '#2BA89B' and tea2 == 38 and post2 == '#E8A33D', (post, post2, tea2))

        # ================= 25. 多門市第三階段：分店價格規則與個別價、跨店調價、跨店公告 =================
        TEA = "s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[4]"
        SOUP = "s => { var r = __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '玉米濃湯' && r[3] === '大'); return r ? r[4] : null; }"
        ids_now = [b['id'] for b in (await fn('brandOverview', tokI))['v']['branches']]
        P1, P2 = ids_now[0], ids_now[1]
        await fn('setPrices', {k_tea_hq: '40'}, tokI)
        await fn('brandSync', tokI, P1, {'menu': True}, {}); await fn('brandSync', tokI, P2, {'menu': True}, {})
        # --- 價格規則：總店價 +10%，取整到 5 ---
        r = await fn('brandPricingSet', tokI, P1, {'mode': 'pct', 'value': 600, 'round': 5}, False); check('價格規則：百分比超出範圍被擋', not r['v']['ok'] and '百分比' in r['v']['msg'], r)
        r = await fn('brandPricingSet', tokI, P1, {'mode': 'amt', 'value': 9999}, False); check('價格規則：金額超出範圍被擋', not r['v']['ok'], r)
        r = await fn('brandPricingSet', tokB1, P1, {'mode': 'pct', 'value': 10, 'round': 5}, True); check('價格規則：分店通行證不能設定', 'err' in r, r)
        rs = (await fn('brandPricingSet', tokI, P1, {'mode': 'pct', 'value': 10, 'round': 5}, True))['v']
        soup_hq = await ev("t => { authGuard_(t, false); var r = getData_().rows.find(x => x.name === '玉米濃湯' && x.spec === '大'); return r.p; }", tokI)
        check('價格規則：儲存並套用——分店價變成「總店價 +10% 取整到 5」（紅茶中杯 40 → 45、玉米濃湯大 60 → 65）', rs['ok'] and rs['applied'] and (await ev(TEA, P1)) == 45 and (await ev(SOUP, P1)) == 65 and soup_hq == '60', (rs, await ev(TEA, P1)))
        check('價格規則：只動分店，總店價不變；另一家沒設規則的分店也不變', (await ev(TEA, HQ)) == 40 and (await ev(TEA, P2)) == 40)
        ov = (await fn('brandOverview', tokI))['v']['branches'][0]
        check('分店總覽帶出價格規則（+10%、取整 5、個別價 0 項）', ov['pricing']['mode'] == 'pct' and ov['pricing']['value'] == 10 and ov['pricing']['round'] == 5 and ov['pricing']['overrides'] == 0, ov['pricing'])
        # --- 分店改價 → 自動記成個別價 ---
        tokP1 = [b for b in (await fn('brandOverview', tokI))['v']['branches'] if b['id'] == P1][0]['menuUrl'].split('t=')[1]
        k_tea_b = await ev("s => __store.books[shopById_(s).ssId].sheets['價格表'].data.find(r => r[2] === '紅茶' && r[3] === '中杯')[0]", P1)
        await fn('setPrices', {k_tea_b: '50'}, tokP1)
        pg = (await fn('brandPricingGet', tokI, P1))['v']
        check('分店改價自動記成個別價（紅茶中杯 50），列出分類、品項、規格、價格', len(pg['overrides']) == 1 and pg['overrides'][0]['name'] == '紅茶' and pg['overrides'][0]['spec'] == '中杯' and pg['overrides'][0]['price'] == 50, pg)
        await fn('setPrices', {k_tea_hq: '44'}, tokI)
        await fn('brandSync', tokI, P1, {'menu': True}, {})
        check('品牌同步：有個別價的品項不被蓋掉（仍 50），沒有的照「總店價 +10%」算（玉米濃湯大仍 65）', (await ev(TEA, P1)) == 50 and (await ev(SOUP, P1)) == 65, (await ev(TEA, P1)))
        # --- 跨店調價 ---
        r = await fn('brandAdjustCheck', tokI, {'mode': 'amt', 'value': 0}); check('跨店調價：沒填數字被擋', not r['v']['ok'], r)
        r = await fn('brandAdjustCheck', tokI, {'mode': 'pct', 'value': 500}); check('跨店調價：百分比超出範圍被擋', not r['v']['ok'], r)
        r = await fn('brandAdjustCheck', tokP1, {'mode': 'amt', 'value': 5}); check('跨店調價：分店通行證不能用', 'err' in r, r)
        spec = {'scope': '湯品', 'mode': 'amt', 'value': 5, 'round': 5, 'overrides': False, 'branches': [P1, P2]}
        pv = (await fn('brandAdjustCheck', tokI, spec))['v']['report']
        check('跨店調價預覽：總店湯品 4 個價格會變動（2 個品項×小大），各分店變動數也列出', pv['hq']['count'] == 4 and pv['hq']['sample'][0]['title'] == '湯品' and all(b.get('updated', 0) > 0 for b in pv['branches']), pv)
        check('跨店調價預覽：還沒改動任何價格', (await ev(SOUP, HQ)) == 60 and (await ev(SOUP, P1)) == 65 and (await ev(SOUP, P2)) == 60)
        ad = (await fn('brandAdjust', tokI, spec))['v']
        check('跨店調價套用：總店 +5（玉米濃湯大 60 → 65）', ad['ok'] and (await ev(SOUP, HQ)) == 65, ad)
        check('跨店調價套用：同價的分店跟著 +5（65）；有 +10% 規則的分店依規則算（65×1.1 取整 5 → 70）', (await ev(SOUP, P2)) == 65 and (await ev(SOUP, P1)) == 70, (await ev(SOUP, P1)))
        check('跨店調價套用：不在範圍的品項（紅茶）總店、分店都不變', (await ev(TEA, HQ)) == 44 and (await ev(TEA, P1)) == 50)
        check('跨店調價：寫進各家的修改紀錄與授權中心紀錄', await ev("s => __store.books[shopById_(s).ssId].sheets['修改紀錄'].data.some(r => r[5] === '跨店調價')", HQ) and await ev("() => cRows_('logs').some(l => l['動作'] === '跨店調價')"))
        spec2 = {'scope': '', 'mode': 'amt', 'value': 3, 'round': 1, 'overrides': True, 'branches': [P1]}
        await fn('brandAdjust', tokI, spec2)
        check('跨店調價：勾選「個別價也一起調」——分店的個別價紅茶 50 → 53；沒勾的另一家分店這次不連動', (await ev(TEA, P1)) == 53 and (await ev(TEA, HQ)) == 47 and (await ev(TEA, P2)) == 44, (await ev(TEA, P1), await ev(TEA, HQ), await ev(TEA, P2)))
        await fn('brandFollowSet', tokI, P2, {'theme': True, 'logo': True, 'info': True, 'struct': True, 'menu': False})
        pvf = (await fn('brandAdjustCheck', tokI, {'scope': '', 'mode': 'amt', 'value': 1, 'branches': [P2]}))['v']['report']
        check('跨店調價：設為「不跟隨菜單」的分店會略過並說明', pvf['branches'][0].get('skipped') and '不跟隨' in pvf['branches'][0]['skipped'], pvf)
        await fn('brandFollowSet', tokI, P2, {'theme': True, 'logo': True, 'info': True, 'struct': True, 'menu': True})
        # --- 恢復跟隨 ---
        cl = (await fn('brandOverridesClear', tokI, P1, [], True))['v']
        check('恢復跟隨：清除個別價並套用——紅茶回到「總店價 47 +10% 取整 5」= 50', cl['ok'] and cl['cleared'] >= 1 and (await ev(TEA, P1)) == 50, (cl, await ev(TEA, P1)))
        check('恢復跟隨：個別價清空', (await fn('brandPricingGet', tokI, P1))['v']['overrides'] == [])
        await fn('brandPricingSet', tokI, P1, {'mode': 'same'}, True)
        check('價格規則：改回「同總店價」並套用，分店價回到總店價（紅茶 47）', (await ev(TEA, P1)) == 47, await ev(TEA, P1))
        # --- 跨店公告 ---
        notice = (await fn('tSaveNotice', {'title': '連假營業調整', 'start': '2026-10-01', 'end': '2099-12-31', 'show': True, 'content': {'cat': 'hours', 'lead': '連假照常營業', 'tag': '公告'}}, tokI))['v']
        nl = (await fn('brandNoticeList', tokI))['v']['notices']
        check('跨店公告：列出總店的公告（標題、類別、期間）', any(n['id'] == notice['id'] and n['title'] == '連假營業調整' and n['cat'] == '營業時間調整' for n in nl), nl)
        r = await fn('brandPushNotice', tokI, 'N000', [P1]); check('跨店公告：找不到的公告被擋', not r['v']['ok'], r)
        r = await fn('brandPushNotice', tokI, notice['id'], []); check('跨店公告：沒勾分店被擋', not r['v']['ok'], r)
        r = await fn('brandPushNotice', tokP1, notice['id'], [P1]); check('跨店公告：分店通行證不能發佈', 'err' in r, r)
        pr = (await fn('brandPushNotice', tokI, notice['id'], [P1, P2]))['v']
        check('跨店公告：發佈到兩家分店', pr['ok'] and len(pr['results']) == 2 and not any(x['updated'] for x in pr['results']), pr)
        cust1 = await ev("s => doGet({ parameter: { s } }).getContent()", P1)
        check('跨店公告：分店顧客頁顯示這則公告', '連假營業調整' in cust1 and '連假照常營業' in cust1)
        await fn('tSaveNotice', {'id': notice['id'], 'title': '連假營業調整（更新）', 'start': '2026-10-01', 'end': '2099-12-31', 'show': True, 'content': {'cat': 'hours', 'lead': '連假改為 8 點開門', 'tag': '公告'}}, tokI)
        pr2 = (await fn('brandPushNotice', tokI, notice['id'], [P1]))['v']
        cnt = await ev("s => { var b = shopById_(s); CTX = { shopId: b.id, ssId: b.ssId, shop: b }; _spMap = null; return tListNotices_(30).filter(x => x.title.indexOf('連假營業調整') === 0).length; }", P1)
        cust1 = await ev("s => doGet({ parameter: { s } }).getContent()", P1)
        check('跨店公告：重複發佈同一則是「更新」（只有一則，內容更新），不會變兩則', pr2['results'][0]['updated'] and cnt == 1 and '連假改為 8 點開門' in cust1 and '連假照常營業' not in cust1, (pr2, cnt))
        await fn('brandBranchSet', tokI, P2, 'suspended')
        pr3 = (await fn('brandPushNotice', tokI, notice['id'], [P2]))['v']
        check('跨店公告：停用的分店會略過並說明', pr3['results'][0].get('skipped'), pr3)
        await fn('brandBranchSet', tokI, P2, 'active')
        # --- 瀏覽器 ---
        await H.evaluate("p => openPage(p)", {'p': 'brand', 't': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function("window.__hlEnd === true && document.querySelectorAll('#list .br').length >= 2", timeout=10000)
        check('分店管理頁：每家分店卡片有價格規則（方式、數字、取整、儲存並套用、個別價 N 項）', await fr.locator('#list [data-prc] .pm').count() == len(ids_now) + 2 or await fr.locator('#list [data-prc] .pm').count() >= 2)
        await fr.select_option('#aScope', '湯品'); await fr.select_option('#aMode', 'amt'); await fr.fill('#aVal', '2'); await fr.select_option('#aRound', '1')
        await fr.evaluate("document.querySelectorAll('#aList [data-b]').forEach(x => { x.checked = true; })")
        await fr.click('#aCheck'); await fr.wait_for_function("document.querySelector('#msg3').textContent.includes('預覽')", timeout=60000)
        rep = await fr.inner_text('#aRep')
        check('分店管理頁：跨店調價預覽顯示總店變動明細（舊價 → 新價）與各分店變動數', '總店：4 項價格會變動' in rep and '68 → 70' in rep and '個品項的價格會變動' in rep, rep[:300])
        before = await ev(SOUP, HQ)
        check('分店管理頁：預覽不改價', before == 68)
        await fr.click('#aGo'); await fr.wait_for_function("document.querySelector('#msg3').textContent.includes('調價完成')", timeout=90000)
        check('分店管理頁：按「套用調價」總店湯品 +2（68 → 70）', (await ev(SOUP, HQ)) == 70, await ev(SOUP, HQ))
        await fr.wait_for_function("document.querySelectorAll('#nSel option').length >= 1 && !document.querySelector('#nSel').textContent.includes('讀不到')", timeout=10000)
        check('分店管理頁：跨店公告下拉列出總店公告', '連假營業調整' in await fr.inner_text('#nSel'))
        await fr.evaluate("document.querySelectorAll('#nList [data-b]').forEach(x => { x.checked = true; })")
        await fr.click('#nGo'); await fr.wait_for_function("document.querySelector('#msg4').textContent.includes('完成')", timeout=40000)
        check('分店管理頁：發佈公告後顯示各分店結果（已更新）', '已更新分店上的這則公告' in await fr.inner_text('#nRep'), await fr.inner_text('#nRep'))
        # 個別價清單
        await fn('setPrices', {k_tea_b: '61'}, tokP1)
        await H.evaluate("p => openPage(p)", {'p': 'brand', 't': tokI})
        fr = H.child_frames[0]
        await fr.wait_for_function("window.__hlEnd === true && document.querySelectorAll('#list .br').length >= 2", timeout=10000)
        await fr.click(f'[data-prc="{P1}"] [data-ovr]')
        await fr.wait_for_selector(f'[data-ovl="{P1}"] .it', timeout=8000)
        check('分店管理頁：點「個別價 N 項」列出分店自己的價格，並說明不會被同步蓋掉', '紅茶' in await fr.inner_text(f'[data-ovl="{P1}"]') and '61' in await fr.inner_text(f'[data-ovl="{P1}"]') and '不會蓋掉' in await fr.inner_text(f'[data-ovl="{P1}"]'))

        # 單店模式不受影響
        # ================= 26. 瀏覽器：開通連結 ?p=activate → 設定密碼 → 直接登入 =================
        r = (await fn('admSaveShop', adm, {'name': '開通測試店', 'taxId': '55667788', 'owner': 'c', 'email': 'act@example.com', 'plan': 'pro', 'skipTaxCheck': True, 'start': 'pilot'}))['v']
        check('開通信寄出', r['ok'] and r['mailed'], r)
        await H.evaluate("p => openPage(p)", {'p': 'activate'})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true')
        check('開通連結直接打開「首次開通」', await fr.is_visible('#v-reset') and '首次開通' in await fr.inner_text('#v-reset'))
        await fr.fill('#pTax', '55667788'); await fr.click('#pSend')
        await fr.wait_for_selector('#p2:not(.hide)')
        mid = await link_of('act@example.com')
        await H.evaluate("p => openPage(p)", {'ml': mid})          # 按信裡的「設定密碼」
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true')
        await fr.evaluate("window.__go = []; goTop = u => window.__go.push(u); true")
        await fr.wait_for_selector('#m2:not(.hide)')
        check('設定密碼連結：直接出現設定密碼（不用輸入驗證碼）', '首次開通' in await fr.inner_text('#mTitle') and await fr.locator('#pOtp').count() == 0)
        await fr.fill('#mNew', 'myShop2026'); await fr.fill('#mNew2', 'myShop2027'); await fr.click('#mDone')
        await fr.wait_for_function("document.querySelector('#msgM').textContent.includes('不一樣')")
        check('設定密碼：兩次輸入不一樣被擋', True)
        await fr.fill('#mNew2', 'myShop2026'); await fr.click('#mDone')
        await fr.wait_for_function("window.__go.length > 0")
        tk = await fr.evaluate("localStorage.getItem('hl-token')")
        check('開通頁：設定密碼後直接登入並跳到主畫面，帳號是試營運', 'p=home' in await fr.evaluate("window.__go[0]") and (await ev("t => authCheck(t)", tk))['lic']['label'] == '試營運')
        await H.evaluate("p => openPage(p)", {})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true')
        await fr.evaluate("localStorage.clear()")
        await H.evaluate("p => openPage(p)", {})
        fr = H.child_frames[0]
        await fr.wait_for_function('window.__hlEnd === true')
        check('登入頁連結改名為「首次開通／忘記密碼」', '首次開通' in await fr.inner_text('#toReset'))
        await fr.fill('#taxId', '12341234'); await fr.fill('#pw', 'whatever1'); await fr.click('#send')
        await fr.wait_for_function("document.querySelector('#msg').textContent.includes('首次開通')")
        check('登入失敗時提示「第一次使用請按首次開通」', True)
        await fr.click('#toReset')
        check('按「首次開通」會帶入剛輸入的統編', await fr.input_value('#pTax') == '12341234')

        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
