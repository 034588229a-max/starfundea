"""把弘林圖示庫（assets/sfd-icons.js）嵌進各工具頁面。

為什麼要嵌進去：Apps Script 的 HTML 之間只能用 include 共用，而測試模擬器不支援；
直接把圖示庫放進每個頁面最穩。圖示庫改版時，換掉 assets/sfd-icons.js，再執行：
    python scripts/sync_icons.py
頁面裡用法：<button data-ic="calendar">…</button>，載入後自動在文字前面補上圖示。
也可以寫 <i data-icon="coffee" data-size="20"></i>（會自動換成圖示）。
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'assets', 'sfd-icons.js')
PAGES = ['Page', 'Tools', 'Staff', 'Clock', 'Login', 'Account', 'Brand', 'Admin', 'Setup', 'Customer', 'Ledger', 'Home']
CSS = '.ico{width:1.15em;height:1.15em;vertical-align:-.2em;margin-right:.4em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:0 0 auto}\n'
BEGIN, END = '/* HL-ICONS:BEGIN */', '/* HL-ICONS:END */'
POS_PAGES = ['Tools', 'Staff', 'Clock']
POS_CSS = '/* HL-POS */ .tabs{display:grid!important;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:10px;overflow:visible!important}.tabs button{display:flex!important;flex-direction:column;align-items:center;justify-content:center;gap:6px;min-height:78px;border-radius:20px!important;font-size:15px;font-weight:900;padding:10px 6px;white-space:normal;text-align:center;box-shadow:0 3px 0 rgba(0,0,0,.09)}.tabs button svg.hl-icon{width:28px;height:28px;margin:0}.btn{min-height:50px;border-radius:14px}\n'

lib = open(LIB, encoding='utf-8').read().replace('\r\n', '\n').strip()
assert '/' + '/' not in lib.replace('http:/' + '/', ''), '圖示庫不能含連續兩個斜線（Apps Script 會砍掉）'
APPLY = ("(function () {\n"
         "  Array.prototype.forEach.call(document.querySelectorAll('[data-ic]'), function (el) {\n"
         "    if (el.querySelector('svg.hl-icon')) return;\n"
         "    el.insertAdjacentHTML('afterbegin', hlIcon(el.getAttribute('data-ic'), { size: 18, stroke: 2, cls: 'ico' }));\n"
         "  });\n"
         "  hlIcon.render();\n"
         "})();\n"
         "/* App 外殼（GitHub Pages 的 PWA）：頁面被嵌在外殼裡時，target=_top 的連結改由外殼開，不會跳出外殼 */\n"
         "(function shellNav() {\n"
         "  var ao = location.ancestorOrigins, tp = ao && ao.length ? ao[ao.length - 1] : '';\n"
         "  if (!tp || tp.indexOf('script.google.com') >= 0 || tp.indexOf('googleusercontent.com') >= 0) return;\n"
         "  document.addEventListener('click', function (e) {\n"
         "    var a = e.target.closest ? e.target.closest('a[target=\"_top\"]') : null;\n"
         "    if (!a || !a.href) return;\n"
         "    e.preventDefault();\n"
         "    try { window.top.postMessage({ hlGo: a.href }, '*'); } catch (x) {}\n"
         "  }, true);\n"
         "  window.hlShellToken = function (t) { try { window.top.postMessage({ hlToken: t }, '*'); } catch (x) {} };\n"
         "})();\n")
BLOCK = BEGIN + '\n' + lib + '\n' + APPLY + END + '\n'

for name in PAGES:
    p = os.path.join(ROOT, 'src', name + '.html')
    t = open(p, encoding='utf-8', newline='').read()
    crlf = '\r\n' in t
    t = t.replace('\r\n', '\n')
    if BEGIN in t:
        i = t.index(BEGIN); j = t.index(END, i) + len(END)
        if t[j:j + 1] == '\n': j += 1
        t = t[:i] + BLOCK + t[j:]
    else:
        m = re.search(r'/\* 圖示工具：.*?\n\}\)\(\);\n', t, re.S)
        if m: t = t[:m.start()] + BLOCK + t[m.end():]
        else:
            assert 'window.__hlEnd = true;' in t, name
            t = t.replace('window.__hlEnd = true;', BLOCK + 'window.__hlEnd = true;', 1)
    if name in POS_PAGES and '/* HL-POS */' not in t:
        k = t.index('<style>') + len('<style>')
        t = t[:k] + '\n' + POS_CSS + t[k:]
    if '.ico{' not in t:
        k = t.index('<style>') + len('<style>')
        t = t[:k] + '\n' + CSS + t[k:]
    open(p, 'w', encoding='utf-8', newline='').write(t.replace('\n', '\r\n') if crlf else t)
    print('已更新', name + '.html')
