"""Apps Script 陷阱檢查：改完 src/ 任何檔案先跑。
python3 scripts/check_gas.py
"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
bad = []
names = {}
for f in sorted(os.listdir(SRC)):
    base, ext = os.path.splitext(f)
    if ext in ('.gs', '.html'):
        if base in names: bad.append(f'檔名重複：{names[base]} 與 {f}（Apps Script 的指令碼與 HTML 不能同名）')
        names[base] = f
    if ext != '.html': continue
    s = open(os.path.join(SRC, f), encoding='utf-8').read()
    if '__hlEnd = true' not in s: bad.append(f'{f}：結尾缺少 window.__hlEnd = true')
    for m in re.finditer(r'<script>(.*?)</script>', s, flags=re.S):
        start = s[:m.start()].count('\n') + 1
        for i, line in enumerate(m.group(1).split('\n')):
            code = line.strip()
            if re.search(r'\\\\/{2}', line) and not code.startswith('//'):
                bad.append(f'{f}:{start + i}：正規表示式裡有 \\\\//（會被 Apps Script 當成註解砍掉）→ {code[:80]}')
            if '//' in line and not code.startswith('//'):
                # 行尾註解會被砍掉但無害；字串裡的 // 會壞掉——一律提醒，讓人確認
                idx = line.index('//'); before = line[:idx]
                if before.count("'") % 2 or before.count('"') % 2 or before.count('`') % 2:
                    bad.append(f'{f}:{start + i}：字串裡有 //（會被 Apps Script 砍掉）→ {code[:80]}')
for f in sorted(os.listdir(SRC)):
    if f.endswith('.html'):
        s = open(os.path.join(SRC, f), encoding='utf-8').read()
        for m in re.finditer(r'<\?=', s): bad.append(f'{f}：用了 <?= ?>（會自動跳脫加引號），請改 <?!= ?>')
print('\n'.join(bad) if bad else 'OK：沒有發現 Apps Script 陷阱')
sys.exit(1 if bad else 0)
