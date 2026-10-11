"""試營運店家（三多屋）建立測試：createPilotSanduowu() 之後，店家、免驗證碼登入、店家資料、菜單品項與標示、顧客頁。
執行：python tests/pilot_e2e.py
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
(function () { __store.props.ssId = 'test'; var p = __ss.insertSheet('價格表'); p.data = [['x'], [''], [''], [''], ['代碼']]; })();
"""
HOST = """<!doctype html><html><head><meta charset="utf-8"><script>window.__REAL_CODE = true;</script>
<script src="/mock.js"></script><script src="/Code.gs.js"></script><script src="/Tools.gs.js"></script><script src="/Tenant.gs.js"></script><script src="/Mail.gs.js"></script><script src="/Auth.gs.js"></script><script src="/Billing.gs.js"></script><script src="/Provision.gs.js"></script><script src="/Shop.gs.js"></script><script src="/BrandServer.gs.js"></script><script src="/StaffServer.gs.js"></script><script src="/LedgerServer.gs.js"></script><script src="/HomeServer.gs.js"></script><script src="/PilotData.gs.js"></script><script src="/saas_mock.js"></script>
<script>window.__FILES = %s;</script><script src="/seed.js"></script></head><body></body></html>"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await (await b.new_context()).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        async def route(r):
            u = r.request.url
            if u == 'http://t/': return await r.fulfill(body=HOST % files_json(), content_type='text/html; charset=utf-8')
            if u.endswith('/mock.js'): return await r.fulfill(path=os.path.join(T, 'tools_mock.js'), content_type='text/javascript')
            if u.endswith('/saas_mock.js'): return await r.fulfill(path=os.path.join(T, 'saas_mock.js'), content_type='text/javascript')
            if u.endswith('/Code.gs.js'): return await r.fulfill(path=os.path.join(SRC, 'Code.gs'), content_type='text/javascript')
            if u.endswith('/Tools.gs.js'): return await r.fulfill(path=os.path.join(SRC, 'ToolsServer.gs'), content_type='text/javascript')
            m = re.search(r'/(Tenant|Mail|Auth|Billing|Provision|Shop|BrandServer|StaffServer|LedgerServer|HomeServer|PilotData)\.gs\.js$', u)
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

        await ev("setupCenter()")
        check('統編 27323989 通過檢查碼', await ev("taxIdOk_('27323989')"))
        r = await fn('createPilotSanduowu'); sid = r['v']['id'] if 'v' in r else ''
        check('建立試營運店家：成功並新增 24 個品項', 'err' not in r and r['v']['added'] == 24, r)
        s = await ev("s => shopById_(s)", sid)
        check('店家資料：公司名稱、統編、負責人、使用中、有試算表', s['name'] == '三多屋國際事業有限公司' and s['taxId'] == '27323989' and s['owner'] == '李奕立' and s['status'] == 'active' and bool(s['ssId']), s)
        check('試營運：統編加入免驗證碼清單', '27323989' in await ev("__store.props.testAccounts"))
        n0 = await ev("__store.mails.length")
        r = await ev("authStart('27323989', 'Test27323989')"); check('登入：統編＋密碼正確就直接通過、不寄信', r['ok'] and r.get('bypass') and await ev("__store.mails.length") == n0, r)
        r = await ev("authVerify('27323989', '', 'dev1')"); check('登入：驗證碼空白也能登入', r['ok'] and r['token'], r)
        tok = r['token']
        r = await ev("authStart('27323989', 'Wrong12345')"); check('登入：密碼錯誤仍然擋', not r['ok'], r)
        d = (await fn('getData', tok))['v']
        names = [x['name'] for x in d['rows']]
        check('菜單：24 個品項（含編號），分類是熟食、蓋飯、壽司、麵食、小菜', len(d['rows']) == 24 and sorted(set(x['cat'] for x in d['rows'])) == sorted(['熟食', '蓋飯', '壽司', '麵食', '小菜']), (len(d['rows']), set(x['cat'] for x in d['rows'])))
        row = lambda n: [x for x in d['rows'] if x['name'] == n][0]
        check('菜單：價格正確（鮪魚蓋飯 880、白蝦拉麵 250、鱈魚肝 150、味噌湯 50）', row('4 超級豪華鮪魚蓋飯')['p'] == '880' and row('11 白蝦拉麵')['p'] == '250' and row('20 鱈魚肝')['p'] == '150' and row('21 味噌湯')['p'] == '50')
        check('菜單：價格看不到的「7 全鮭蓋飯」價格留空待補', row('7 全鮭蓋飯')['p'] == '', row('7 全鮭蓋飯'))
        check('菜單：招牌星號、限量說明、過敏與辣標示', row('1 三多屋特餐（炒飯＋鯖魚）')['star'] and row('2 鹽烤鮭魚親子丼')['side'] == '限量' and 'spicy' in row('17 辣味螺肉')['tags'] and 'shellfish' in row('18 龍蝦沙拉')['tags'], (row('17 辣味螺肉'), row('18 龍蝦沙拉')))
        cfg = await ev("s => { CTX = { shopId: s, ssId: shopById_(s).ssId, role: 'owner', shop: shopById_(s) }; _spMap = null; return shopCfg_(); }", sid)
        check('店家設定：店名、地址、電話、營業時間、公休、營業日（週二至週日）', cfg['name'] == '三多屋爸爸嘴' and '太原路19號1樓' in cfg['address'] and cfg['phone'] == '02-2555-7708' and cfg['hours'].startswith('週二') and cfg['closedText'] == '公休：週一' and sorted(cfg['openDays']) == [0, 2, 3, 4, 5, 6], cfg)
        cust = await ev("s => doGet({ parameter: { s, p: 'menu' } }).getContent()", sid)
        check('顧客電子菜單頁可以打開', '三多屋爸爸嘴' in cust)
        menu = (await fn('getMenu', sid))['v']
        check('顧客電子菜單：看得到品項與每區說明（附味噌湯、不附湯）', '鮪魚蓋飯' in json.dumps(menu, ensure_ascii=False) and '每份附一碗味噌湯' in json.dumps(menu, ensure_ascii=False) and '此區不附湯' in json.dumps(menu, ensure_ascii=False))

        # ---------- 基本資料：桌號、Wi-Fi、班別、員工建檔、廠商、公告 ----------
        st = (await fn('tGetState', tok))['v']
        tb = st['tables']
        check('桌號 QR：12 桌＋候位區＋外帶自取，共 14 張', len(tb) == 14 and tb[0]['name'] == '第 1 桌' and tb[11]['name'] == '第 12 桌' and tb[12]['type'] == 'wait' and tb[13]['type'] == 'take', tb)
        check('桌號 QR：每張網址都指向這家店的電子菜單、而且不重複', all(('?s=' + sid + '&p=menu#') in r['url'] and r['url'].startswith('https') for r in tb) and len(set(r['url'] for r in tb)) == 14, tb[:2])
        wf = st['wifi']
        check('Wi-Fi 卡：有建立，密碼長度合法，且標明是範例值要改', wf and wf['ssid'] == 'TOCONFIRM-WIFI' and 8 <= len(wf['pass']) <= 63 and '範例' in wf['note'], wf)
        check('店家資料：主色、輔色、底部標籤（低消與附湯）已套用', st['shop']['primary'] == '#5B3A24' and st['shop']['accent'] == '#D9622B' and '低消 150' in st['shop']['chips'], st['shop'])
        nts = st['notices']
        check('公告：有一則試營運公告，勾了顧客頁顯示', len(nts) == 1 and nts[0]['title'] == '試營運公告' and nts[0]['show'] is True, nts)
        pub = (await fn('tGetNotices', sid))['v']
        check('顧客頁看得到試營運公告（含營業時間）', len(pub) == 1 and pub[0]['title'] == '試營運公告' and pub[0]['big'] == '11:00 – 20:00', pub)
        sst = (await fn('stState', tok, ''))['v']
        shifts = sst['cfg']['shifts']
        check('班別範本：早班、晚班、全天三種，遲到寬限 5 分', len(shifts) == 3 and [x['n'] for x in shifts] == ['早班', '晚班', '全天'] and shifts[0]['s'] == '10:00' and sst['cfg']['grace'] == 5, sst['cfg'])
        emps = sst['emps']
        check('員工：2 個「待填寫」名額，沒有代填姓名與 PIN', len(emps) == 2 and all(e['status'] == '待填寫' and not e['pinSet'] for e in emps), emps)
        check('員工：通用建檔連結已開啟（員工自己填，店主核准）', sst['joinOn'] is True and '&p=join&jc=' in sst['joinUrl'], sst['joinUrl'])
        lst = (await fn('lgState', tok, ''))['v']
        vds = lst['vendors']
        check('固定廠商：5 家，分類與常用金額都帶好', len(vds) == 5 and vds[0]['name'] == '魚貨（待改）' and vds[0]['cat'] == '進貨：食材' and vds[0]['quick'] == [1000, 2000, 3000, 5000] and sorted(set(v['cat'] for v in vds)) == sorted(['進貨：食材', '進貨：飲料', '進貨：包材']), vds)
        check('首次設定精靈已標記完成：店主登入直接進系統', await ev("props_().getProperty('onboarded')") == '1')

        r2 = await fn('createPilotSanduowu')
        check('重複執行不會出錯：沿用同一家店、不重複新增品項、舊登入失效（密碼重設）', 'err' not in r2 and r2['v']['id'] == sid and 'err' in await fn('getData', tok), r2)
        bs = r2['v']['basics']
        check('重複執行：桌號、Wi-Fi、班別、員工、廠商都跳過，不會變成兩份', bs['tables'] == 0 and bs['wifi'] == 0 and bs['shifts'] == 0 and bs['invites'] == 0 and bs['vendors'] == 0 and len(bs['skipped']) == 10, bs)
        r3 = await ev("authVerify('27323989', '', 'dev2')"); tok = r3['token']
        st2 = (await fn('tGetState', tok))['v']
        check('重複執行：桌號還是 14 張、公告還是 1 則（同名公告更新同一筆）', len(st2['tables']) == 14 and len(st2['notices']) == 1, (len(st2['tables']), len(st2['notices'])))
        v2 = (await fn('lgState', tok, ''))['v']['vendors']
        check('重複執行：廠商還是 5 家', len(v2) == 5, v2)
        check('待確認清單有 13 項（菜單 6 項＋基本資料 7 項）', await ev("PILOT_TODO.length") == 13)
        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
