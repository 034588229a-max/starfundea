/**
 * 店務收支（LedgerServer.gs；前綴 lg）：進貨支出、固定廠商快速記帳、其他支出、收入，月報表與月結待付款。
 * 資料在每家店自己的試算表：「廠商」「收支」兩個分頁（純文字格式）。工具函式沿用 StaffServer.gs 的 st*（試算表讀寫、日期）。
 * 權限：店主與夥伴都能記帳、看今天的明細；刪除、廠商設定、報表、結清只有店主（夥伴只能撤銷自己 10 分鐘內記的最後一筆）。
 */
var LG_OUT_CATS = ['進貨：食材', '進貨：飲料', '進貨：包材', '人事', '租金', '水電瓦斯', '設備維修', '行銷廣告', '雜支', '其他'];
var LG_IN_CATS = ['現場營業額', '外送平台', '線上訂單', '其他收入'];
var LG_PAYS = ['現金', '轉帳', '信用卡', '月結'];
var LG_DOCS = ['統一發票', '收據', '無憑證'];
var LG_TAX_RATE = 0.05;
var LG_MAX_VENDORS = 30;
var LG_MAX_AMOUNT = 9999999;

function lgGuard_(key, write) {
  if (write) tGuard_(key); else tGuardRead_(key);
  var owner = typeof isOwner_ === 'function' ? isOwner_() : true;
  return { owner: owner, uid: (typeof CTX !== 'undefined' && CTX && CTX.uid) || 'owner' };
}
function lgOwner_(key, write) {
  var g = lgGuard_(key, write);
  if (!g.owner) throw new Error('只有店主可以做這個操作');
  return g;
}
function lgInt_(v) { var n = Math.round(Number(String(v).replace(/[, ]/g, ''))); return isNaN(n) ? 0 : n; }

/* ---------- 廠商 ---------- */
function lgVendors_(all) {
  return stRows_('vendor').map(function (r) {
    return { id: String(r['編號']), name: String(r['名稱']), cat: String(r['分類']), pay: String(r['付款方式'] || '現金'),
      quick: String(r['常用金額'] || '').split(/[,，\s]+/).map(lgInt_).filter(function (n) { return n > 0; }).slice(0, 4),
      status: String(r['狀態'] || '使用中'), sort: Number(r['排序']) || 0, pin: String(r['置頂']) === '是',
      orderDays: stStr_(r['叫貨日']).split(/[,，\s]+/).filter(function (x) { return /^[0-6]$/.test(x); }).map(Number),
      time: stT_(r['叫貨時間']) || '15:00', assignee: String(r['負責人'] || ''), _r: r._r };
  }).filter(function (v) { return all || v.status === '使用中'; }).sort(function (a, b) { return (b.pin ? 1 : 0) - (a.pin ? 1 : 0) || a.sort - b.sort || (a.id < b.id ? -1 : 1); });
}
function lgVendorPub_(v) { return { id: v.id, name: v.name, cat: v.cat, pay: v.pay, quick: v.quick, status: v.status, pin: v.pin, orderDays: v.orderDays, time: v.time, assignee: v.assignee }; }
function lgVendorRow_(id, name, cat, pay, quick, status, sort, pin, days, time, assignee) { return [id, name, cat, pay, quick.join(','), status, sort, pin ? '是' : '', days.join(','), time || '15:00', assignee || '']; }

