"""店家工具（Tools.gs + Tools.html）端對端測試
執行：python3 tests/tools_e2e.py
需要：playwright（chromium）、zxing-cpp、pillow、pdftoppm、tests/vendor 內的 html2canvas 與 jsPDF
"""
import asyncio, base64, io, os, re, subprocess, sys, tempfile, datetime
from PIL import Image, ImageDraw
import zxingcpp
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfutil import pdf_to_pngs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'tests')
SRC = os.path.join(ROOT, 'src')
VEND = {
    'html2canvas': os.path.join(T, 'vendor/html2canvas-1.4.1/dist/html2canvas.min.js'),
    'jspdf': os.path.join(T, 'vendor/jspdf-2.5.1/dist/jspdf.umd.min.js'),
}
results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)))

def gas_strip(html):
    """模擬 Apps Script：<script> 內 // 到行尾會被砍掉（除了整行註解，其實整行也砍，結果一樣）"""
    def fix(m):
        lines = []
        for ln in m.group(1).split('\n'):
            i = ln.find('//')
            lines.append(ln if i < 0 else ln[:i])
        return '<script>' + '\n'.join(lines) + '</script>'
    return re.sub(r'<script>(.*?)</script>', fix, html, flags=re.S)

def page_html():
    html = open(os.path.join(SRC, 'Tools.html'), encoding='utf-8').read()
    html = gas_strip(html)
    html = html.replace('<?!= boot ?>', 'window.__BOOT').replace('<?!= key ?>', '"test-key"')
    inject = ('<script src="/mock.js"></script><script src="/Tools.gs.js"></script>'
              '<script>window.__BOOTJSON = tJs_(tState_()); window.__BOOT = eval("(" + window.__BOOTJSON + ")");</script>')
    return html.replace('<head>', '<head>' + inject, 1)

