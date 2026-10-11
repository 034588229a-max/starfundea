"""把要放上 GitHub Pages 的網站整理成 publish/ 資料夾（直接把裡面的東西拖到 GitHub 倉庫）：
  publish/index.html   服務說明網站（site/index.html）
  publish/app/         手機 App 外殼（pwa/）：員工打卡、店主管理、店家菜單
  publish/.nojekyll    告訴 GitHub Pages 不要用 Jekyll 處理
  publish/brand/       品牌標誌（SVG／PNG），給網站與社群使用
  publish/guide/       商家使用指南（網頁版與 PDF，先執行 make_guide_shots.py、make_merchant_guide.py）
執行：python scripts/build_publish.py（會先重新產生 site/index.html）"""
import os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'publish')
subprocess.check_call([sys.executable, os.path.join(ROOT, 'scripts', 'build_site.py')])
if os.path.isdir(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
shutil.copy(os.path.join(ROOT, 'site', 'index.html'), os.path.join(OUT, 'index.html'))
shutil.copytree(os.path.join(ROOT, 'pwa'), os.path.join(OUT, 'app'), ignore=shutil.ignore_patterns('README.md'))
brand = os.path.join(ROOT, 'brand'); os.makedirs(os.path.join(OUT, 'brand'))
for f in os.listdir(brand):
    if f.endswith(('.svg', '.png')) and f.startswith('starfundea-') and 'brand-sheet' not in f:
        shutil.copy(os.path.join(brand, f), os.path.join(OUT, 'brand', f))
for sub in ('official','kit'):
    shutil.copytree(os.path.join(brand, sub), os.path.join(OUT, 'brand', sub))
vd = os.path.join(ROOT, 'site', 'vendor')
if os.path.isdir(vd): shutil.copytree(vd, os.path.join(OUT, 'vendor'))
ph = os.path.join(ROOT, 'site', 'photos')
if os.path.isdir(ph): shutil.copytree(ph, os.path.join(OUT, 'photos'), ignore=shutil.ignore_patterns('_raw', 'post-qr-brand.jpg'))
g = os.path.join(ROOT, 'guide')
if os.path.isfile(os.path.join(g, 'SFD系統使用指南.html')):
    os.makedirs(os.path.join(OUT, 'guide'))
    shutil.copy(os.path.join(g, 'SFD系統使用指南.html'), os.path.join(OUT, 'guide', 'index.html'))
    if os.path.isfile(os.path.join(g, 'SFD系統使用指南.pdf')): shutil.copy(os.path.join(g, 'SFD系統使用指南.pdf'), os.path.join(OUT, 'guide', 'SFD系統使用指南.pdf'))
open(os.path.join(OUT, '.nojekyll'), 'w').close()
n = sum(len(fs) for _, _, fs in os.walk(OUT))
print(f'已整理 {n} 個檔案到 publish/')