/** 新增或修改固定廠商。v = {id?, name, cat, pay, quick:[金額…]} */
function lgVendorSave(v, key) {
  lgOwner_(key, true);
  return lgVendorSave_(v);
}
/** 同上，但不檢查權限（給種子資料用，驗證規則完全一樣）。 */
function lgVendorSave_(v) {
  v = v || {};
  var name = tClean_(v.name, 12).trim();
  if (!name) throw new Error('請填廠商名稱');
  var cat = LG_OUT_CATS.indexOf(v.cat) >= 0 ? v.cat : '進貨：食材';
  var pay = LG_PAYS.indexOf(v.pay) >= 0 ? v.pay : '現金';
  var quick = (Array.isArray(v.quick) ? v.quick : String(v.quick || '').split(/[,，\s]+/)).map(lgInt_).filter(function (n) { return n > 0 && n <= LG_MAX_AMOUNT; }).slice(0, 4);
  var days = (Array.isArray(v.orderDays) ? v.orderDays : []).map(Number).filter(function (n, i, a) { return n >= 0 && n <= 6 && a.indexOf(n) === i; }).sort();
  return stLocked_(function () {
    var all = lgVendors_(true), cur = v.id ? all.filter(function (x) { return x.id === String(v.id); })[0] : null;
    if (v.id && !cur) throw new Error('找不到這家廠商');
    if (all.some(function (x) { return x.status === '使用中' && x.name === name && (!cur || x.id !== cur.id); })) throw new Error('已經有一家叫「' + name + '」的廠商了');
    if (!cur && all.filter(function (x) { return x.status === '使用中'; }).length >= LG_MAX_VENDORS) throw new Error('固定廠商最多 ' + LG_MAX_VENDORS + ' 家，請先停用不用的');
    var pin = v.pin === true || v.pin === '是';
    var time = stTimeOk_(v.orderTime) ? v.orderTime : (cur ? cur.time : '15:00'), who = v.assignee != null ? tClean_(v.assignee, 12).trim() : (cur ? cur.assignee : '');
    if (cur) stPut_('vendor', cur._r, lgVendorRow_(cur.id, name, cat, pay, quick, '使用中', cur.sort, pin, days, time, who));
    else stPut_('vendor', 0, lgVendorRow_(stNextId_('vendor', 'V', 3), name, cat, pay, quick, '使用中', all.length + 1, pin, days, time, who));
    return lgVendors_().map(lgVendorPub_);
  });
}
function lgVendorDelete(id, key) {
  lgOwner_(key, true);
  var v = lgVendors_(true).filter(function (x) { return x.id === String(id); })[0];
  if (v) stPut_('vendor', v._r, lgVendorRow_(v.id, v.name, v.cat, v.pay, v.quick, '停用', v.sort, v.pin, v.orderDays, v.time, v.assignee));
  return lgVendors_().map(lgVendorPub_);
}

/* ---------- 收支明細 ---------- */
function lgEntries_(from, to) {
  return stRows_('ledger').map(function (r) {
    return { id: String(r['編號']), d: stStr_(r['日期']), type: String(r['類型']), cat: String(r['分類']), vid: String(r['廠商編號'] || ''), vendor: String(r['廠商名稱'] || ''),
      amt: Number(r['金額']) || 0, pay: String(r['付款方式'] || ''), paid: String(r['結清'] || '是') !== '否', note: String(r['備註'] || ''), by: String(r['記錄者'] || ''), at: String(r['建立時間'] || ''),
      inv: String(r['發票號碼'] || ''), items: String(r['購買品項'] || ''), taxable: r['應稅金額'] === '' || r['應稅金額'] == null ? null : Number(r['應稅金額']), tax: Number(r['稅額']) || 0, buyer: String(r['採購人員'] || ''), doc: String(r['憑證'] || ''), file: String(r['收據檔案'] || ''), orig: String(r['正本'] || ''), _r: r._r };
  }).filter(function (e) { return (!from || e.d >= from) && (!to || e.d <= to); });
}
function lgPub_(e) { return { id: e.id, d: e.d, type: e.type, cat: e.cat, vid: e.vid, vendor: e.vendor, amt: e.amt, pay: e.pay, paid: e.paid, note: e.note, by: e.by, at: e.at, inv: e.inv, items: e.items, taxable: e.taxable, tax: e.tax, buyer: e.buyer, doc: e.doc, hasFile: !!e.file, orig: e.orig }; }
function lgRowArr_(e) {
  return [e.id, e.d, e.type, e.cat, e.vid, e.vendor, e.amt, e.pay, e.paid ? '是' : '否', e.note, e.by, e.at, e.inv || '', e.items || '', e.taxable == null ? '' : e.taxable, e.tax || 0, e.buyer || '', e.doc || '', e.file || '', e.orig || ''];
}
function lgBuyerName_(g) {
  if (g.owner) return '店主';
  try { var p = typeof partnerById_ === 'function' ? partnerById_(g.uid) : null; if (p && p.name) return String(p.name).slice(0, 12); } catch (e) {}
  return '夥伴';
}
function lgSum_(list) {
  var s = { out: 0, inn: 0, unpaid: 0 };
  list.forEach(function (e) { if (e.type === '收入') s.inn += e.amt; else { s.out += e.amt; if (e.pay === '月結' && !e.paid) s.unpaid += e.amt; } });
  s.net = s.inn - s.out; return s;
}

