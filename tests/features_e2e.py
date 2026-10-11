"""菜單功能測試：調價助手、過敏原／素食標示（編輯、A3 印出、顧客電子菜單篩選）。
真的 Code.gs＋Page.html＋Customer.html（單店模式，跟弘林一樣）。
執行：python tests/features_e2e.py
"""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T, SRC = os.path.join(ROOT, 'tests'), os.path.join(ROOT, 'src')
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:500]))

def files_json():
    f = {n: open(os.path.join(SRC, n + '.html'), encoding='utf-8').read() for n in ['Page', 'Customer', 'Tools', 'Login', 'Admin', 'Account', 'Setup', 'Brand']}
    return json.dumps(f).replace('</', '<\\/')

SEED = """
(function () {
  __store.props.ssId = 'test';
  var p = __ss.insertSheet('價格表');
  p.data = [['弘林'], [''], [''], [''], ['代碼']];
  ITEMS.forEach(function (it) { p.data.push([it[0], it[1], it[2], it[3], it[4], it[4], false, !!it[5], '', '']); });
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
            m = re.search(r'/(Tenant|Mail|Auth|Billing|Provision|Shop|BrandServer)\.gs\.js$', u)
            if m: return await r.fulfill(path=os.path.join(SRC, m.group(1) + '.gs'), content_type='text/javascript')
            if u.endswith('/seed.js'): return await r.fulfill(body=SEED, content_type='text/javascript')
            return await r.abort()
        await page.route('**/*', route)
        await page.goto('http://t/')
        H = page.main_frame
        async def ev(js, arg=None): return await H.evaluate(js, arg)
        async def open_(params):
            await H.evaluate('p => openPage(p)', params)
            return H.child_frames[0]
        async def row(key):
            return await ev("k => { var r = __ss.sheets['價格表'].data.find(x => x[0] === k); return r ? r[4] : null; }", key)

        # ================= 調價助手 =================
        fr = await open_({'staff': 'hl7q2x9m'})
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        before = {k: await row(k) for k in ['drink|紅茶|0', 'drink|紅茶|1', 'drink|奶茶|0', 'single|薯餅|0', 'toast|玉米／蔬菜／起司|0']}
        await fr.click('#adjBtn'); await fr.wait_for_selector('#adjModal.open')
        check('調價助手：沒填數字時不能套用', await fr.is_disabled('#adjApply'))
        await fr.select_option('#adjScope', 'drink')
        await fr.fill('#adjVal', '5')
        n_drink = await fr.locator('#adjList [data-i]').count()
        check('調價助手：只調「喝點什麼」，預覽列出該分類所有有價格的品項（+5 元）', n_drink == await fr.evaluate("Object.keys(DEFAULTS).filter(k => k.startsWith('drink|') && (prices[k] ?? '') !== '').length"), n_drink)
        txt = await fr.inner_text('#adjList')
        check('調價助手：預覽顯示「舊價 → 新價」', '25 → 30' in txt and '30 → 35' in txt, txt[:100])
        await fr.select_option('#adjMode', 'pct'); await fr.fill('#adjVal', '10'); await fr.select_option('#adjRound', '5')
        txt = await fr.inner_text('#adjList')
        check('調價助手：百分比＋取整到 5 元（25 元 +10% → 30；35 → 40）', '25 → 30' in txt and '35 → 40' in txt, txt[:200])
        await fr.select_option('#adjMode', 'amt'); await fr.select_option('#adjRound', '1'); await fr.fill('#adjVal', '5')
        await fr.uncheck('#adjList [data-i="0"]')
        sm = await fr.inner_text('#adjSum')
        check('調價助手：可以取消個別品項，統計跟著變', '已取消 1 項' in sm, sm)
        await fr.click('#adjApply')
        await fr.wait_for_function("document.querySelector('#adjMsg').textContent.includes('已調整')")
        after = {k: await row(k) for k in before}
        check('調價助手：套用後試算表價格更新（紅茶中杯被取消所以不變、其他飲料 +5）', after['drink|紅茶|0'] == before['drink|紅茶|0'] and after['drink|紅茶|1'] == int(before['drink|紅茶|1']) + 5 and after['drink|奶茶|0'] == int(before['drink|奶茶|0']) + 5, (before, after))
        check('調價助手：其他分類不受影響', after['single|薯餅|0'] == before['single|薯餅|0'] and after['toast|玉米／蔬菜／起司|0'] == before['toast|玉米／蔬菜／起司|0'])
        check('調價助手：套用後提示會用橘底標出變動，並提醒做公告', '橘底' in await fr.inner_text('#adjMsg'))
        log = await ev("__ss.sheets['修改紀錄'].data.filter(r => r[5] === '菜單工具').length")
        check('調價助手：每一項都寫進修改紀錄', log >= n_drink - 1, log)
        await fr.click('#adjUndo')
        await fr.wait_for_function("document.querySelector('#adjMsg').textContent.includes('已復原')")
        back = {k: await row(k) for k in before}
        check('調價助手：「復原上次調價」全部回到原價', back == before, (before, back))
        await fr.select_option('#adjScope', ''); await fr.select_option('#adjMode', 'amt'); await fr.fill('#adjVal', '-100000')
        check('調價助手：降太多時價格最低到 0，不會變負數', all(int(x) >= 0 for x in re.findall(r'→ (-?\d+)', await fr.inner_text('#adjList'))))
        await fr.fill('#adjVal', '0.4'); await fr.select_option('#adjRound', '1')
        check('調價助手：調整幅度被取整抵銷時，提示沒有品項會變動', await fr.locator('#adjList [data-i]').count() == 0 and '沒有品項會變動' in await fr.inner_text('#adjSum'))
        await fr.click('#adjClose')

        # ================= 標示 =================
        fr = await open_({'staff': 'hl7q2x9m'})
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('標示：伺服器提供標示清單（12 種）', await fr.evaluate("TAGDEFS.length") == 12)
        await fr.click('.it[data-name="美式"] .more >> nth=0') if False else None
        await fr.evaluate("document.querySelector('.more[data-item=\"danbing|美式\"]').click()")
        await fr.wait_for_selector('#imModal.open')
        await fr.click('#imTags [data-c="egg"]'); await fr.click('#imTags [data-c="milk"]'); await fr.click('#imTags [data-c="spicy"]')
        await fr.click('#imTagSave')
        await fr.wait_for_function("document.querySelector('#imMsg').textContent.includes('已儲存')")
        await fr.wait_for_function("!document.querySelector('#imModal').classList.contains('open')")
        tg = await ev("__ss.sheets['價格表'].data.filter(r => r[0].startsWith('danbing|美式|')).map(r => r[9])")
        check('標示：存在這個品項的每一列（蛋餅、抓餅蛋、河粉三個規格）', tg == ['egg,milk,spicy'] * 3, tg)
        check('標示：菜單工具的品項旁邊顯示標籤', await fr.locator('.it[data-name="美式"] .tg').count() == 3 or await fr.locator('.sec#sec-danbing .it:has-text("美式") .tg').count() >= 3)
        await fr.evaluate("document.querySelector('.more[data-item=\"club|海陸總匯\"]').click()")
        await fr.wait_for_selector('#imModal.open')
        await fr.click('#imTags [data-c="shellfish"]'); await fr.click('#imTags [data-c="gluten"]'); await fr.click('#imTagSave')
        await fr.wait_for_function("document.querySelector('#imMsg').textContent.includes('已儲存')")
        await fr.wait_for_function("!document.querySelector('#imModal').classList.contains('open')")
        await fr.evaluate("document.querySelector('.more[data-item=\"single|薯餅\"]').click()")
        await fr.wait_for_selector('#imModal.open')
        await fr.click('#imTags [data-c="vegan"]'); await fr.click('#imTagSave')
        await fr.wait_for_function("document.querySelector('#imMsg').textContent.includes('已儲存')")
        await fr.wait_for_function("!document.querySelector('#imModal').classList.contains('open')")
        await fr.evaluate("document.querySelector('.more[data-item=\"single|熱狗\"]').click()")
        await fr.wait_for_selector('#imModal.open')
        await fr.click('#imTags [data-c="veg"]'); await fr.click('#imTags [data-c="egg"]'); await fr.click('#imTagSave')
        await fr.wait_for_function("document.querySelector('#imMsg').textContent.includes('已儲存')")
        await fr.wait_for_function("!document.querySelector('#imModal').classList.contains('open')")
        r = await fr.evaluate("(async () => { try { await new Promise((ok, no) => google.script.run.withSuccessHandler(ok).withFailureHandler(no).setTags('single|薯餅', ['egg', 'hack', 'veg'], 'WRONG')); return 'no error'; } catch (e) { return e.message; } })()")
        check('標示：沒有權限（鑰匙錯誤）不能改', '權限' in r, r)
        await ev("setTags('single|薯餅', ['vegan', 'hack', 'vegan', ' veg '], 'hl7q2x9m')")
        check('標示：不合法的代碼被過濾、重複去掉', await ev("__ss.sheets['價格表'].data.find(r => r[0] === 'single|薯餅|0')[9]") == 'vegan,veg')
        await ev("setTags('single|薯餅', ['vegan'], 'hl7q2x9m')")
        # A3 印出
        fr = await open_({'staff': 'hl7q2x9m'})
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        sh = await fr.evaluate("sheetHTML('menu', 'V1')")
        check('標示：A3 菜單的品項後面印出小標籤（蛋、奶、辣、素…）', sh.count('class="tg') >= 3 + 2 + 1 + 2 and '>蛋<' in sh and '>辣<' in sh and 'class="tg d"' in sh and 'class="tg f"' in sh, sh.count('class="tg'))
        check('標示：頁尾有圖例說明', '含該過敏原' in sh and '純素' in sh and '辣＝辣味' in sh)
        blank = await fr.evaluate("sheetHTML('blank')")
        check('標示：空白核對表不印標籤', 'class="tg' not in blank)
        lay = await fr.evaluate("(() => { sheetHTML('menu', 'V1'); return [lastPlan.overflow, lastPlan.pageCount]; })()")
        check('標示：印了標籤後版面仍然排得下（一頁）', lay == [False, 1], lay)
        # 新增品項時選標示
        await fr.evaluate("document.querySelector('.addbtn[data-sid=\"single\"]').click()")
        await fr.wait_for_selector('#addModal.open')
        await fr.fill('#addName', '堅果沙拉'); await fr.click('#addTags [data-c="nut"]'); await fr.click('#addTags [data-c="veg"]')
        await fr.fill('#addCols input >> nth=0', '90'); await fr.click('#addOk')
        await fr.wait_for_function("!document.querySelector('#addModal').classList.contains('open')")
        check('標示：新增品項時一併選標示', await ev("__ss.sheets['價格表'].data.find(r => r[0] === 'single|堅果沙拉|0')[9]") == 'nut,veg')

        # ================= 顧客電子菜單 =================
        m = await ev("getMenu()")
        check('電子菜單：回傳分類與品項（只含有價格、沒隱藏的）', len(m['cats']) >= 8 and all(i['prices'] for c in m['cats'] for i in c['items']) and not any(i['name'] == '炸物拼盤 MIX' for c in m['cats'] for i in c['items']))
        drink = next(c for c in m['cats'] if c['name'] == '喝點什麼'); red = next(i for i in drink['items'] if i['name'] == '紅茶')
        check('電子菜單：多規格合成一筆（紅茶 中杯 25／大杯 30）', red['prices'] == [{'spec': '中杯', 'price': 25}, {'spec': '大杯', 'price': 30}], red)
        am = next(i for c in m['cats'] for i in c['items'] if i['name'] == '美式' and c['name'].startswith('蛋餅'))
        check('電子菜單：帶出標示', am['tags'] == ['egg', 'milk', 'spicy'], am)
        await ev("setHidden('drink|紅茶', true, 'hl7q2x9m')")
        m2 = await ev("getMenu()"); check('電子菜單：隱藏的品項不會出現', not any(i['name'] == '紅茶' for c in m2['cats'] for i in c['items']))
        await ev("setHidden('drink|紅茶', false, 'hl7q2x9m')")
        fr = await open_({})
        await fr.wait_for_function('window.__hlEnd === true')
        check('電子菜單：顧客首頁有「看菜單」', await fr.locator('#tiles >> text=看菜單').count() == 1)
        await fr.click('#tiles >> text=看菜單')
        await fr.wait_for_selector('#v-menu.on .mc')
        n_all = await fr.locator('#menuBody .mi').count()
        check('電子菜單：顯示所有品項與價格（含多規格價格）', n_all > 100 and '25' in await fr.inner_text('#menuBody'), n_all)
        check('電子菜單：有標示的品項旁邊顯示標籤', await fr.locator('#menuBody .tg').count() >= 6)
        check('電子菜單：有「素食」「不辣」篩選與過敏原按鈕（只列有用到的）', await fr.locator('#mfDiet [data-d="veg"]').count() == 1 and await fr.locator('#mfDiet [data-d="nospicy"]').count() == 1 and await fr.locator('#mfAlg [data-a="egg"]').count() == 1 and await fr.locator('#mfAlg [data-a="sesame"]').count() == 0)
        await fr.click('#mfDiet [data-d="veg"]')
        names = await fr.evaluate("[...document.querySelectorAll('#menuBody .mi .nm')].map(x => x.textContent)")
        check('電子菜單：篩「素食」只剩標示素／純素的品項（薯餅、熱狗、堅果沙拉）', len(names) == 3 and all(any(k in n for k in ['薯餅', '熱狗', '堅果沙拉']) for n in names), names)
        await fr.click('#mfDiet [data-d="vegan"]')
        names = await fr.evaluate("[...document.querySelectorAll('#menuBody .mi .nm')].map(x => x.textContent)")
        check('電子菜單：篩「純素」只剩純素（薯餅）', len(names) == 1 and '薯餅' in names[0], names)
        await fr.click('#mfDiet [data-d=""]'); await fr.click('#mfDiet [data-d="nospicy"]')
        check('電子菜單：「不辣」排除有辣標示的品項（美式不見了，其他還在）', await fr.locator('#menuBody .mi .tg:text("辣")').count() == 0 and await fr.locator('#menuBody .mi').count() == n_all - 1, (await fr.locator('#menuBody .mi').count(), n_all))
        await fr.click('#mfDiet [data-d=""]')
        await fr.click('#mfAlg [data-a="egg"]')
        left = await fr.locator('#menuBody .mi').count()
        has_egg = await fr.evaluate("[...document.querySelectorAll('#menuBody .mi')].some(x => /蛋/.test(x.querySelector('.tg') ? [...x.querySelectorAll('.tg')].map(t => t.textContent).join('') : ''))")
        check('電子菜單：避開「蛋」：有蛋標示的品項消失，其他還在', left < n_all and not has_egg and left > 100, (left, n_all))
        await fr.click('#mfAlg [data-a="milk"]'); await fr.click('#mfAlg [data-a="gluten"]'); await fr.click('#mfAlg [data-a="shellfish"]')
        check('電子菜單：可以同時避開多種過敏原', await fr.locator('#menuBody .mi').count() < left)
        await fr.click('#mfDiet [data-d="veg"]'); await fr.click('#mfAlg [data-a="nut"]')
        names = await fr.evaluate("[...document.querySelectorAll('#menuBody .mi .nm')].map(x => x.textContent)")
        check('電子菜單：「素食」加「避開堅果、蛋…」同時生效（只剩薯餅）', len(names) == 1 and '薯餅' in names[0], names)
        await fr.click('#mfAlg [data-a="nut"]')
        fr = await open_({'p': 'menu'})
        await fr.wait_for_selector('#v-menu.on .mc')
        check('電子菜單：網址 ?p=menu 直接打開菜單頁', await fr.locator('#menuBody .mi').count() > 100)

        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
