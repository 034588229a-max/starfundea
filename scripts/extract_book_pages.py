"""把簡報（官網書本改版計劃）的頁面轉成官網書本用的資料：
  python scripts/extract_book_pages.py <簡報 slides 資料夾>
產生 site/book/pages.json（標題、重點、重點句、章節）與 site/book/demos/<id>.html（動態展示頁）。
之後執行 python scripts/build_book.py 把它們排進 site/index.template.html。"""
import html, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = [
    ('menu', '菜單'), ('menutag', '菜單'), ('menuout', '菜單'),
    ('card', '名片'),
    ('hr', '人事'), ('hrform', '人事'), ('portal', '人事'), ('schedule', '人事'), ('clock', '人事'), ('leave', '人事'),
    ('notice', '公告收支'), ('hire', '公告收支'), ('handover', '公告收支'), ('ledger', '公告收支'), ('reminder', '公告收支'),
]


FALLBACK = {'leave': ('依勞動基準法第 38 條', '特休天數自動算、自動扣')}


def inner(s):
    return re.sub(r'\s+', ' ', s).strip()


def main(src):
    out, demos = [], os.path.join(ROOT, 'site', 'book', 'demos')
    os.makedirs(demos, exist_ok=True)
    for sid, chap in ORDER:
        t = io.open(os.path.join(src, sid + '.html'), encoding='utf-8').read()
        kick = re.search(r'text-transform:uppercase">(.*?)</p>', t, re.S).group(1)
        title = re.search(r'<h2[^>]*>(.*?)</h2>', t, re.S).group(1)
        ul = re.search(r'<ul[^>]*>(.*?)</ul>', t, re.S).group(1)
        lis = [inner(x) for x in re.findall(r'<li>(.*?)</li>', ul, re.S)]
        box = re.search(r'<div style="width:700px;background:#0E1623[^>]*>(.*?)</div>', t, re.S)
        hl = re.findall(r'<p[^>]*>(.*?)</p>', box.group(1), re.S) if box else []
        if not hl and sid in FALLBACK:
            hl = list(FALLBACK[sid])
        table = re.search(r'<table style="font-size:30px.*?</table>', t, re.S)
        emb = re.search(r'<x-embed[^>]*>(.*?)</x-embed>', t, re.S).group(1)
        io.open(os.path.join(demos, sid + '.html'), 'w', encoding='utf-8', newline='\n').write(emb)
        out.append({'id': sid, 'chapter': chap, 'kicker': inner(kick), 'title': inner(title), 'points': lis,
                    'hlSmall': inner(hl[0]) if len(hl) > 0 else '', 'hlBig': inner(hl[1]) if len(hl) > 1 else '',
                    'table': re.sub(r' style="[^"]*"', '', inner(table.group(0))) if table else ''})
    io.open(os.path.join(ROOT, 'site', 'book', 'pages.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('ok', len(out))


if __name__ == '__main__':
    main(sys.argv[1])