/** 記一筆。e = {type:'支出'|'收入', cat, vendorId?, amount, pay, note, date?} */
function lgAdd(e, key) {
  var g = lgGuard_(key, true);
  e = e || {};
  var type = e.type === '收入' ? '收入' : '支出';
  var amt = lgInt_(e.amount);
  if (amt < 1) throw new Error('請輸入金額');
  if (amt > LG_MAX_AMOUNT) throw new Error('金額太大了，請確認');
  var today = stToday_(), d = stDayOk_(e.date) ? e.date : today;
  if (d > today) throw new Error('不能記未來的日期');
  if (!g.owner && d < stAdd_(today, -1)) throw new Error('夥伴只能記今天或昨天的帳，更早的請店主補記');
  if (d < stAdd_(today, -400)) throw new Error('日期太久以前了');
  var v = e.vendorId ? lgVendors_(true).filter(function (x) { return x.id === String(e.vendorId); })[0] : null;
  if (e.vendorId && !v) throw new Error('找不到這家廠商');
  var cat = tClean_(e.cat, 12) || (v ? v.cat : '');
  var cats = type === '收入' ? LG_IN_CATS : LG_OUT_CATS;
  if (cats.indexOf(cat) < 0) cat = type === '收入' ? '其他收入' : '其他';
  var pay = LG_PAYS.indexOf(e.pay) >= 0 ? e.pay : (v ? v.pay : '現金');
  if (type === '收入' && pay === '月結') pay = '轉帳';
  /* 憑證：統一發票要有發票號碼；應稅金額預設 = 含稅金額 ÷ 1.05（可改；免稅就等於金額、稅額 0） */
  var doc = LG_DOCS.indexOf(e.doc) >= 0 ? e.doc : '無憑證', inv = String(e.invoice || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 20), taxable = null, tax = 0;
  if (type === '收入') { doc = ''; inv = ''; }
  else if (doc === '統一發票') {
    if (!/^[A-Z]{2}\d{8}$/.test(inv)) throw new Error('發票號碼要是 2 個英文字母加 8 位數字（例如 AB12345678）');
    if (e.taxFree === true) { taxable = amt; tax = 0; }
    else {
      taxable = e.taxable === '' || e.taxable == null ? Math.round(amt / (1 + LG_TAX_RATE)) : lgInt_(e.taxable);
      if (taxable < 1 || taxable > amt) throw new Error('應稅金額要大於 0，而且不能超過含稅金額');
      tax = amt - taxable;
    }
    if (!e.allowDup && lgEntries_().some(function (x) { return x.inv === inv; })) throw new Error('發票號碼 ' + inv + ' 已經記過了（如果是不同的帳，請確認後選「仍要記帳」）');
  } else if (doc !== '收據') inv = '';
  var buyer = tClean_(e.buyer, 12).trim() || lgBuyerName_(g);
  var rcp = e.receipt && e.receipt.b64 ? lgCheckReceipt_(e.receipt) : null;
  return stLocked_(function () {
    var id = stNextId_('ledger', 'L', 5);
    stPut_('ledger', 0, lgRowArr_({ id: id, d: d, type: type, cat: cat, vid: v ? v.id : '', vendor: v ? v.name : tClean_(e.vendorName, 12), amt: amt, pay: pay, paid: pay !== '月結', note: tClean_(e.note, 40), by: g.uid, at: stToday_() + ' ' + stClock_(),
      inv: inv, items: tClean_(e.items, 60), taxable: taxable, tax: tax, buyer: type === '收入' ? '' : buyer, doc: doc, file: rcp ? lgSaveReceipt_(id, d, rcp) : '', orig: type === '支出' && (doc === '統一發票' || doc === '收據') ? (e.origReceived === true && g.owner ? '已收到' : '未收到') : '' }));
    return { id: id, today: lgEntries_(today, today).map(lgPub_) };
  });
}

