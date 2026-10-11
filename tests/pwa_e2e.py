"""App 外殼（pwa/，放 GitHub Pages）測試：安裝設定檔與圖示、店家代碼、三個入口組出的網址、
記住登入、頁面傳來的「開新頁／記住登入」訊息、離線時外殼仍能開。用假的 Apps Script 網址，不連 Google。
執行：python tests/pwa_e2e.py
"""
import asyncio, json, os, re, sys, mimetypes
from playwright.async_api import async_playwright
from PIL import Image
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PWA = os.path.join(ROOT, 'pwa')
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:400]))

HOST = 'http://localhost:8765'
EXEC = 'http://exec.test/exec'
STUB = """<!doctype html><meta charset=utf-8><title>stub</title><body>stub app
<script>window.addEventListener('message', function (e) { if (e.data && e.data.say) parent.postMessage(e.data.say, '*'); });
parent.postMessage({ stubLoaded: location.search }, '*');</script>"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 800})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        async def route(r):
            u = r.request.url
            if u.startswith(EXEC):
                return await r.fulfill(body=STUB, content_type='text/html; charset=utf-8')
            if u.startswith(HOST):
                path = u[len(HOST):].split('?')[0].lstrip('/')
                if path == '' or path.endswith('/'): path += 'index.html'
                if path == 'config.js':
                    return await r.fulfill(body="window.HL_CONFIG = { exec: '%s', product: 'test' };" % EXEC, content_type='text/javascript')
                fp = os.path.join(PWA, path.replace('/', os.sep))
                if os.path.isfile(fp):
                    ct = mimetypes.guess_type(fp)[0] or 'application/octet-stream'
                    if fp.endswith('.webmanifest'): ct = 'application/manifest+json'
                    return await r.fulfill(path=fp, content_type=ct)
                return await r.fulfill(status=404, body='nf')
            return await r.abort()
        await ctx.route('**/*', route)

        # ---------- 設定檔與圖示 ----------
        for k, name in [('clock', '員工打卡'), ('owner', '店主管理'), ('menu', '店家菜單')]:
            m = json.load(open(os.path.join(PWA, k, 'manifest.webmanifest'), encoding='utf-8'))
            icons = {i['sizes'] + i['purpose']: i for i in m['icons']}
            ok = m['name'] == name and m['display'] == 'standalone' and m['start_url'] == './' and m['scope'] == './' and set(icons) == {'192x192any', '512x512any', '512x512maskable'}
            for i in m['icons']:
                fp = os.path.normpath(os.path.join(PWA, k, i['src']))
                im = Image.open(fp); ok = ok and os.path.isfile(fp) and '%dx%d' % im.size == i['sizes']
            check(f'安裝設定檔：{name}（standalone、192／512／可遮罩圖示都存在且尺寸正確）', ok, m)
            html = open(os.path.join(PWA, k, 'index.html'), encoding='utf-8').read()
            check(f'{name}：有 apple-touch-icon、主題色、全螢幕設定', 'apple-touch-icon' in html and 'apple-mobile-web-app-capable' in html and 'theme-color' in html and 'manifest.webmanifest' in html)
        check('圖示不是純色塊（畫了圖案）', len(Image.open(os.path.join(PWA, 'icons', 'clock-512.png')).convert('RGB').getcolors(100000)) > 2)

        # ---------- 員工打卡：店家代碼 ----------
        await page.goto(HOST + '/clock/')
        await page.wait_for_selector('#setup:not(.hidden)', timeout=8000)
        check('員工打卡：沒有店家代碼時先問代碼', await page.is_visible('#setup') and await page.is_hidden('#app'))
        await page.fill('#sid', 'abc'); await page.click('#go')
        check('員工打卡：代碼格式不對會提示', '格式不對' in await page.inner_text('#sErr'))
        await page.fill('#sid', 's0007'); await page.click('#go')
        await page.wait_for_selector('#app:not(.hidden)', timeout=5000)
        src = await page.get_attribute('#app', 'src')
        check('員工打卡：輸入代碼後嵌入 Apps Script 打卡頁（?s=店家代碼&p=clock）', src == EXEC + '?s=S0007&p=clock', src)
        check('員工打卡：店家代碼記在手機', await page.evaluate("localStorage.getItem('hl-shop')") == 'S0007')
        await page.goto(HOST + '/clock/')
        await page.wait_for_selector('#app:not(.hidden)', timeout=5000)
        check('員工打卡：下次開啟不用再輸入代碼', await page.get_attribute('#app', 'src') == EXEC + '?s=S0007&p=clock')
        await page.goto(HOST + '/clock/?s=s0012'); await page.wait_for_selector('#app:not(.hidden)')
        check('員工打卡：網址帶 ?s= 時以網址為準（轉大寫）並覆蓋記住的代碼', await page.get_attribute('#app', 'src') == EXEC + '?s=S0012&p=clock' and await page.evaluate("localStorage.getItem('hl-shop')") == 'S0012')
        await page.goto(HOST + '/clock/?reset=1'); await page.wait_for_selector('#setup:not(.hidden)')
        check('員工打卡：?reset=1 可以清掉記住的店家', await page.is_visible('#setup'))

        # ---------- 店家菜單 ----------
        await page.goto(HOST + '/menu/?s=S0003'); await page.wait_for_selector('#app:not(.hidden)')
        check('店家菜單：嵌入顧客菜單頁（?s=店家代碼&p=menu）', await page.get_attribute('#app', 'src') == EXEC + '?s=S0003&p=menu')

        # ---------- 店主管理 ----------
        await page.evaluate("localStorage.clear()")
        await page.goto(HOST + '/owner/'); await page.wait_for_selector('#app:not(.hidden)')
        check('店主管理：沒有登入紀錄時開登入頁（?go=home，登入後直接進主畫面）', await page.get_attribute('#app', 'src') == EXEC + '?go=home', await page.get_attribute('#app', 'src'))
        # 假 App 傳訊息給外殼
        async def post(msg, origin='http://exec.test'):
            await page.evaluate("""([m]) => { var f = document.getElementById('app'); }""", [msg])
        # 從 iframe 內送訊息（來源是假 App 的網域）
        frame = [f for f in page.frames if f.url.startswith(EXEC)][0]
        await frame.evaluate("() => parent.postMessage({ hlToken: 'TOKEN-A' }, '*')")
        await page.wait_for_timeout(200)
        check('店主管理：登入後頁面傳來的通行證會記在外殼', await page.evaluate("localStorage.getItem('hl-token')") == 'TOKEN-A')
        await page.goto(HOST + '/owner/'); await page.wait_for_selector('#app:not(.hidden)')
        check('店主管理：下次開啟直接帶通行證進主畫面，不用再登入', await page.get_attribute('#app', 'src') == EXEC + '?p=home&t=TOKEN-A')
        frame = [f for f in page.frames if f.url.startswith(EXEC)][0]
        await frame.evaluate("() => parent.postMessage({ hlGo: 'http://exec.test/exec?p=staff&t=TOKEN-B' }, '*')")
        await page.wait_for_timeout(300)
        check('頁面裡的連結（target=_top）交給外殼，在同一個視窗開新頁，不跳出 App', await page.get_attribute('#app', 'src') == EXEC + '?p=staff&t=TOKEN-B' and await page.evaluate("location.pathname") == '/owner/')
        check('開新頁時順便更新記住的通行證', await page.evaluate("localStorage.getItem('hl-token')") == 'TOKEN-B')
        frame = [f for f in page.frames if f.url.startswith(EXEC)][0]
        await frame.evaluate("() => parent.postMessage({ hlGo: 'https://evil.example.com/steal?t=X' }, '*')")
        await page.wait_for_timeout(300)
        check('外殼只接受 Apps Script 網址的導向（陌生網址不會被開）', await page.get_attribute('#app', 'src') == EXEC + '?p=staff&t=TOKEN-B')
        await frame.evaluate("() => parent.postMessage({ hlToken: '' }, '*')"); await page.wait_for_timeout(200)
        check('登出時通行證從外殼清除', await page.evaluate("localStorage.getItem('hl-token')") in (None, ''))
        # 別的來源的訊息不理
        await page.evaluate("window.postMessage({ hlToken: 'FAKE' }, '*')"); await page.wait_for_timeout(200)
        check('不是 Apps Script 來源的訊息不理（防偽造）', await page.evaluate("localStorage.getItem('hl-token')") in (None, ''))

        # ---------- 首頁（入口與連結）----------
        await page.evaluate("localStorage.clear()")
        await page.goto(HOST + '/'); await page.fill('#sid', 's0005')
        hc, hm, ho = await page.get_attribute('#a-clock', 'href'), await page.get_attribute('#a-menu', 'href'), await page.get_attribute('#a-owner', 'href')
        check('首頁：三個入口，輸入店家代碼後打卡／菜單連結帶上代碼', hc == 'clock/?s=S0005' and hm == 'menu/?s=S0005' and ho == 'owner/', (hc, hm, ho))
        check('首頁：有 iPhone 與 Android 安裝教學', '加入主畫面' in await page.inner_text('body') and '安裝應用程式' in await page.inner_text('body'))
        await page.reload()
        check('首頁：店家代碼記在手機', await page.input_value('#sid') == 'S0005')
        await page.click('[data-copy=clock]'); await page.wait_for_timeout(300)
        check('首頁：複製員工打卡連結', 'clock/?s=S0005' in await page.inner_text('#msg'))
        await page.fill('#sid', 'xx'); await page.click('[data-copy=menu]')
        check('首頁：代碼不對時不給連結', '請先輸入正確' in await page.inner_text('#msg'))

        # ---------- 離線 ----------
        await page.goto(HOST + '/clock/?s=S0005'); await page.wait_for_selector('#app:not(.hidden)')
        await page.evaluate("navigator.serviceWorker.ready.then(() => 1)")
        await page.reload(); await page.wait_for_timeout(500)
        check('離線快取：Service Worker 已啟用', await page.evaluate("!!navigator.serviceWorker.controller"))
        await ctx.set_offline(True)
        await page.goto(HOST + '/clock/?s=S0005'); await page.wait_for_timeout(800)
        check('沒有網路時外殼仍能開啟（顯示外殼，不是瀏覽器錯誤頁）', await page.locator('#app').count() == 1 and await page.title() == '員工打卡')
        await ctx.set_offline(False)
        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
