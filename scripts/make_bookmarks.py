"""專案常用網址的書籤檔（Netscape 書籤格式，Chrome、Edge、Safari、Firefox 都能匯入）。
輸出：bookmarks/星樂創意-書籤.html。網址有變就改下面的 BASE、PAGES、SCRIPT_ID 再執行：python scripts/make_bookmarks.py"""
import html, os, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'bookmarks'); os.makedirs(OUT, exist_ok=True)
EXEC = 'https://script.google.com/macros/s/AKfycbwPhHfsMZ-cXx3r_YLv1hQsk6lf_isDBN8GXybqTb46qKceAC8CVXhhpi6WWPTAYGE/exec'
PAGES = 'https://034588229a-max.github.io/starfundea/'
REPO = 'https://github.com/034588229a-max/starfundea'
SCRIPT_ID = '1Bl-JpTJjZ3_Cks1H1yiMNYIH7q5GxSdZ0gyhNhPqBt9QZ5j4zDysrxst'

TREE = [
 ('① 對外網站與 App', [
   ('服務說明網站', PAGES), ('SFD系統使用指南（網頁）', PAGES + 'guide/'), ('SFD系統使用指南（PDF）', PAGES + 'guide/SFD%E7%B3%BB%E7%B5%B1%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97.pdf'),
   ('手機 App 入口（輸入店家代碼、安裝教學）', PAGES + 'app/'), ('App：員工打卡', PAGES + 'app/clock/'), ('App：店主管理', PAGES + 'app/owner/'), ('App：店家菜單（顧客）', PAGES + 'app/menu/'),
   ('品牌標誌檔（Logo）', PAGES + 'brand/official/logo-horizontal-dark.svg'), ('社群素材範例（封面）', PAGES + 'brand/kit/fb-cover-1640x624.png')]),
 ('② 系統登入與後台（Apps Script 網頁應用程式）', [
   ('登入頁（店主、夥伴）', EXEC), ('管理後台（管理員）', EXEC + '?p=admin'),
   ('試營運店家：員工打卡（店家代碼要換成實際的）', EXEC + '?s=S0001&p=clock'), ('試營運店家：顧客電子菜單', EXEC + '?s=S0001&p=menu'),
   ('試營運店家：面試登記頁', EXEC + '?s=S0001&p=apply')]),
 ('③ 開發與部署', [
   ('Apps Script 專案編輯器（執行函式、看紀錄）', f'https://script.google.com/home/projects/{SCRIPT_ID}/edit'),
   ('Apps Script 我的專案', 'https://script.google.com/home'), ('Apps Script 設定（開啟 Apps Script API）', 'https://script.google.com/home/usersettings'),
   ('Apps Script 部署作業', f'https://script.google.com/home/projects/{SCRIPT_ID}/deployments'), ('Apps Script 執行紀錄', f'https://script.google.com/home/projects/{SCRIPT_ID}/executions'),
   ('Apps Script 專案設定（指令碼屬性）', f'https://script.google.com/home/projects/{SCRIPT_ID}/settings'),
   ('GitHub 倉庫 starfundea', REPO), ('GitHub：上傳檔案', REPO + '/upload'), ('GitHub：Pages 設定', REPO + '/settings/pages'), ('GitHub：提交紀錄', REPO + '/commits/main'),
   ('Google 雲端硬碟', 'https://drive.google.com/drive/my-drive'), ('Google 試算表', 'https://docs.google.com/spreadsheets/')]),
 ('④ 品牌、名稱與商標查詢', [
   ('經濟部商工登記公示資料（查公司名稱）', 'https://findbiz.nat.gov.tw'), ('智慧財產局 商標檢索', 'https://tmsearch.tipo.gov.tw'), ('WIPO 全球品牌資料庫', 'https://branddb.wipo.int'),
   ('TWNIC（.tw 網域查詢）', 'https://www.twnic.tw'), ('Namecheap 網域搜尋', 'https://www.namecheap.com/domains/'), ('Cloudflare 網域', 'https://dash.cloudflare.com'),
   ('Google Fonts（Noto Sans TC、Barlow Condensed）', 'https://fonts.google.com'), ('Lucide 圖示庫（本專案圖示來源）', 'https://lucide.dev/icons/')]),
 ('⑤ 官方文件與說明', [
   ('Apps Script 文件', 'https://developers.google.com/apps-script'), ('Apps Script 配額限制', 'https://developers.google.com/apps-script/guides/services/quotas'),
   ('clasp（Apps Script 命令列工具）', 'https://github.com/google/clasp'), ('GitHub Pages 說明', 'https://docs.github.com/pages'),
   ('財政部電子發票整合服務平台', 'https://www.einvoice.nat.gov.tw'), ('財政部稅務入口網', 'https://www.etax.nat.gov.tw')]),
]

def build():
    t = str(int(time.time()))
    out = ['<!DOCTYPE NETSCAPE-Bookmark-file-1>', '<!-- This is an automatically generated file. It will be read and overwritten. DO NOT EDIT! -->',
           '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">', '<TITLE>Bookmarks</TITLE>', '<H1>Bookmarks</H1>', '<DL><p>',
           f'    <DT><H3 ADD_DATE="{t}" LAST_MODIFIED="{t}">星樂創意 StarFunDea</H3>', '    <DL><p>']
    for folder, links in TREE:
        out.append(f'        <DT><H3 ADD_DATE="{t}" LAST_MODIFIED="{t}">{html.escape(folder)}</H3>'); out.append('        <DL><p>')
        for name, url in links: out.append(f'            <DT><A HREF="{html.escape(url, quote=True)}" ADD_DATE="{t}">{html.escape(name)}</A>')
        out.append('        </DL><p>')
    out += ['    </DL><p>', '</DL><p>']
    return '\n'.join(out) + '\n'

p = os.path.join(OUT, '星樂創意-書籤.html')
open(p, 'w', encoding='utf-8').write(build())
print('已產生', p, '共', sum(len(l) for _, l in TREE), '個書籤')