/* ---------- 收據照片（存進店主自己的雲端，不開公開連結）與「憑證正本」旗標 ---------- */
function lgCheckReceipt_(f) {
  var name = tClean_(f.name, 60) || 'receipt.jpg', ext = (name.split('.').pop() || '').toLowerCase();
  if (['jpg', 'jpeg', 'png', 'pdf'].indexOf(ext) < 0) throw new Error('收據只收 JPG、PNG、PDF');
  var bytes; try { bytes = Utilities.base64Decode(String(f.b64)); } catch (er) { throw new Error('收據檔案讀取失敗，請重新選擇'); }
  if (!bytes.length) throw new Error('收據檔案是空的');
  if (bytes.length > ST_FILE_MAX) throw new Error('收據檔案太大（上限 4MB），請重新拍照');
  return { ext: ext, bytes: bytes, mime: ext === 'pdf' ? 'application/pdf' : ext === 'png' ? 'image/png' : 'image/jpeg' };
}
function lgSaveReceipt_(id, d, rcp) {
  try {
    var root = subFolder_('收據', '收據'), nm = d.slice(0, 7), it = root.getFoldersByName(nm), dir = it.hasNext() ? it.next() : root.createFolder(nm);
    return dir.createFile(Utilities.newBlob(rcp.bytes, rcp.mime, id + '.' + rcp.ext)).getId();
  } catch (er) { return ''; }
}
/** 補上傳收據：店主，或記這筆帳的人本人 */
function lgAttach(id, file, key) {
  var g = lgGuard_(key, true), e = lgEntries_().filter(function (x) { return x.id === String(id); })[0];
  if (!e) throw new Error('找不到這筆帳');
  if (!g.owner && e.by !== g.uid) throw new Error('只能幫自己記的帳補收據');
  var rcp = lgCheckReceipt_(file || {}), fid = lgSaveReceipt_(e.id, e.d, rcp);
  if (!fid) throw new Error('收據存檔失敗，請稍後再試');
  e.file = fid; stPut_('ledger', e._r, lgRowArr_(e));
  return { ok: true, today: lgEntries_(stToday_(), stToday_()).map(lgPub_) };
}
/** 店主：標記「憑證正本」有沒有收到（統一發票、收據才有） */
function lgSetOriginal(id, got, key) {
  lgOwner_(key, true);
  var e = lgEntries_().filter(function (x) { return x.id === String(id); })[0];
  if (!e) throw new Error('找不到這筆帳');
  if (e.orig === '') throw new Error('這筆沒有憑證（無憑證或收入）');
  e.orig = got ? '已收到' : '未收到'; stPut_('ledger', e._r, lgRowArr_(e));
  return { ok: true, orig: e.orig };
}
/** 店主：看收據照片的連結（只有店主打得開） */
function lgReceiptUrl(id, key) {
  lgOwner_(key, false);
  var e = lgEntries_().filter(function (x) { return x.id === String(id); })[0];
  if (!e || !e.file) throw new Error('這筆沒有收據照片');
  return { url: 'https://drive.google.com/file/d/' + e.file + '/view' };
}
/* ---------- 叫貨：叫貨日（含時間與負責人）、已叫貨、提醒 ---------- */
function lgOrderDone_(day) {
  var m = {};
  stRows_('order').forEach(function (r) { if (stStr_(r['日期']) === day) m[String(r['廠商編號'])] = { at: stT_(r['時間']), by: String(r['記錄者']) }; });
  return m;
}
/** 今天要叫的廠商（含是否已叫）與昨天沒叫完的 */
function lgOrders_(today) {
  var vs = lgVendors_().filter(function (v) { return v.orderDays.length; }), dow = stDow_(today), ydow = stDow_(stAdd_(today, -1)), td = lgOrderDone_(today), yd = lgOrderDone_(stAdd_(today, -1)), out = { today: [], overdue: [] };
  var pub = function (v, done, day) { return { vid: v.id, name: v.name, time: v.time, who: v.assignee, done: !!done, at: done ? done.at : '', by: done ? done.by : '', day: day }; };
  vs.forEach(function (v) {
    if (v.orderDays.indexOf(dow) >= 0) out.today.push(pub(v, td[v.id], today));
    if (v.orderDays.indexOf(ydow) >= 0 && !yd[v.id] && !td[v.id]) out.overdue.push(pub(v, null, stAdd_(today, -1)));
  });
  return out;
}
function lgOrdersFor_(name, today) {
  var o = lgOrders_(today), mine = function (x) { return x.who === name; };
  return { today: o.today.filter(mine), overdue: o.overdue.filter(mine) };
}
function lgOrderMark_(vid, by) {
  var today = stToday_();
  return stLocked_(function () {
    if (!lgOrderDone_(today)[vid]) stPut_('order', 0, [today, vid, '已叫貨', stClock_(), tClean_(by, 12)]);
    return lgOrders_(today);
  });
}
/** 按「已叫貨」：店主或夥伴 */
function lgOrdered(vid, key) {
  var g = lgGuard_(key, true);
  var v = lgVendors_().filter(function (x) { return x.id === String(vid); })[0];
  if (!v) throw new Error('找不到這家廠商');
  return lgOrderMark_(v.id, lgBuyerName_(g));
}
/** 叫貨日提醒：叫貨日當天 9 點後，寄給店主與負責的員工；昨天沒叫完的隔天再提醒；每週一順便列出還沒收到正本的憑證。一天只寄一次 */
function lgOrderRemind_() {
  var today = stToday_();
  if (Number(stClock_().slice(0, 2)) < 9 || tGetJson_('lg_order_last', '') === today) return { sent: 0 };
  tSetJson_('lg_order_last', today);
  var o = lgOrders_(today), items = o.today.filter(function (x) { return !x.done; }).map(function (x) { return { o: x, tag: '今天要叫' }; })
    .concat(o.overdue.map(function (x) { return { o: x, tag: '昨天沒叫' }; }));
  var line = function (i) { return '【' + i.tag + '】' + i.o.name + '（' + i.o.time + ' 前' + (i.o.who ? '，負責：' + i.o.who : '') + '）'; };
  var lines = [];
  if (items.length) lines.push('叫貨提醒：\n' + items.map(line).join('\n') + '\n\n叫完請按「已叫貨」（員工入口或店務收支）。');
  if (stDow_(today) === 1) {
    var pend = lgEntries_(stAdd_(today, -120), today).filter(function (e) { return e.orig === '未收到'; });
    if (pend.length) lines.push('還沒收到憑證正本的帳 ' + pend.length + ' 筆（共 ' + pend.reduce(function (s, e) { return s + e.amt; }, 0) + ' 元），到「店務收支」→ 報表可以勾選。');
  }
  if (!lines.length) return { sent: 0, items: 0 };
  var sent = 0, to = typeof notifyTo_ === 'function' ? notifyTo_('order') : (typeof shopCfg_ === 'function' ? shopCfg_().notifyEmail : ''), done = {};
  if (to && emailOk_(to)) { mail_(to, '【叫貨提醒】' + (items.length ? items.map(function (i) { return i.o.name; }).join('、') : '憑證正本待收'), lines.join('\n\n')); sent++; done[to] = 1; }
  if (typeof notifyOn_ === 'function' && !notifyOn_('orderEmp')) return { sent: sent, items: items.length };
  stEmps_().filter(function (e) { return e.status === '在職' && emailOk_(e.email) && !done[e.email]; }).forEach(function (e) {
    var mine = items.filter(function (i) { return i.o.who === e.name; });
    if (!mine.length) return;
    mail_(e.email, '【叫貨提醒】' + mine.map(function (i) { return i.o.name; }).join('、'), e.name + ' 你好，\n\n' + mine.map(line).join('\n') + '\n\n叫完請在員工入口按「已叫貨」。', null, { brand: 'shop' }); sent++;
  });
  return { sent: sent, items: items.length };
}

