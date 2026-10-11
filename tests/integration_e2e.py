"""整合測試：真的 Code.gs ＋ Tools.gs，經由 doGet 產生三個頁面（菜單工具、店家工具、顧客頁）
在 iframe 裡執行（跟 Apps Script 一樣），google.script.run 接到同一份模擬試算表。
執行：python3 tests/integration_e2e.py
"""
import re, asyncio, base64, json, os, subprocess, sys, tempfile, datetime
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
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:400]))

TW = datetime.timezone(datetime.timedelta(hours=8))
today = datetime.datetime.now(TW).date()
D = lambda n: (today + datetime.timedelta(days=n)).isoformat()
# 下一個「至少 3 天後」的星期五，休三天（五六日本來都有營業）
fri = next(today + datetime.timedelta(days=n) for n in range(3, 10) if (today + datetime.timedelta(days=n)).weekday() == 4)
CL_S, CL_E = fri.isoformat(), (fri + datetime.timedelta(days=2)).isoformat()
wed = next(fri + datetime.timedelta(days=n) for n in range(1, 8) if (fri + datetime.timedelta(days=n)).weekday() == 2)
SP = wed.isoformat()                                     # 公休的星期三，設定特別營業
wed2 = (wed + datetime.timedelta(days=7)).isoformat()    # 下一個星期三：照常公休
mon_after = next(fri + datetime.timedelta(days=n) for n in range(3, 8) if (fri + datetime.timedelta(days=n)).weekday() == 0).isoformat()

def files_json():
    f = {n: open(os.path.join(SRC, n + '.html'), encoding='utf-8').read() for n in ['Page', 'Customer', 'Tools', 'Login', 'Admin', 'Account']}
    return json.dumps(f).replace('</', '<\\/')