def make_png(w, h, bg=None, fg=(27, 79, 138), mode='RGBA'):
    im = Image.new('RGBA', (w, h), bg + (255,) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([w * .2, h * .2, w * .8, h * .8], fill=fg + (255,))
    d.rectangle([w * .4, h * .1, w * .6, h * .9], fill=(232, 118, 42, 255))
    p = os.path.join(tempfile.gettempdir(), f'logo_{w}x{h}_{bool(bg)}.png')
    if mode == 'RGB':
        p = p.replace('.png', '.jpg'); im.convert('RGB').save(p, quality=92)
    else:
        im.save(p)
    return p

def decode_pdf(b64):
    pdf = os.path.join(tempfile.gettempdir(), 'out.pdf')
    open(pdf, 'wb').write(base64.b64decode(b64))
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith('pg-'): os.remove(os.path.join(tempfile.gettempdir(), f))
    pdf_to_pngs(pdf, os.path.join(tempfile.gettempdir(), 'pg'))
    found, npages = [], 0
    for f in sorted(os.listdir(tempfile.gettempdir())):
        if f.startswith('pg-'):
            npages += 1
            im = Image.open(os.path.join(tempfile.gettempdir(), f))
            found += [r.text for r in zxingcpp.read_barcodes(im)]
    return found, npages, pdf

TABLE_URLS = [('候位點餐', 'https://iding.app/e2fbc0')] + [
    (f'第 {i} 桌', 'https://iding.app/' + c) for i, c in enumerate(
        ['fbf433', 'b1d69e', 'ae7d4f', 'a605f6', '9ec511', 'c9172f', '80250f', '3c7aec', '6bad04'], 1)]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 420, 'height': 900}, device_scale_factor=1)
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        async def route(r):
            u = r.request.url
            if u.startswith('http://t/index'):
                return await r.fulfill(body=page_html(), content_type='text/html; charset=utf-8')
            if u.endswith('/mock.js'):
                return await r.fulfill(path=os.path.join(T, 'tools_mock.js'), content_type='text/javascript')
            if u.endswith('/Tools.gs.js'):
                return await r.fulfill(path=os.path.join(SRC, 'ToolsServer.gs'), content_type='text/javascript')
            for k, v in VEND.items():
                if k in u and 'cdnjs' in u:
                    return await r.fulfill(path=v, content_type='text/javascript')
            return await r.abort()
        await page.route('**/*', route)
        await page.goto('http://t/index')
        await page.wait_for_timeout(500)

        check('頁面載入完整（__hlEnd）', await page.evaluate('window.__hlEnd === true'))
        check('沒有 JS 錯誤', not errors, errors)
        check('boot JSON 跳脫 < 與 /', '</' not in await page.evaluate('__BOOTJSON') and '\\/' in await page.evaluate('__BOOTJSON'))
        check('預設店名', await page.input_value('#sName') == '弘林早午餐')
        check('預設敲敲老闆網址', (await page.input_value('#sKnock')).endswith('/exec?p=knock'))

        # ---------- Logo ----------
        await page.click('.tabs button[data-tab=logo]')
        await page.set_input_files('#logoFile', make_png(300, 300))
        await page.wait_for_timeout(400)
        txt = await page.inner_text('#logoChecks')
        check('低解析 300px 被退件', '無法上傳' in txt and '800' in txt, txt)
        check('退件時上傳鈕停用', await page.is_disabled('#logoSave'))

        await page.set_input_files('#logoFile', make_png(1800, 300))
        await page.wait_for_timeout(400)
        check('6:1 太細長被退件', '太細長' in await page.inner_text('#logoChecks'))

        await page.set_input_files('#logoFile', make_png(1000, 1000, bg=(200, 30, 40), mode='RGB'))
        await page.wait_for_timeout(500)
        txt = await page.inner_text('#logoChecks')
        check('1000px：可上傳但提醒 1500', '建議 1500' in txt and not await page.is_disabled('#logoSave'), txt)
        check('偵測到單色底（紅）', '有底色' in txt, txt)
        bg = await page.evaluate('logoBg()')
        r, g, bl = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
        check('底色接近 #C81E28', abs(r - 200) < 8 and abs(g - 30) < 8 and abs(bl - 40) < 8, bg)
        await page.click('#logoSave'); await page.wait_for_timeout(800)
        meta = await page.evaluate('S.logoMeta')
        check('Logo 存到伺服器且記錄底色', meta and meta['bgMode'] == 'solid' and meta['w'] == 1000 and meta['level'] == 'warn', meta)
        tile_bg = await page.evaluate("getComputedStyle(document.querySelector('#logoView .ltile')).backgroundColor")
        check('色塊底色＝Logo 底色', tile_bg == 'rgb(%d, %d, %d)' % (r, g, bl), tile_bg)

        await page.set_input_files('#logoFile', make_png(2600, 1300))
        await page.wait_for_timeout(500)
        txt = await page.inner_text('#logoChecks')
        check('去背 Logo：色塊白色', '去背' in txt and await page.evaluate('logoBg()') == '#FFFFFF', txt)
        await page.click('#logoSave'); await page.wait_for_timeout(1200)
        meta = await page.evaluate('S.logoMeta')
        check('大圖縮到長邊 2000、保留透明 PNG', meta['w'] == 2000 and meta['h'] == 1000 and meta['type'] == 'image/png' and meta['origW'] == 2600, meta)
        files = await page.evaluate('[Object.values(__store.files).filter(f=>!f.trashed&&f.blob.n.startsWith("logo_")&&!f.blob.n.startsWith("logo_web")).length, Object.values(__store.files).filter(f=>!f.trashed&&f.blob.n.startsWith("logo_web")).length]')
        check('舊 Logo 移到垃圾桶，只留一組（原圖＋網頁小圖）', files == [1, 1], files)
        webok = await page.evaluate('(() => { const m = JSON.parse(__store.props.t_logo); const f = __store.files[m.webId]; return !!f && f.blob.b.length <= 70000; })()')
        check('網頁小圖 70KB 以內', webok)

        # 繞過前端直接塞小圖 → 伺服器擋下
        small = base64.b64encode(open(make_png(200, 200), 'rb').read()).decode()
        err = await page.evaluate('''b => { try { tSaveLogo({b64:b, origW:200, origH:200, origType:'image/png', origBytes:1000}, 'test-key'); return 'no error'; } catch(e){ return e.message; } }''', small)
        check('伺服器端也擋低解析', '解析度不符合' in err, err)
        err = await page.evaluate('''b => { try { tSaveLogo({b64:b, origW:3000, origH:3000, origType:'image/png', origBytes:1000}, 'test-key'); return 'no error'; } catch(e){ return e.message; } }''', small)
        check('謊報原圖尺寸被擋', '不一致' in err, err)
        err = await page.evaluate('''() => { try { tSaveShop({name:'x'}, 'wrong'); return 'no error'; } catch(e){ return e.message; } }''')
        check('錯誤鑰匙不能寫入', '權限' in err, err)

        # 手動底色
        await page.select_option('#bgMode', 'manual')
        await page.evaluate("document.getElementById('bgPick').value='#112233'")
        await page.click('#bgSave'); await page.wait_for_timeout(300)
        check('手動底色儲存', (await page.evaluate('S.logoMeta.bgManual')) == '#112233')
        await page.select_option('#bgMode', 'auto')
        await page.click('#bgSave'); await page.wait_for_timeout(300)

        # 店家資料：錯誤網址
        await page.fill('#sLine', 'lin.ee/abc')
        await page.click('#shopSave'); await page.wait_for_timeout(300)
        check('店家資料：網址格式錯誤會提示', 'https' in await page.inner_text('#toast'))
        await page.fill('#sLine', 'https://lin.ee/VpY3C6z')
        await page.click('#shopSave'); await page.wait_for_timeout(300)
        check('店家資料儲存', 'lin.ee' in (await page.evaluate('S.shop.lineUrl')))

        # ---------- 桌號 QR ----------
        await page.click('.tabs button[data-tab=table]')
        await page.evaluate("document.querySelector('details').open = true")
        bulk = '\n'.join(f'{n}, {u}' for n, u in TABLE_URLS)
        await page.fill('#bulk', bulk)
        await page.click('#bulkReplace'); await page.wait_for_timeout(200)
        rows = await page.evaluate('readRows()')
        check('批次貼上 10 筆', len(rows) == 10, len(rows))
        check('候位自動判斷類型', rows[0]['type'] == 'wait' and rows[1]['type'] == 'table', rows[:2])
        # 只有網址 → 自動編號
        await page.fill('#bulk', 'https://iding.app/zz9911')
        await page.click('#bulkAdd'); await page.wait_for_timeout(200)
        rows = await page.evaluate('readRows()')
        check('只貼網址自動命名第 10 桌', rows[-1]['name'] == '第 10 桌', rows[-1])
        # 重複網址 → 擋下
        await page.fill('#bulk', '第 11 桌 https://iding.app/fbf433')
        await page.click('#bulkAdd'); await page.wait_for_timeout(200)
        st = await page.inner_text('#tbl tbody tr:last-child .st')
        check('重複網址顯示錯誤', '重複' in st, st)
        await page.click('#tPdf'); await page.wait_for_timeout(300)
        check('有錯時不產生 PDF', '修正' in await page.inner_text('#toast'))
        await page.click('#tbl tbody tr:last-child .x')
        await page.click('#tbl tbody tr:last-child .x')
        await page.wait_for_timeout(100)

        for layout, per in [('a5x2', 2), ('a6x4', 4), ('a4', 1)]:
            await page.select_option('#layout', layout)
            await page.evaluate('() => { window.__pdf = null; if (!window.__origFlow) { window.__origFlow = savePdfFlow; savePdfFlow = function(doc){ window.__pdf = doc.output("datauristring").split(",")[1]; return window.__origFlow.apply(null, arguments); }; } return 1; }')
            await page.click('#tPdf')
            await page.wait_for_function('window.__pdf && document.querySelector("#tOut .result")', timeout=120000)
            b64 = await page.evaluate('window.__pdf')
            found, npages, pdf = decode_pdf(b64)
            want = sorted(u for _, u in TABLE_URLS)
            check(f'{layout}：{npages} 頁', npages == -(-10 // per), npages)
            check(f'{layout}：10 個 QR 全部掃得到且網址正確', sorted(found) == want, (sorted(found), want))
            if layout == 'a5x2':
                import shutil; shutil.copy(pdf, os.path.join(tempfile.gettempdir(), 'table_a5x2.pdf'))
        check('桌號清單已存到伺服器', len(await page.evaluate('JSON.parse(__store.props.t_tables)')) == 10)
        check('PDF 存到雲端並設為知道連結可看', await page.evaluate('Object.values(__store.files).filter(f=>f.blob.t==="application/pdf"&&f.shared).length') == 3)
        await page.fill('#tOut .em', 'boss@example.com'); await page.click('#tOut .sendm'); await page.wait_for_timeout(300)
        check('PDF 可寄 Email', await page.evaluate('__store.mails.length') == 1)

        # ---------- 公告 ----------
        await page.click('.tabs button[data-tab=notice]')
        await page.select_option('#n_cat', 'vacation'); await page.wait_for_timeout(200)
        check('休假範本帶入敲敲老闆網址', (await page.input_value('#n_q1Url')).endswith('?p=knock'))
        today = datetime.date.today()
        await page.check('#n_show')
        await page.fill('#n_start', (today - datetime.timedelta(days=1)).isoformat())
        await page.fill('#n_end2', (today + datetime.timedelta(days=30)).isoformat())
        await page.evaluate('() => { window.__pdf = null; return 1; }')
        await page.click('#nPdf')
        await page.wait_for_function('window.__pdf && document.querySelector("#nOut .result")', timeout=60000)
        found, npages, pdf = decode_pdf(await page.evaluate('window.__pdf'))
        import shutil; shutil.copy(pdf, os.path.join(tempfile.gettempdir(), 'notice.pdf'))
        check('公告 PDF 一頁', npages == 1, npages)
        check('公告兩個 QR 都掃得到', sorted(found) == sorted([await page.input_value('#n_q1Url'), 'https://lin.ee/VpY3C6z']), found)
        await page.wait_for_timeout(300)
        lst = await page.evaluate('S.notices')
        check('公告存進「公告」分頁並記 PDF 連結', len(lst) == 1 and lst[0]['pdf'].startswith('https') and lst[0]['id'].startswith('N'), lst)
        pub = await page.evaluate('tGetNotices()')
        check('顧客頁可讀到有效公告', len(pub) == 1 and pub[0]['big'] == '2027 年 2 月 23 日', pub)
        check('顧客端資料不含 PDF／內部欄位', 'pdf' not in pub[0] and 'content' not in pub[0])
        # 內容很多 → 自動縮字仍一頁
        await page.fill('#n_det', '\n'.join(f'第 {i} 點說明文字比較長一點點' for i in range(14)))
        await page.fill('#n_detTitle', '注意事項')
        await page.click('#nPrev'); await page.wait_for_timeout(300)
        sc = await page.evaluate("parseFloat(document.querySelector('#nPv .nt').style.fontSize)")
        check('內容過多時自動縮小字級', sc < 16, sc)
        # 編輯同一則不會新增
        await page.click('#nSave'); await page.wait_for_timeout(400)
        check('同一則公告更新不重複新增', len(await page.evaluate('S.notices')) == 1)
        # 過期公告不顯示
        await page.click('#nNew')
        await page.check('#n_show'); await page.fill('#n_start', '2020-01-01'); await page.fill('#n_end2', '2020-01-02')
        await page.click('#nSave'); await page.wait_for_timeout(400)
        check('過期公告不出現在顧客頁', len(await page.evaluate('tGetNotices()')) == 1)
        # 錯誤網址
        await page.fill('#n_q2Url', 'line.me'); await page.click('#nSave'); await page.wait_for_timeout(300)
        check('公告 QR 網址錯誤擋下', '小 QR' in await page.inner_text('#toast'))
        # 刪除需按兩次
        await page.click('#nList [data-del="0"]'); await page.wait_for_timeout(100)
        check('刪除需再按一次確認', len(await page.evaluate('S.notices')) == 2)
        await page.click('#nList [data-del="0"]'); await page.wait_for_timeout(300)
        check('刪除公告', len(await page.evaluate('S.notices')) == 1)

        # ---------- 公告類別 ----------
        cats = await page.evaluate('S.cats.map(c=>c.key)')
        check('公告類別 8 種（已移除價格調整）', len(cats) == 8 and 'price' not in cats and 'promo' in cats, cats)
        await page.click('#nNew')
        await page.select_option('#n_cat', 'newitem'); await page.wait_for_timeout(200)
        check('選「新品上市」帶入範本', '新品上市' in await page.input_value('#n_tag') and '升級套餐' in await page.input_value('#n_det'))
        pill = await page.evaluate("getComputedStyle(document.querySelector('#nPv .tagp')).backgroundColor")
        check('標籤顏色依類別（新品上市＝橘色）', pill == 'rgb(232, 118, 42)', pill)
        await page.check('#n_show'); await page.fill('#n_start', ''); await page.fill('#n_end2', '')
        await page.click('#nSave'); await page.wait_for_timeout(400)
        rowcat = await page.evaluate("__ss.sheets['公告'].data.slice(1).map(r=>r[9])")
        check('試算表「類別」欄寫入中文名稱', '新品上市' in rowcat and __import__('json').dumps(rowcat) and rowcat.count('') == 0, rowcat)
        # 編輯中改類別：內容保留
        before = await page.input_value('#n_det')
        await page.select_option('#n_cat', 'promo'); await page.wait_for_timeout(200)
        check('編輯中改類別不覆蓋內容', await page.input_value('#n_det') == before)
        await page.select_option('#n_cat', 'newitem')
        # 新增一則臨時公休 → 顧客頁排序在最前
        await page.click('#nNew'); await page.select_option('#n_cat', 'closed')
        await page.check('#n_show'); await page.click('#nSave'); await page.wait_for_timeout(400)
        pub = await page.evaluate('tGetNotices()')
        check('顧客頁依重要性排序（公休在前）', [x['cat'] for x in pub][:1] == ['closed'] and {'newitem', 'vacation'} <= {x['cat'] for x in pub}, [x['cat'] for x in pub])
        check('顧客頁資料含類別名稱與顏色', pub[0]['catName'] == '臨時公休' and pub[0]['color'].startswith('#'))
        await page.select_option('#nFilter', 'newitem'); await page.wait_for_timeout(100)
        n = await page.evaluate("document.querySelectorAll('#nList li').length")
        check('清單可依類別篩選', n == 1, n)
        opt = await page.evaluate("document.querySelector('#nFilter option[value=newitem]').textContent")
        check('篩選選單顯示數量', '（1）' in opt, opt)
        for rk, pw, ph in [('sq', 1000, 1000), ('story', 720, 1280), ('a4', 794, 1123)]:
            await page.select_option('#n_ratio', rk); await page.wait_for_timeout(250)
            dm = await page.evaluate("() => { var pg = document.querySelector('#nPv .pg'); var nt = document.querySelector('#nPv .nt'); return [pg.offsetWidth, pg.offsetHeight, nt.scrollHeight]; }")
            check(f'公告比例「{rk}」：預覽尺寸 {pw}×{ph}，內容不超出頁面', dm[0] == pw and dm[1] == ph and dm[2] <= ph + 1, dm)
        check('公告比例會存進公告內容', (await page.evaluate("readNotice().ratio")) == 'a4')
        check('公告有「下載圖片（PNG）」按鈕', await page.locator('#nPng').count() == 1)
        # 舊資料沒有類別 → 一般公告
        await page.evaluate("__ss.sheets['公告'].data.push(['N99','','','舊公告','','',false,'{}','',''])")
        lst = await page.evaluate('tGetState("test-key").notices')
        check('舊資料無類別時歸為一般公告', lst[0]['cat'] == 'general', lst[0])

        # ---------- 節慶 ----------
        fd = await page.evaluate('''() => { var f = new Date(2026, 9, 2); return ['father','qixi','mother','cny','midautumn','xmas'].map(k => ymd(festDate(festOf(k), f))); }''')
        check('節日日期（父親節/七夕/母親節/春節/中秋/聖誕）', fd == ['2027-08-08', '2027-08-08', '2027-05-09', '2027-02-06', '2027-09-15', '2026-12-25'], fd)
        await page.click('#nNew')
        await page.select_option('#n_cat', 'festival'); await page.wait_for_timeout(150)
        check('節慶類別出現節日選單', await page.is_visible('#n_sub'))
        await page.select_option('#n_sub', 'father'); await page.wait_for_timeout(200)
        t = await page.input_value('#n_title'); hl_ = await page.input_value('#n_hiLabel')
        check('父親節範本：給天下爸爸', '爸爸' in t and await page.input_value('#n_tag') == '父親節快樂', t)
        check('父親節日期自動帶入（下一次 8/8）', '8 月 8 日（日）' in hl_, hl_)
        check('顧客頁顯示期間＝節前 7 天到當天', await page.input_value('#n_start') == '2027-08-01' and await page.input_value('#n_end2') == '2027-08-08')
        pill = await page.evaluate("getComputedStyle(document.querySelector('#nPv .tagp')).backgroundColor")
        check('節慶標籤顏色', pill == 'rgb(0, 137, 123)', pill)
        await page.evaluate('() => { window.__pdf = null; return 1; }')
        await page.click('#nPdf')
        await page.wait_for_function('window.__pdf && document.querySelector("#nOut .result")', timeout=60000)
        found, npages, pdf = decode_pdf(await page.evaluate('window.__pdf'))
        import shutil; shutil.copy(pdf, os.path.join(tempfile.gettempdir(), 'father.pdf'))
        check('父親節海報 PDF 一頁、QR 可掃', npages == 1 and len(found) == 2, (npages, found))
        nf = await page.evaluate("document.querySelectorAll('#upcoming .fest').length")
        exp = await page.evaluate("FESTS.filter(f => { var d = festDate(f); return d && (d - today0()) / 86400000 <= 45; }).length")
        check('近期節日快捷鈕', nf == exp, (nf, exp))
        if nf:
            await page.click('#upcoming .fest'); await page.wait_for_timeout(200)
            check('點快捷鈕直接套節慶範本', await page.input_value('#n_cat') == 'festival')
        # ---------- 活動 ----------
        await page.click('#nNew')
        await page.select_option('#n_cat', 'promo'); await page.wait_for_timeout(150)
        opts = await page.evaluate("Array.from(document.querySelectorAll('#n_sub option')).map(o=>o.textContent)")
        check('活動類型 7 種', len(opts) == 7 and '第二件半價' in opts, opts)
        await page.select_option('#n_sub', 'review'); await page.wait_for_timeout(200)
        check('打卡評論範本', await page.input_value('#n_q1Title') == '掃碼留評論' and 'Google' in await page.input_value('#n_det'))
        check('活動期間自動帶入', '–' in await page.input_value('#n_hiBig') and await page.input_value('#n_end2') != '')
        await page.fill('#n_q1Url', 'https://g.page/r/abc123/review')
        await page.click('#nSave'); await page.wait_for_timeout(400)
        saved = await page.evaluate("S.notices.find(n => n.id === S.noticeId)")
        check('活動公告存檔含類別與子範本', saved['cat'] == 'promo' and saved['content']['sub'] == 'review', saved and saved['content'].get('sub'))
        await page.select_option('#nFilter', '')
        await page.click(f"#nList [data-ed='{await page.evaluate('S.notices.findIndex(n => n.id === S.noticeId)')}']"); await page.wait_for_timeout(200)
        check('編輯時還原子範本選單', await page.input_value('#n_sub') == 'review')
        check('停售類別已移除', 'soldout' not in await page.evaluate('S.cats.map(c=>c.key)'))

        # ---------- Wi-Fi ----------
        await page.click('.tabs button[data-tab=wifi]')
        await page.fill('#w_ssid', 'HongLin;Guest'); await page.fill('#w_pass', 'short')
        await page.click('#wPdf'); await page.wait_for_timeout(200)
        check('WPA 密碼太短會擋', '8～63' in await page.inner_text('#toast'))
        await page.fill('#w_pass', 'brunch:2026,"ok"\\x')
        await page.select_option('#w_layout', 'a6x4')
        await page.evaluate('() => { window.__pdf = null; return 1; }')
        await page.click('#wPdf')
        await page.wait_for_function('window.__pdf && document.querySelector("#wOut .result")', timeout=60000)
        found, npages, pdf = decode_pdf(await page.evaluate('window.__pdf'))
        import shutil; shutil.copy(pdf, os.path.join(tempfile.gettempdir(), 'wifi.pdf'))
        want = 'WIFI:T:WPA;S:HongLin\\;Guest;P:brunch\\:2026\\,\\"ok\\"\\\\x;H:false;;'
        check('Wi-Fi A6 四拼：4 張都掃得到', npages == 1 and len(found) == 4, (npages, len(found)))
        check('Wi-Fi QR 內容正確（特殊字元已跳脫）', set(found) == {want}, (found[:1], want))
        txt = await page.evaluate("document.querySelector('#wPv').innerText")
        check('卡片印出網路名稱與密碼', 'HongLin;Guest' in txt and 'brunch:2026' in txt, txt[:200])
        check('Wi-Fi 設定存到伺服器', await page.evaluate('JSON.parse(__store.props.t_wifi).ssid') == 'HongLin;Guest')
        await page.select_option('#w_enc', 'nopass'); await page.click('#wPrev'); await page.wait_for_timeout(200)
        q = await page.evaluate("wifiText(readWifi())")
        check('無密碼格式', q == 'WIFI:T:nopass;S:HongLin\\;Guest;H:false;;', q)
        err = await page.evaluate('''() => { try { tSaveWifi({ssid:'x', pass:'123', enc:'WPA'}, 'test-key'); return 'no'; } catch(e) { return e.message; } }''')
        check('伺服器端也驗證 Wi-Fi 密碼', '8～63' in err, err)

        # ---------- 名片 ----------
        await page.click('.tabs button[data-tab=card]'); await page.wait_for_timeout(400)
        check('名片：店名預設帶入店家資料', (await page.input_value('#c_name')) == await page.evaluate('S.shop.name'))
        check('名片：預設配色跟店家配色一致', (await page.input_value('#c_cp')).upper() == (await page.evaluate('S.shop.primary')).upper() and (await page.input_value('#c_ca')).upper() == (await page.evaluate('S.shop.accent')).upper())
        check('名片：4 種版型、9 種配色可選', await page.locator('#c_tpls [data-tpl]').count() == 4 and await page.locator('#c_pals [data-pal]').count() == 9)
        check('名片：預覽同時顯示正面與背面', await page.locator('#cPv .cpb').count() == 2)
        await page.click('#c_pals [data-pal=graph]'); await page.wait_for_timeout(200)
        check('名片：選配色範本會設定主色與強調色', (await page.input_value('#c_cp')).upper() == '#10161D' and (await page.input_value('#c_ca')).upper() == '#1AA3C0')
        await page.fill('#c_person', '王小明'); await page.fill('#c_jobtitle', '店長 | Manager'); await page.fill('#c_phone', '03-4588229')
        await page.fill('#c_addr', '桃園市中壢區廣州路11號'); await page.fill('#c_line', '@322kwvxu'); await page.fill('#c_email', 'hi@example.com'); await page.fill('#c_web', 'example.com')
        await page.fill('#c_pay', '現金、LINE Pay、全支付'); await page.wait_for_timeout(300)
        pv = await page.evaluate("document.querySelector('#cPv').innerText")
        check('名片：預覽即時帶出姓名、職稱、電話、地址、LINE 與付款方式（欄位多時 Email、網站優先讓位）', all(x in pv for x in ['王小明', '店長 | Manager', '03-4588229', '廣州路11號', '@322kwvxu', '全支付', '現金', '03-4588229']), pv[:300])
        for tp in ['top', 'bar', 'solid', 'side']:
            await page.click(f'#c_tpls [data-tpl={tp}]'); await page.wait_for_timeout(150)
            check(f'名片：版型「{tp}」正反面都能預覽', await page.locator('#cPv .cpb').count() == 2 and '王小明' in await page.evaluate("document.querySelector('#cPv').innerText"))
        await page.select_option('#c_qr', 'custom'); await page.fill('#c_url', 'not a url')
        await page.click('#cPdfPrint'); await page.wait_for_timeout(300)
        check('名片：自訂網址不正確會擋', '自訂網址不正確' in await page.inner_text('#toast'))
        await page.fill('#c_url', 'https://example.com/hello?x=1'); await page.fill('#c_cap', '掃碼逛逛'); await page.wait_for_timeout(300)
        await page.evaluate('() => { window.__pdf = null; return 1; }')
        await page.click('#cPdfPrint')
        await page.wait_for_function('window.__pdf && document.querySelector("#cOut .result")', timeout=120000)
        found, npages, pdf = decode_pdf(await page.evaluate('window.__pdf'))
        shutil.copy(pdf, os.path.join(tempfile.gettempdir(), 'card_print.pdf'))
        import fitz
        d = fitz.open(pdf); sz = (round(d[0].rect.width / 72 * 25.4, 1), round(d[0].rect.height / 72 * 25.4, 1))
        check('名片印刷廠版：兩頁（正面＋背面），尺寸 96×60 mm（含 3 mm 出血）', npages == 2 and sz == (96.0, 60.0), (npages, sz))
        check('名片印刷廠版：正面 QR 掃得到且網址正確（背面沒有 QR）', set(found) == {'https://example.com/hello?x=1'}, found)
        sv = await page.evaluate('JSON.parse(__store.props.t_card)')
        check('名片：設定存到伺服器（版型、配色、姓名、付款方式、雙面）', sv['person'] == '王小明' and sv['qr'] == 'custom' and sv['pal'] == 'graph' and sv['cp'] == '#10161D' and sv['tpl'] == 'side' and '全支付' in sv['payments'] and sv['sides'] == 'double' and sv['qrFront'] is True, sv)
        await page.fill('#c_sheets', '1'); await page.wait_for_timeout(200)
        await page.evaluate('() => { window.__pdf = null; document.querySelector("#cOut").innerHTML = ""; return 1; }')
        await page.click('#cPdfSheet')
        await page.wait_for_function('window.__pdf && document.querySelector("#cOut .result")', timeout=120000)
        found, npages, pdf = decode_pdf(await page.evaluate('window.__pdf'))
        shutil.copy(pdf, os.path.join(tempfile.gettempdir(), 'card_sheet.pdf'))
        d = fitz.open(pdf); sz = (round(d[0].rect.width / 72 * 25.4), round(d[0].rect.height / 72 * 25.4))
        check('名片 A4 版：兩頁 A4（正面＋背面）', npages == 2 and sz == (210, 297), (npages, sz))
        check('名片 A4 版：正面 QR 10 個（背面是 Logo，沒有 QR），內容都是設定的網址', len(found) == 10 and set(found) == {'https://example.com/hello?x=1'}, (len(found), set(found)))
        await page.select_option('#c_sides', 'front'); await page.evaluate('() => { window.__pdf = null; document.querySelector("#cOut").innerHTML = ""; return 1; }')
        await page.click('#cPdfPrint'); await page.wait_for_function('window.__pdf && document.querySelector("#cOut .result")', timeout=120000)
        found, npages, pdf = decode_pdf(await page.evaluate('window.__pdf'))
        check('名片：選「只印正面」只輸出一頁', npages == 1 and len(found) == 1, (npages, found))
        await page.select_option('#c_sides', 'double')
        bk = await page.evaluate("() => { var c = readCard(); return cardBack(c); }")
        check('名片背面：只有置中的 Logo 與店名，沒有 QR 圖', 'cbk' in bk and 'class="qb"' not in bk, bk[:200])
        await page.select_option('#c_qr', 'line'); await page.wait_for_timeout(300)
        check('名片：改連 LINE 後網址跟著變', await page.evaluate('cardUrlOf(readCard())') == await page.evaluate('S.shop.lineUrl'))
        err = await page.evaluate("""() => { try { tSaveCard({name:'x', qr:'custom', qrUrl:'javascript:1'}, 'test-key'); return 'no'; } catch(e) { return e.message; } }""")
        check('名片：伺服器端也驗證自訂網址', '網址' in err, err)

        # ---------- LINE 圖文選單 ----------
        await page.evaluate("() => { BOOT.cardInfo = BOOT.cardInfo || {}; BOOT.cardInfo.phone = '03-4588229'; }")
        await page.click('.tabs button[data-tab=rich]'); await page.wait_for_timeout(900)
        dm = await page.evaluate("() => { var c = document.querySelector('#rmPv canvas'); return c ? [c.width, c.height] : document.querySelector('#rmPv').innerText; }")
        check('LINE 選單：預設 6 格大圖，尺寸 2500×1686', dm == [2500, 1686] and await page.locator('#rm_cells [data-rk=t]').count() == 6, dm)
        for n, want in [(4, 4), (2, 2)]:
            await page.click(f'#rm_n [data-n="{n}"]'); await page.wait_for_timeout(500)
            check(f'LINE 選單：{n} 格版型有 {want} 個格子', await page.locator('#rm_cells [data-rk=t]').count() == want)
        await page.click('#rm_n [data-n="4"]'); await page.click('#rm_sz [data-big="0"]'); await page.wait_for_timeout(500)
        dm = await page.evaluate("() => { var c = document.querySelector('#rmPv canvas'); return c ? [c.width, c.height] : null; }")
        check('LINE 選單：小圖尺寸 2500×843', dm == [2500, 843], dm)
        await page.click('#rm_sz [data-big="1"]'); await page.wait_for_timeout(400)
        size = await page.evaluate("() => new Promise(ok => { var c = document.querySelector('#rmPv canvas'); c.toBlob(b => ok(b.size), 'image/png'); })")
        check('LINE 選單：PNG 小於 1MB', 0 < size < 1024 * 1024, size)
        lk = await page.inner_text('#rmLinks')
        check('LINE 選單：連結清單列出每一格的範圍與網址（菜單連結帶店家編號或 p=menu）', '第 1 格' in lk and 'p=menu' in lk and '第 4 格' in lk, lk[:300])
        await page.fill('#rm_cells [data-rk=t][data-i="0"]', '看菜單'); await page.wait_for_timeout(500)
        check('LINE 選單：改標題後預覽與連結清單同步', '看菜單' in await page.inner_text('#rmLinks'))
        await page.select_option('#rm_cells [data-rk=l][data-i="0"]', 'custom'); await page.wait_for_timeout(400)
        await page.fill('#rm_cells [data-rk=u][data-i="0"]', 'javascript:1'); await page.click('#rmPng'); await page.wait_for_timeout(300)
        check('LINE 選單：自訂網址不正確會擋', '自訂網址不正確' in await page.inner_text('#toast'))
        check('按鈕文字處理完會還原', await page.inner_text('#nPdf') == '儲存並產生 PDF' and await page.inner_text('#tPdf') == '儲存並產生 PDF')
        await page.screenshot(path=os.path.join(tempfile.gettempdir(), 'tools_mobile.png'), full_page=False)
        check('全程沒有 JS 錯誤', not errors, errors)
        await b.close()

asyncio.run(main())
ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