/** 撤銷：店主可刪任何一筆；夥伴只能撤銷自己 10 分鐘內記的 */
function lgDelete(id, key) {
  var g = lgGuard_(key, true);
  var e = lgEntries_().filter(function (x) { return x.id === String(id); })[0];
  if (!e) return { today: lgEntries_(stToday_(), stToday_()).map(lgPub_) };
  if (!g.owner) {
    var mins = (stNow_().getTime() - Date.parse(e.at.replace(' ', 'T') + ':00+08:00')) / 60000;
    if (e.by !== g.uid || isNaN(mins) || mins > 10) throw new Error('夥伴只能撤銷自己 10 分鐘內記的帳，其他請店主處理');
  }
  stDel_('ledger', [e._r]);
  return { today: lgEntries_(stToday_(), stToday_()).map(lgPub_) };
}

/** 店主：把某家廠商（或指定幾筆）的月結標成已付款 */
function lgSettle(vendorId, ids, key) {
  lgOwner_(key, true);
  return stLocked_(function () {
    var n = 0;
    lgEntries_().forEach(function (e) {
      if (e.pay !== '月結' || e.paid) return;
      if ((ids && ids.length ? ids.indexOf(e.id) >= 0 : (vendorId ? e.vid === String(vendorId) : false))) {
        var r = stRows_('ledger').filter(function (x) { return String(x['編號']) === e.id; })[0];
        if (r) { e.paid = true; stPut_('ledger', r._r, lgRowArr_(e)); n++; }
      }
    });
    return { settled: n };
  });
}

