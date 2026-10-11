/**
 * 主畫面（HomeServer.gs）：點餐機式的大按鈕首頁，店主與夥伴登入後先到這裡，再點進各功能。
 * 網址 ?p=home&t=通行證（單店：?p=home&staff=鑰匙）。按鈕上的小徽章是「現在要處理的事」。
 */
function homeUrl_(p, key) {
  var base = tWebUrl_(); if (!base) return '';
  var k = (typeof saas_ === 'function' && saas_() ? 't=' : 'staff=') + key;
  return base + '?' + (p ? 'p=' + p + '&' : '') + k;
}
function homeState(key) {
  tGuardRead_(key);
  var owner = typeof isOwner_ === 'function' ? isOwner_() : true, saas = typeof saas_ === 'function' && saas_();
  var cfg = typeof shopCfg_ === 'function' ? shopCfg_() : {}, today = stToday_(), badge = {};
  try { if (typeof lgEntries_ === 'function') { var s = lgSum_(lgEntries_(today, today)); badge.ledger = s.out || s.inn ? '今日支出 ' + s.out.toLocaleString('en-US') : ''; } } catch (e) {}
  if (owner) {
    try {
      var pend = stLeaves_().filter(function (l) { return l.status === '待審'; }).length;
      var wait = stEmps_().filter(function (e) { return e.status === '待確認'; }).length;
      var apps = stApplies_().filter(function (a) { return a.status === '新登記'; }).length;
      var n = pend + wait + apps;
      badge.staff = n ? n + ' 件待處理' : '';
    } catch (e) {}
  }
  var base = tWebUrl_(), clockUrl = base ? base + (saas ? '?s=' + CTX.shopId + '&p=clock' : '?p=clock') : '';
  var tl = function (p, tab) { var u = homeUrl_('tools', key); return u && tab ? u + '&tab=' + tab : u; };
  var tiles = [
    { cat: 'menu', id: 'menu', t: '菜單改價', s: '價格、A3 菜單、調價助手', ic: 'book-open', url: homeUrl_('', key), badge: '' }
  ];
  if (saas && base) tiles.push({ cat: 'menu', id: 'customer', t: '顧客電子菜單', s: '看顧客看到的畫面', ic: 'smartphone', url: base + '?s=' + CTX.shopId + '&p=menu', badge: '', blank: true });
  tiles.push(
    { cat: 'mkt', id: 'notice', t: '公告海報', s: '公休、活動、節慶、價格調整', ic: 'newspaper', url: tl('tools', 'notice'), badge: '' },
    { cat: 'mkt', id: 'table', t: '桌號 QR', s: '掃碼點餐、候位、外帶海報', ic: 'qr-code', url: tl('tools', 'table'), badge: '' },
    { cat: 'mkt', id: 'wifi', t: 'Wi-Fi 卡', s: '客人掃碼直接連網', ic: 'wifi', url: tl('tools', 'wifi'), badge: '' },
    { cat: 'mkt', id: 'card', t: '名片', s: '含 QR Code，可印刷', ic: 'credit-card', url: tl('tools', 'card'), badge: '' },
    { cat: 'mkt', id: 'hiring', t: '徵才海報', s: '掃碼登記面試', ic: 'user-plus', url: (homeUrl_('tools', key) || '') + '&hiring=1', badge: '' },
    { cat: 'ops', id: 'cal', t: '店休日曆', s: '公休、特別營業日', ic: 'calendar', url: tl('tools', 'cal'), badge: '' },
    { cat: 'ops', id: 'hand', t: '交接紀錄', s: '各班交代、今日摘要', ic: 'notebook-pen', url: tl('tools', 'hand'), badge: '' },
    { cat: 'fin', id: 'ledger', t: '店務收支', s: '進貨記帳、發票、月結、報表', ic: 'wallet', url: homeUrl_('ledger', key), badge: badge.ledger || '' }
  );
  if (owner) tiles.push({ cat: 'staff', id: 'staff', t: '人員與班表', s: '員工、排班、請假、徵才', ic: 'users', url: homeUrl_('staff', key), badge: badge.staff || '' });
  if (clockUrl) tiles.push({ cat: 'staff', id: 'clock', t: '員工打卡', s: '在這支手機打卡', ic: 'clock', url: clockUrl, badge: '', blank: true });
  if (owner) {
    tiles.push({ cat: 'set', id: 'logo', t: 'Logo 與店家資料', s: '店名、配色範本、Logo', ic: 'store', url: tl('tools', 'logo'), badge: '' });
    tiles.push({ cat: 'set', id: 'setup', t: '設定精靈', s: '地址、電話、LINE、配色', ic: 'palette', url: saas ? homeUrl_('setup', key) : '', badge: '' });
    if (saas && !CTX.shop.brandId) tiles.push({ cat: 'set', id: 'brand', t: '分店管理', s: '同步、跨店調價與公告', ic: 'building-2', url: homeUrl_('brand', key), badge: '' });
    if (saas) tiles.push({ cat: 'set', id: 'account', t: '帳號與訂閱', s: '夥伴、授權、顧客網址', ic: 'user-check', url: homeUrl_('account', key), badge: '' });
  } else {
    tiles.push({ cat: 'set', id: 'logo', t: '店家資料', s: 'Logo 與配色', ic: 'store', url: tl('tools', 'logo'), badge: '' });
  }
  tiles = tiles.filter(function (x) { return x.url; });
  var lic = saas && CTX.lic ? { label: CTX.lic.label, msg: CTX.lic.msg, expires: CTX.lic.expires, mode: CTX.lic.mode } : null;
  var cats = [{ k: 'menu', n: '菜單', ic: 'book-open' }, { k: 'mkt', n: '行銷', ic: 'megaphone' }, { k: 'ops', n: '店務', ic: 'clipboard-list' }, { k: 'fin', n: '財務', ic: 'wallet' }, { k: 'staff', n: '人員', ic: 'users' }, { k: 'set', n: '設定與帳號', ic: 'settings' }];
  return { name: cfg.name || '', owner: owner, today: today, tiles: tiles, cats: cats, lic: lic, brand: typeof brand_ === 'function' ? brand_() : {} };
}
function homePage_(key) {
  tGuardRead_(key);
  var t = HtmlService.createTemplateFromFile('Home');
  t.boot = tJs_({ token: key, state: homeState(key) });
  return t.evaluate().setTitle('主畫面')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
