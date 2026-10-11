"""把 site/book/ 的頁面資料排進 site/index.template.html 的書本（翻書首屏）：
  python scripts/build_book.py   （之後再執行 python scripts/build_site.py 產生 site/index.html）
來源：site/book/pages.json、site/book/demos/*.html（動態展示，從簡報轉來）、site/book/cover_front.html（封面）。
範本裡 BOOK:BEGIN／END、DOTS:BEGIN／END、BOOKDEMOS:BEGIN／END 三組標記之間的內容由本程式重新產生，可重複執行。"""
import html as H, io, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, 'site', 'book')
TPL = os.path.join(ROOT, 'site', 'index.template.html')
CHAP = {'菜單': '菜單', '名片': '名片', '人事': '人事管理', '公告收支': '公告・交接・收支'}
DOT = {'菜單': '菜單', '名片': '名片', '人事': '人事管理', '公告收支': '公告・交接・收支'}


def rd(p):
    return io.open(p, encoding='utf-8').read()


def lis(points, cls=''):
    return '<ul class="pts%s">%s</ul>' % (cls, ''.join('<li>%s</li>' % x for x in points))


def text_page(i, p):
    tb = '<div class="lvt">%s</div>' % p['table'] if p.get('table') else ''
    return ('<div class="face back"><div class="pg left"><div class="pg-in"><div class="no">%02d</div><div class="kk">%s</div><h3>%s</h3>%s%s'
            '%s</div></div></div>') % (i, p['kicker'], p['title'], lis(p['points']), tb, ('<div class="hl2"><small>%s</small><b>%s</b></div>' % (p['hlSmall'], p['hlBig'])) if p['hlBig'] else '')


def demo_front(i, p):
    return ('<div class="face front"><div class="pg right"><div class="mhead"><div class="no">%02d　%s</div><h3>%s</h3></div>'
            '<div class="dm" data-d="%s"><iframe title="%s" sandbox="allow-scripts" tabindex="-1"></iframe></div>'
            '%s%s</div></div>') % (i, CHAP[p['chapter']], p['title'], p['id'], H.escape(p['kicker']), ('<div class="dmc"><small>%s</small><b>%s</b></div>' % (p['hlSmall'], p['hlBig'])) if p['hlBig'] else '', lis(p['points'], ' mo'))


GIFT_FRONT = ('<div class="face front"><div class="pg right"><div class="mhead"><div class="no">開店禮包</div><h3>現在試用，名片下個月就寄到</h3></div><div class="dev"><div class="hd"><b>開店禮包</b><span>免費試用期間</span></div>'
              '<div class="gf" data-onshow="%d"><div class="gi"><b>Logo 設計</b><small>品牌的起點</small></div><div class="gi"><b>品牌規格書</b><small>色彩、字體、用法</small></div><div class="gi"><b>名片</b><small>次月高級印刷寄出</small></div><div class="gi"><b>社群推廣工具</b><small>LINE、FB 大頭貼與封面</small></div></div>'
              '<p class="gnote">單店、多店都適用。不用倒數、不用搶名額，想開通就告訴我們。</p>'
              '<a class="btn pri" href="{{APP_URL}}" style="width:100%%;margin-top:6px">預約開通</a></div></div></div>')
GIFT_BACK = ('<div class="face back"><div class="pg left"><div class="pg-in"><div class="no">+</div><div class="kk">還有這些</div><h3>不只是這些畫面</h3><ul class="pts">'
             '<li><b>發連結，對方自己填</b>：員工、廠商、應徵者各一條網址，資料進來你只要按確認</li>'
             '<li><b>我們也能代建檔</b>：菜單、員工、廠商一次建好</li>'
             '<li><b>實體物料一起做</b>：Logo、規格書、名片、護貝菜單、桌牌 QR</li></ul><p class="hint">往下捲，看完整功能與方案費用。</p></div></div></div>')


def build():
    pages = json.loads(rd(os.path.join(BOOK, 'pages.json')))
    D = len(pages)
    cover = rd(os.path.join(BOOK, 'cover_front.html')).strip()
    leaves = ['<div class="leaf" data-i="0">%s%s</div>' % (cover, text_page(1, pages[0]))]
    for k in range(1, D + 1):
        back = text_page(k + 1, pages[k]) if k < D else GIFT_BACK.replace('</div></div></div>', '</div></div></div>', 1)
        # 最後一張示範頁的背面（左頁）改成「禮包」說明；禮包頁自己的背面是「還有這些」
        if k == D:
            back = ('<div class="face back"><div class="pg left"><div class="pg-in"><div class="no">+</div><div class="kk">開店禮包</div><h3>現在試用，名片下個月就寄到</h3><ul class="pts">'
                    '<li><b>Logo 設計</b>：品牌的起點，歸店家所有</li><li><b>品牌規格書</b>：色彩、字體、用法一次講清楚</li>'
                    '<li><b>名片</b>：次月高級印刷寄出</li><li><b>社群推廣工具</b>：LINE、FB 大頭貼與封面</li></ul>'
                    '<div class="hl2"><small>不用倒數，不用搶名額</small><b>想開通，按一下就好</b></div></div></div></div>')
        leaves.append('<div class="leaf" data-i="%d">%s%s</div>' % (k, demo_front(k, pages[k - 1]), back))
    leaves.append('<div class="leaf" data-i="%d">%s%s</div>' % (D + 1, GIFT_FRONT % (D + 1), GIFT_BACK))
    # 章節點
    dots, first = [], {}
    for k, p in enumerate(pages, 1):
        first.setdefault(p['chapter'], [k, k])[1] = k
    for ch, (a, b) in first.items():
        dots.append('<button type="button" class="dot" data-n="%d" data-r="%d-%d" aria-label="%s"><i></i><span>%s</span></button>' % (a, a, b, DOT[ch], DOT[ch]))
    dots.append('<button type="button" class="dot" data-n="%d" data-r="%d-%d" aria-label="開店禮包"><i></i><span>開店禮包</span></button>' % (D + 1, D + 1, D + 1))
    dots.append('<button type="button" class="dot" data-n="%d" data-r="%d-%d" aria-label="開始試用"><i></i><span>開始</span></button>' % (D + 2, D + 2, D + 2))
    demos = {}
    for p in pages:
        demos[p['id']] = rd(os.path.join(BOOK, 'demos', p['id'] + '.html'))
    js = json.dumps(demos, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/').replace('<!--', '<\\!--').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    t = rd(TPL)

    def put(t, tag, body):
        a, b = '<!--%s:BEGIN-->' % tag, '<!--%s:END-->' % tag
        if tag == 'BOOKDEMOS':
            a, b = '/*BOOKDEMOS:BEGIN*/', '/*BOOKDEMOS:END*/'
        i, j = t.index(a), t.index(b)
        return t[:i + len(a)] + '\n' + body + '\n' + t[j:]
    t = put(t, 'BOOK', '\n'.join(leaves))
    t = put(t, 'DOTS', ''.join(dots))
    t = put(t, 'BOOKDEMOS', 'var DEMOS = ' + js + ';var BOOK_D = %d;' % D)
    io.open(TPL, 'w', encoding='utf-8', newline='').write(t)
    print('ok：%d 頁示範、%d 個章節點' % (D, len(dots)))


if __name__ == '__main__':
    build()