/* ---------- 狀態與報表 ---------- */
function lgState(key, ym) {
  var g = lgGuard_(key, false), today = stToday_();
  var vendors = lgVendors_().map(lgVendorPub_);
  var recent = {};                      /* 每家廠商最近一次金額，畫面上當作快速金額 */
  lgEntries_(stAdd_(today, -120), today).sort(function (a, b) { return a.d < b.d ? -1 : 1; }).forEach(function (e) { if (e.vid) recent[e.vid] = e.amt; });
  var buyers = ['店主'], seen = { '店主': 1 };
  try {
    if (typeof saas_ === 'function' && saas_()) cRows_('partners').forEach(function (r) { if (String(r['店家編號']) === CTX.shopId && r['狀態'] === '使用中') { var n = String(r['名稱']).slice(0, 12); if (!seen[n]) { seen[n] = 1; buyers.push(n); } } });
    stEmps_().forEach(function (x) { if (x.status === '在職' && !seen[x.name]) { seen[x.name] = 1; buyers.push(x.name); } });
  } catch (e) {}
  var itemsBy = {};
  lgEntries_(stAdd_(today, -120), today).sort(function (a, b) { return a.d < b.d ? 1 : -1; }).forEach(function (e) {
    if (!e.vid || !e.items) return; var l = itemsBy[e.vid] = itemsBy[e.vid] || []; if (l.indexOf(e.items) < 0 && l.length < 5) l.push(e.items);
  });
  var out = { owner: g.owner, today: today, buyers: buyers, me: lgBuyerName_(g), docs: LG_DOCS, itemsBy: itemsBy, taxRate: LG_TAX_RATE, vendors: vendors, recent: recent, outCats: LG_OUT_CATS, inCats: LG_IN_CATS, pays: LG_PAYS, uid: g.uid,
    entries: lgEntries_(today, today).map(lgPub_), maxAmount: LG_MAX_AMOUNT };
  out.todaySum = lgSum_(lgEntries_(today, today));
  out.orders = lgOrders_(today); out.assignees = buyers.filter(function (x) { return x !== '店主'; });
  if (g.owner) out.report = lgReport_(ym);
  return out;
}
function lgReport_(ym) {
  var today = stToday_(), m = /^\d{4}-\d{2}$/.test(String(ym || '')) ? ym : today.slice(0, 7);
  var from = m + '-01', nx = new Date(Date.UTC(Number(m.slice(0, 4)), Number(m.slice(5, 7)), 1)), to = stAdd_(nx.toISOString().slice(0, 10), -1);
  var list = lgEntries_(from, to), byCat = {}, byVendor = {}, byDay = {}, byBuyer = {}, inv = { n: 0, taxable: 0, tax: 0, total: 0 };
  list.forEach(function (e) {
    if (e.type === '支出') {
      byCat[e.cat] = (byCat[e.cat] || 0) + e.amt;
      var vn = e.vendor || '（無廠商）'; byVendor[vn] = (byVendor[vn] || 0) + e.amt;
      var bn = e.buyer || '（未填）'; byBuyer[bn] = (byBuyer[bn] || 0) + e.amt;
      if (e.doc === '統一發票') { inv.n++; inv.taxable += e.taxable || 0; inv.tax += e.tax || 0; inv.total += e.amt; }
    }
    var o = byDay[e.d] = byDay[e.d] || { inn: 0, out: 0 }; if (e.type === '收入') o.inn += e.amt; else o.out += e.amt;
  });
  var unpaid = {};
  lgEntries_().forEach(function (e) { if (e.pay === '月結' && !e.paid && e.type === '支出') { var k = e.vid || e.vendor; var o = unpaid[k] = unpaid[k] || { vid: e.vid, name: e.vendor || '（無廠商）', amt: 0, n: 0 }; o.amt += e.amt; o.n++; } });
  var arr = function (o) { return Object.keys(o).map(function (k) { return { name: k, amt: o[k] }; }).sort(function (a, b) { return b.amt - a.amt; }); };
  var origPend = lgEntries_().filter(function (e) { return e.orig === '未收到'; }).sort(function (a, b) { return a.d < b.d ? -1 : 1; }).map(lgPub_);
  return { month: m, from: from, to: to, origPending: origPend, sum: lgSum_(list), byCat: arr(byCat), byVendor: arr(byVendor), byBuyer: arr(byBuyer), invoice: inv,
    days: Object.keys(byDay).sort().map(function (d) { return { d: d, inn: byDay[d].inn, out: byDay[d].out }; }),
    unpaid: Object.keys(unpaid).map(function (k) { return unpaid[k]; }).sort(function (a, b) { return b.amt - a.amt; }),
    entries: list.sort(function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : a.id < b.id ? 1 : -1; }).map(lgPub_) };
}
function lgReport(ym, key) { lgOwner_(key, false); return lgReport_(ym); }

/* ---------- 頁面 ---------- */
function ledgerPage_(key) {
  lgGuard_(key, false);
  var t = HtmlService.createTemplateFromFile('Ledger'), base = tWebUrl_();
  t.boot = tJs_({ token: key, brand: typeof brand_ === 'function' ? brand_() : {}, home: base ? base + '?p=home&' + (typeof saas_ === 'function' && saas_() ? 't=' : 'staff=') + key : '' });
  return t.evaluate().setTitle('店務收支')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
