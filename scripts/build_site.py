"""產生服務說明網頁：把 site/index.template.html 的 {{APP_URL}} 換成正式服務網址（installer/config.json 的 serviceUrl）。
python scripts/build_site.py  →  site/index.html（純靜態、無外部套件，可直接放 Cloudflare Pages／GitHub Pages）
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(ROOT, 'installer', 'config.json'), encoding='utf-8-sig'))
url = cfg.get('serviceUrl') or '#'
tpl = open(os.path.join(ROOT, 'site', 'index.template.html'), encoding='utf-8').read()
out = tpl.replace('{{APP_URL}}', url)
open(os.path.join(ROOT, 'site', 'index.html'), 'w', encoding='utf-8', newline='').write(out)
print('已產生 site/index.html，按鈕指向：', url)
