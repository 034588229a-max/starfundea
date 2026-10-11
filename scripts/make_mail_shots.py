"""商家指南用的信件截圖：直接用 src/Mail.gs 與 src/Auth.gs 的真實版型產生（不是另外畫的圖）。
輸出 guide/shots/32-mail.png（手機寬 390px、2 倍解析度），make_merchant_guide.py 的「系統寄出的信」會用到。
執行：python scripts/make_mail_shots.py（在 make_guide_shots.py 之後、make_merchant_guide.py 之前）"""
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src'); OUT = os.path.join(ROOT, 'guide', 'shots'); os.makedirs(OUT, exist_ok=True)
STUB = """
var captured = null;
function mail_(to, subject, body, o) { captured = o; }
function webUrl_() { return 'https://example.com/exec'; }
function licOf_() { return { mode: 'full' }; }
function productName_() { return '星樂創意 StarFunDea'; }
"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 390, 'height': 800}, device_scale_factor=2)
    pg.set_content('<html><body></body></html>')
    pg.add_script_tag(content=open(os.path.join(SRC, 'Mail.gs'), encoding='utf-8').read())
    pg.add_script_tag(content=open(os.path.join(SRC, 'Auth.gs'), encoding='utf-8').read())
    pg.add_script_tag(content=STUB)
    html = pg.evaluate("""() => {
      actMail_({ name: '示範早午餐店', taxId: '12345675', status: 'pilot', expires: '2026-11-10', email: 'shop@example.com' }, false);
      return mailHtml_(captured).replace('cid:sfdLogo', 'data:image/png;base64,' + MAIL_LOGO_B64).replace('cid:sfdMark', 'data:image/png;base64,' + MAIL_MARK_B64);
    }""")
    pg.set_content(html); pg.wait_for_timeout(200)
    pg.screenshot(path=os.path.join(OUT, '32-mail.png'), full_page=True)
    b.close()
print('已產生 guide/shots/32-mail.png')
