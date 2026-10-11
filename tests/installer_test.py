"""啟用工具核心測試：用本機假伺服器模擬 Apps Script（POST → 302 轉址 → GET 回 JSON）。
執行：python tests/installer_test.py
"""
import http.server, json, os, sys, tempfile, threading, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'installer'))
TMP = tempfile.mkdtemp()
os.environ['APPDATA'] = TMP
import activate_core as core

results = []
def check(name, cond, info=''):
    results.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ← ' + str(info)[:300]))

STORE, SEEN = {}, []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode('utf-8')
        SEEN.append((self.headers.get('Content-Type'), json.loads(body)))
        q = json.loads(body)
        if q['action'] == 'login':
            out = {'ok': True, 'mail': 'sh***@example.com'} if q['password'] == 'good1234' else {'ok': False, 'code': 'bad', 'msg': '統編或密碼不正確'}
        elif q['action'] == 'verify':
            out = {'ok': True, 'token': 'tok', 'shop': {'id': 'S1', 'name': '小確幸'}, 'lic': {'label': '試用', 'expires': '2026-11-01'},
                   'urls': {'menu': 'https://x/exec?t=tok', 'tools': 'https://x/exec?p=tools&t=tok'}, 'sheetUrl': 'https://docs/x'} if q['code'] == '123456' else {'ok': False, 'msg': '驗證碼不正確或已過期'}
        else: out = {'ok': False}
        STORE['r'] = json.dumps(out)
        self.send_response(302); self.send_header('Location', '/echo'); self.end_headers()
    def do_GET(self):
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(STORE.get('r', '{}').encode('utf-8'))

srv = http.server.HTTPServer(('127.0.0.1', 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = 'http://127.0.0.1:%d/exec' % srv.server_address[1]

r = core.start_login(url, ' 22099131 ', 'bad')
check('密碼錯誤：回傳訊息', not r['ok'] and '不正確' in r['msg'], r)
check('用 text/plain 送出（Apps Script 不用預檢）', SEEN[-1][0].startswith('text/plain') and SEEN[-1][1]['taxId'] == '22099131', SEEN[-1])
r = core.start_login(url, '22099131', 'good1234'); check('密碼正確：回傳遮罩信箱（跟隨 302 轉址）', r['ok'] and r['mail'].startswith('sh***'), r)
r = core.verify_login(url, '22099131', '000000'); check('驗證碼錯誤：不存登入狀態', not r['ok'] and core.load_session() is None, r)
r = core.verify_login(url, '22099131', ' 123456 '); check('驗證成功', r['ok'] and r['shop']['name'] == '小確幸', r)
s = core.load_session(); check('登入狀態存在使用者資料夾', s and s['token'] == 'tok' and s['urls']['menu'].endswith('t=tok'), s)
check('裝置代碼固定不變', core.device_id() == core.device_id() and len(core.device_id()) == 32 and SEEN[-1][1]['device'] == core.device_id())
folder = tempfile.mkdtemp()
made = core.make_shortcuts(s, folder)
check('建立兩個桌面捷徑（.url）', len(made) == 2 and all(os.path.exists(p) for p in made), made)
check('捷徑內容是正確網址', 'URL=https://x/exec?t=tok' in open(made[0], encoding='utf-8').read())
check('檔名去掉不能用的字元', os.path.basename(core.make_shortcut('a/b:c', 'https://x', folder)) == 'abc.url')
try:
    core.call('http://127.0.0.1:1/none', {'action': 'login'}, timeout=2); check('連不上服務會丟出清楚的錯誤', False)
except core.ApiError as e:
    check('連不上服務會丟出清楚的錯誤', '連不上' in str(e), e)
try:
    core.call('', {}); check('沒設定網址會提醒', False)
except core.ApiError as e:
    check('沒設定網址會提醒', 'serviceUrl' in str(e), e)

ok = sum(1 for _, c in results if c)
print(f'\n{ok}/{len(results)} 通過')
sys.exit(0 if ok == len(results) else 1)