SEED = """
(function () {
  __store.props.ssId = 'test';
  var ss = __ss, p = ss.insertSheet('價格表');
  p.data = [['弘林'], [''], [''], [''], ['代碼']];
  ITEMS.forEach(function (it) { p.data.push([it[0], it[1], it[2], it[3], it[4], it[4], false, !!it[5], '']); });
  var pre = custSheet_('pre');
  pre.appendRow(['R1', new Date(), '%(tm)s', '08:00', '王先生', '0912', '紅茶 × 10', 10, 250, '', '待確認', '']);
  pre.appendRow(['R2', new Date(), '%(tm)s', '07:30', '陳小姐', '0922', '蛋餅 × 5', 5, 150, '', '已確認', '']);
  pre.appendRow(['R3', new Date(), '%(tm)s', '09:00', '取消的人', '0933', '奶茶 × 1', 1, 25, '', '取消', '']);
  pre.appendRow(['R4', new Date(), '%(nw)s', '10:00', '林先生', '0944', '總匯 × 3', 3, 270, '', '待確認', '']);
  var h = custSheet_('help');
  h.appendRow(['H1', new Date(), 'Uber Eats', 'A1', '%(td)s', '少送', '', '', '', '0911', '', '待處理', '', '']);
  h.appendRow(['H2', new Date(), 'Uber Eats', 'A2', '%(td)s', '少送', '', '', '', '0911', '', '已完成', '', '']);
  custSheet_('knock').appendRow(['K1', new Date(), '老闆', '加油', '要', '0900', '待處理', '']);
})();
""" % {'tm': D(1), 'nw': D(7), 'td': D(0)}

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
</script></head><body style="margin:0"><iframe id="f" style="width:420px;height:900px;border:0"></iframe></body></html>"""

def decode_pdf(b64, keep):
    pdf = os.path.join(TMP, keep)
    open(pdf, 'wb').write(base64.b64decode(b64))
    for f in os.listdir(TMP):
        if f.startswith('ipg-'): os.remove(os.path.join(TMP, f))
    pdf_to_pngs(pdf, os.path.join(TMP, 'ipg'))
    found, n = [], 0
    for f in sorted(os.listdir(TMP)):
        if f.startswith('ipg-'):
            n += 1; found += [r.text for r in zxingcpp.read_barcodes(Image.open(os.path.join(TMP, f)))]
    return found, n

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 420, 'height': 900})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        if os.environ.get('DEBUG'): page.on('pageerror', lambda e: print('PAGEERR', str(e)[:300]))
        if os.environ.get('DEBUG'): page.on('console', lambda m: print('CONSOLE', m.text[:300]))
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
        check('Code.gs＋Tools.gs 載入無錯誤', not errors, errors)
        H = page.main_frame
        async def open_(params):
            await H.evaluate('p => openPage(p)', params)
            return H.child_frames[0]

        # ---------- doGet 分流 ----------
        html = await H.evaluate("doGet({parameter:{p:'tools', staff:'hl7q2x9m'}}).getContent()")
        check('?p=tools&staff=鑰匙 → 店家工具', '<h1>店家工具</h1>' in html)
        html = await H.evaluate("doGet({parameter:{p:'tools'}}).getContent()")
        check('沒有鑰匙 → 顧客頁（不會進店家工具）', '<h1>店家工具</h1>' not in html and '顧客服務中心' in html)
        html = await H.evaluate("doGet({parameter:{p:'tools', staff:'wrong'}}).getContent()")
        check('鑰匙錯誤 → 顧客頁', '<h1>店家工具</h1>' not in html)
        html = await H.evaluate("doGet({parameter:{staff:'hl7q2x9m'}}).getContent()")
        check('?staff=鑰匙 → 菜單工具', '菜單工具' in html and 'const STAFF_KEY' in html)
        st = await H.evaluate('selfTest()')
        check('selfTest 全部通過（含店家工具頁面）', '❌' not in st and '店家工具頁面：正常' in st, st)

        # ---------- 菜單工具 ----------
        fr = await open_({'staff': 'hl7q2x9m'})
        await fr.wait_for_function('window.__hlEnd === true && document.querySelector("#stat b")')
        check('菜單工具載入', '已連線' in await fr.inner_text('#stat'))
        href = await fr.get_attribute('#toolsLink', 'href')
        check('菜單工具有「店家工具」連結（網址完整，沒被 // 砍掉）', href == (await H.evaluate('WEB_APP_URL')) + '?p=tools&staff=hl7q2x9m' and href.startswith('https://script.google.com/macros/s/'), href)
        inp = fr.locator('.f[data-k="drink|紅茶|0"] input')
        await inp.fill('28')
        await fr.wait_for_function('document.querySelector("#sync").className.includes("ok")', timeout=8000)
        await page.wait_for_timeout(300)
        sync = await fr.inner_text('#sync')
        val = await H.evaluate("__ss.sheets['價格表'].data.find(r => r[0] === 'drink|紅茶|0')[4]")
        log = await H.evaluate("(__ss.sheets['修改紀錄'] || {data: []}).data.length")
        retry = await H.evaluate("__calls.filter(c => c === 'setPrices').length")
        check('改價直接存好（修正 who 未定義：不再「沒存到，3 秒後重試」）', sync == '已同步' and val == 28 and retry == 1, (sync, val, retry))
        check('修改紀錄有寫入、updatedBy＝菜單工具', log >= 2 and await H.evaluate("__store.props.updatedBy") == '菜單工具')

        # ---------- 店家工具：交接 ----------
        fr = await open_({'p': 'tools', 'staff': 'hl7q2x9m'})
        await fr.wait_for_function('window.__hlEnd === true')
        check('店家工具預設打開「交接」', await fr.is_visible('#tab-hand') and not await fr.is_visible('#tab-logo'))
        sumtxt = await fr.inner_text('#sumCard')
        nums = await fr.evaluate("Array.from(document.querySelectorAll('#sumCard .k b')).map(b => +b.textContent)")
        check('今日摘要：今明預訂 2、待確認 2、異常 1、敲敲 1、交接 0', nums == [2, 2, 1, 1, 0], nums)
        check('摘要列出明天預訂（不含取消的）', '王先生' in sumtxt and '陳小姐' in sumtxt and '取消的人' not in sumtxt, sumtxt)
        check('摘要預訂時間正確（試算表時間格式）', '07:30' in sumtxt and '08:00' in sumtxt, sumtxt)
        check('選單連回菜單工具', (await fr.get_attribute('#menuLink', 'href') or '').endswith('?staff=hl7q2x9m'))
        await fr.fill('#h_who', '小美')
        await fr.click('#h_send'); await page.wait_for_timeout(200)
        check('沒寫內容會擋', '內容' in await fr.inner_text('#toast'))
        await fr.click('#h_types .chipb[data-t="叫貨補貨"]')
        await fr.fill('#h_text', '吐司明天要叫 3 條')
        await fr.check('#h_todo')
        await fr.click('#h_send'); await page.wait_for_timeout(500)
        hs = await H.evaluate("__ss.sheets['交接紀錄'].data.slice(1)")
        check('交接寫進「交接紀錄」分頁', len(hs) == 1 and hs[0][4] == '小美' and hs[0][5] == '叫貨補貨' and hs[0][8] == '待處理', hs)
        check('交接清單顯示待處理', '待處理' in await fr.inner_text('#h_list') and '吐司' in await fr.inner_text('#h_list'))
        check('摘要的交接待處理變 1', (await fr.evaluate("+document.querySelectorAll('#sumCard .k b')[4].textContent")) == 1)
        check('自己寫的不會出現「我看過了」', await fr.locator('#h_list [data-act=ack]').count() == 0)
        await fr.fill('#h_who', '阿明')
        await fr.click('#h_filter .chipb[data-f=unseen]')
        check('「我還沒看過」篩選', await fr.locator('#h_list li').count() == 1)
        await fr.click('#h_list [data-act=ack]'); await page.wait_for_timeout(400)
        check('按「我看過了」記下名字', await H.evaluate("__ss.sheets['交接紀錄'].data[1][11]") == '阿明')
        check('看過後「我還沒看過」清單變空', await fr.locator('#h_list [data-act]').count() == 0 or '沒有符合' in await fr.inner_text('#h_list'))
        await fr.click('#h_filter .chipb[data-f=all]')
        check('全部清單顯示「已看過：阿明」', '已看過：阿明' in await fr.inner_text('#h_list'))
        await fr.click('#h_list [data-act=done]'); await page.wait_for_timeout(400)
        row = await H.evaluate("__ss.sheets['交接紀錄'].data[1]")
        check('按「處理完成」記錄完成人', row[8] == '已完成' and row[9] == '阿明', row)
        check('回傳資料沒有 Date（google.script.run 不能傳 Date）', not errors, errors)
        await page.screenshot(path=os.path.join(TMP, 'shot_hand.png'))

        # ---------- 桌號 QR：清單是空的時候按「新增一桌」「加到清單」（手機回報的錯誤）----------
        await fr.click('.tabs button[data-tab=table]')
        await fr.click('#addRow'); await page.wait_for_timeout(100)
        check('空清單按「新增一桌」不會出錯', await fr.locator('#tbl tbody tr[data-i]').count() == 1 and not errors, errors)
        await fr.click('#clearRows'); await fr.click('#clearRows'); await page.wait_for_timeout(100)
        await fr.evaluate("document.querySelector('#tab-table details').open = true")
        await fr.fill('#bulk', 'https://iding.app/fbf433'); await fr.click('#bulkAdd'); await page.wait_for_timeout(100)
        check('空清單按「加到清單」不會出錯', await fr.locator('#tbl tbody tr[data-i]').count() == 1 and not errors, errors)
        await fr.fill('#tbl tbody tr[data-i] .nm', '第 1 桌'); await page.wait_for_timeout(100)
        check('在空清單新增後輸入不會出錯', not errors, errors)

        # ---------- 店家工具：店休行事曆 ----------
        await fr.click('.tabs button[data-tab=cal]')
        check('顯示每週固定公休', '週三、週四' in await fr.inner_text('#calWeekly'))
        await fr.fill('#c_s', CL_S); await fr.fill('#c_e', CL_E)
        await fr.fill('#c_reason', '老闆休假')
        await fr.click('#c_save'); await page.wait_for_timeout(500)
        cl = await H.evaluate('tListClosures_()')
        check('店休存進「店休行事曆」分頁', len(cl) == 1 and cl[0]['s'] == CL_S and cl[0]['e'] == CL_E and cl[0]['type'] == 'closed', cl)
        # 特別營業：公休的星期三
        await fr.click('#c_type .chipb[data-t=open]')
        await fr.fill('#c_s', SP); await fr.dispatch_event('#c_s', 'change')
        check('特別營業選公休日不會出現警告', await fr.inner_text('#c_warn') == '')
        await fr.fill('#c_s', mon_after); await fr.dispatch_event('#c_s', 'change')
        check('特別營業選本來有營業的日子會提醒', '本來就有營業' in await fr.inner_text('#c_warn'))
        await fr.fill('#c_s', CL_S); await fr.dispatch_event('#c_s', 'change')
        check('日期重疊會提醒', '重疊' in await fr.inner_text('#c_warn'))
        await fr.fill('#c_s', SP); await fr.fill('#c_reason', '特別加開'); await fr.dispatch_event('#c_s', 'change')
        await fr.click('#c_save'); await page.wait_for_timeout(500)
        info = await H.evaluate("[tClosedInfo_('%s'), tClosedInfo_('%s'), tClosedInfo_('%s'), tClosedInfo_('%s')]" % (CL_S, SP, wed2, mon_after))
        check('伺服器判斷：店休日不營業', info[0]['closed'] and info[0]['reason'] == '老闆休假', info[0])
        check('伺服器判斷：特別營業的星期三有營業', not info[1]['closed'], info[1])
        check('伺服器判斷：一般星期三照常公休', info[2]['closed'] and info[2]['reason'] == '每週公休', info[2])
        check('伺服器判斷：一般星期一營業', not info[3]['closed'], info[3])
        await fr.evaluate("(d) => { calMonth = new Date(+d.slice(0,4), +d.slice(5,7)-1, 1); renderCal(); }", CL_S)
        cls = await fr.evaluate("(d) => document.querySelector('#calGrid [data-d=\"' + d + '\"]').className", CL_S)
        check('月曆上店休日標紅', 'closed' in cls, cls)
        await fr.evaluate("(d) => { calMonth = new Date(+d.slice(0,4), +d.slice(5,7)-1, 1); renderCal(); }", SP)
        cls = await fr.evaluate("(d) => document.querySelector('#calGrid [data-d=\"' + d + '\"]').className", SP)
        check('月曆上特別營業標綠', 'special' in cls, cls)
        await fr.evaluate("(d) => { calMonth = new Date(+d.slice(0,4), +d.slice(5,7)-1, 1); renderCal(); }", CL_S)
        await fr.evaluate("() => document.querySelector('#calGrid').scrollIntoView()")
        await page.screenshot(path=os.path.join(TMP, 'shot_cal.png'))
        # 營業日曆海報
        mon = CL_S[:7]
        await fr.select_option('#mp_month', mon)
        await fr.evaluate("() => { window.__pdf = null; var o = savePdfFlow; savePdfFlow = function (doc) { window.__pdf = doc.output('datauristring').split(',')[1]; return o.apply(null, arguments); }; return 1; }")
        await fr.click('#mp_pdf')
        await fr.wait_for_function('window.__pdf && document.querySelector("#mpOut .result")', timeout=60000)
        found, n = decode_pdf(await fr.evaluate('window.__pdf'), 'month_poster.pdf')
        check('營業日曆海報 1 頁、LINE QR 掃得到', n == 1 and found == ['https://lin.ee/VpY3C6z'], (n, found))
        ptxt = await fr.evaluate("(ym) => { var d = document.createElement('div'); d.innerHTML = monthHtml(ym); return d.textContent; }", mon)
        check('海報標出店休原因與公休', '老闆休假' in ptxt and '公休' in ptxt, ptxt[:200])
        # 做成公告
        await fr.click('#c_list [data-mk]'); await page.wait_for_timeout(300)
        check('「做成公告」切到公告頁並套休假範本', await fr.is_visible('#tab-notice') and await fr.input_value('#n_cat') == 'vacation')
        big, infoTxt = await fr.input_value('#n_hiBig'), await fr.input_value('#n_info')
        back = datetime.date.fromisoformat(CL_E) + datetime.timedelta(days=1)
        check('恢復營業日自動算（店休隔天）', big == f'{back.year} 年 {back.month} 月 {back.day} 日', big)
        check('休假期間與最後營業日自動帶入', f'{fri.month}/{fri.day}' in infoTxt and '最後營業日' in infoTxt, infoTxt)
        check('公告顧客頁顯示期間＝店休前 7 天到最後一天', await fr.is_checked('#n_show') and await fr.input_value('#n_end2') == CL_E)
        exp_start = max(D(0), (datetime.date.fromisoformat(CL_S) - datetime.timedelta(days=7)).isoformat())
        check('公告開始顯示日＝店休前 7 天（不早於今天）', await fr.input_value('#n_start') == exp_start, await fr.input_value('#n_start'))
        await fr.fill('#n_start', D(0))   # 測試要馬上在顧客頁看到，改成今天
        await fr.click('#nSave'); await page.wait_for_timeout(400)
        # 摘要的近兩週店休
        await fr.click('.tabs button[data-tab=hand]'); await page.wait_for_timeout(500)
        check('交接摘要列出近兩週店休', '老闆休假' in await fr.inner_text('#sumCard'))

        # ---------- 顧客頁 ----------
        fr = await open_({})
        await fr.wait_for_function('window.__hlEnd === true')
        al = await fr.inner_text('#alerts')
        check('顧客首頁顯示店休', '暫停營業' in al and '老闆休假' in al, al)
        check('顧客首頁顯示特別營業', '特別加開' in al, al)
        check('顧客首頁顯示公告', '休假公告' in al, al)
        await page.screenshot(path=os.path.join(TMP, 'shot_cust.png'))
        await fr.click('[data-go=pre]')
        await fr.fill('#p-date', CL_S); await fr.dispatch_event('#p-date', 'change')
        hint = await fr.inner_text('#p-date-hint')
        check('預訂選店休日：提示店休原因', '老闆休假' in hint, hint)
        await fr.fill('#p-date', SP); await fr.dispatch_event('#p-date', 'change')
        check('預訂選特別營業的星期三：可以訂', '取餐' in await fr.inner_text('#p-date-hint'))
        await fr.fill('#p-date', wed2); await fr.dispatch_event('#p-date', 'change')
        check('預訂選一般星期三：公休', '公休' in await fr.inner_text('#p-date-hint'))
        first_open = await fr.input_value('#p-date')
        f = {'name': '測試', 'phone': '0900', 'time': '08:00', 'items': [{'k': 'drink|紅茶|0', 'q': 2}], 't0': 0}
        err = await H.evaluate("f => { try { submitPreorder(f); return 'ok'; } catch (e) { return e.message; } }", dict(f, date=CL_S))
        check('伺服器也擋店休日預訂', '老闆休假' in err, err)
        ok = await H.evaluate("f => { try { return submitPreorder(f).total; } catch (e) { return e.message; } }", dict(f, date=SP))
        check('伺服器允許特別營業日預訂（金額用新價格 28×2）', ok == 56, ok)
        err = await H.evaluate("f => { try { submitPreorder(f); return 'ok'; } catch (e) { return e.message; } }", dict(f, date=wed2))
        check('伺服器擋一般公休日', '公休' in err, err)

        # ---------- Logo：上傳後菜單與顧客頁都用新 Logo＋底色 ----------
        await H.evaluate("""() => {
          var c = document.createElement('canvas'); c.width = 1000; c.height = 1000; var g = c.getContext('2d');
          g.fillStyle = '#C81E28'; g.fillRect(0, 0, 1000, 1000); g.fillStyle = '#fff'; g.fillRect(300, 300, 400, 400);
          var big = c.toDataURL('image/jpeg', .9).split(',')[1];
          var s = document.createElement('canvas'); s.width = 300; s.height = 300; s.getContext('2d').drawImage(c, 0, 0, 300, 300);
          var web = s.toDataURL('image/jpeg', .8).split(',')[1];
          __store.cache.logo = 'old';
          tSaveLogo({ b64: big, webB64: web, origW: 1000, origH: 1000, origType: 'image/jpeg', origBytes: 1000, bgMode: 'solid', bg: '#C81E28' }, 'hl7q2x9m');
          return 1; }""")
        check('上傳 Logo 會清掉舊的 Logo 快取', await H.evaluate("__store.cache.logo === undefined"))
        uri = await H.evaluate('logoDataUri_()')
        check('菜單／顧客頁改用上傳的網頁小圖', uri.startswith('data:image/jpeg;base64,'), uri[:40])
        check('Logo 底色＝上傳時偵測的底色', await H.evaluate('logoBg_()') == '#C81E28')
        fr = await open_({'staff': 'hl7q2x9m'})
        await fr.wait_for_function('window.__hlEnd === true')
        sh = await fr.evaluate("sheetHTML('preview')")
        check('A3 菜單的 Logo 色塊用 Logo 底色', 'class="tile"' in sh and 'background:#C81E28' in sh)
        fr = await open_({})
        await fr.wait_for_function('window.__hlEnd === true')
        bg = await fr.evaluate("getComputedStyle(document.querySelector('img.logo')).backgroundColor")
        check('顧客頁 Logo 色塊用 Logo 底色', bg == 'rgb(200, 30, 40)', bg)

        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
