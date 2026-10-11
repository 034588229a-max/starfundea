/**
 * 店家工具（ToolsServer.gs：指令碼檔名不能跟 HTML 的 Tools 相同）
 * 網址：…/exec?p=tools&staff=<STAFF_KEY>
 * 功能：① Logo 上傳（解析度把關＋底色連動）② 網址產生 QR
 *       ③ 桌號 QR 海報批次輸出 PDF ④ 公告海報＋顧客頁公告
 * 這個檔案是新增的，不會改到原本的菜單工具；只需要在 Code.gs 的 doGet 加一段分流（見 docs）。
 */

// ===== Logo 最低標準（前端、後端共用同一組數字）=====
var T_LOGO_RULE = {
  minLong: 800,          // 長邊低於 800px → 退件
  minShort: 300,         // 短邊低於 300px → 退件
  recLong: 1500,         // 長邊低於 1500px → 可上傳，但提醒換高解析版本
  maxRatio: 4,           // 長寬比超過 4:1 → 退件（太細長，放進版面會變很小）
  maxBytes: 5 * 1024 * 1024,   // 原始檔上限 5MB
  saveLong: 2000,        // 存檔時長邊最多縮到 2000px（不放大）
  types: ['image/png', 'image/jpeg', 'image/webp']
};

var T_FOLDER_NAME = '弘林店家工具';
var T_NOTICE_SHEET = '公告';
var T_NOTICE_HEAD = ['單號', '建立時間', '更新時間', '標題', '開始日', '結束日', '顧客頁顯示', '內容', 'PDF 連結', '類別'];

// ===== 公告類別（前端、後端共用）=====
// key：程式用代碼；name：顯示名稱；color：標籤顏色；pri：顧客頁排序（數字小的排前面，影響營業的優先）
var T_NOTICE_CATS = [
  { key: 'closed',   name: '臨時公休',     color: '#C0392B', pri: 1 },
  { key: 'vacation', name: '休假／店休',   color: '#6A4C93', pri: 2 },
  { key: 'hours',    name: '營業時間調整', color: '#1B4F8A', pri: 3 },
  { key: 'promo',    name: '活動／優惠',   color: '#B8336A', pri: 5 },
  { key: 'festival', name: '節慶祝福',     color: '#00897B', pri: 6 },
  { key: 'newitem',  name: '新品上市',     color: '#E8762A', pri: 7 },
  { key: 'hiring',   name: '徵才',         color: '#2E7D4F', pri: 8 },
  { key: 'general',  name: '一般公告',     color: '#16233A', pri: 9 }
];
function tCat_(k) {
  for (var i = 0; i < T_NOTICE_CATS.length; i++) {
    if (T_NOTICE_CATS[i].key === k || T_NOTICE_CATS[i].name === k) return T_NOTICE_CATS[i];
  }
  return T_NOTICE_CATS[T_NOTICE_CATS.length - 1];
}

// ---------- 共用小工具 ----------
function tProps_() { return typeof props_ === 'function' ? props_() : PropertiesService.getScriptProperties(); }
function tGetJson_(k, dflt) {
  var v = tProps_().getProperty(k);
  if (!v) return dflt;
  try { return JSON.parse(v); } catch (e) { return dflt; }
}
function tSetJson_(k, obj) { tProps_().setProperty(k, JSON.stringify(obj)); }
function tJs_(obj) {
  var ls = String.fromCharCode(0x2028), ps = String.fromCharCode(0x2029);
  return JSON.stringify(obj).replace(/</g, '\\u003c').replace(/\//g, '\\/')
    .split(ls).join('\\u2028').split(ps).join('\\u2029');
}
function tGuardRead_(key) {
  if (typeof guardRead_ === 'function') return guardRead_(key);
  return tGuard_(key);
}
function tGuard_(key) {
  if (typeof guard_ === 'function') return guard_(key);
  if (typeof STAFF_KEY === 'undefined' || key !== STAFF_KEY) throw new Error('沒有權限（夥伴網址不正確）');
}
function tClean_(s, max) {
  return String(s == null ? '' : s).replace(/[<>]/g, '').slice(0, max || 200);
}
function tUrlOk_(u) {
  u = String(u || '').trim();
  return /^https?:\/\/[^\s]+\.[^\s]+$/i.test(u) && u.length <= 500 ? u : '';
}
function tWebUrl_() { return typeof WEB_APP_URL !== 'undefined' ? WEB_APP_URL : ''; }
function tFolder_() {
  if (typeof saas_ === 'function' && saas_()) return subFolder_(T_FOLDER_NAME, '店家工具');
  var id = tProps_().getProperty('t_folder');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) {} }
  var it = DriveApp.getFoldersByName(T_FOLDER_NAME);
  var f = it.hasNext() ? it.next() : DriveApp.createFolder(T_FOLDER_NAME);
  tProps_().setProperty('t_folder', f.getId());
  return f;
}
function tSs_() {
  if (typeof saas_ === 'function' && saas_()) return book_();
  var id = tProps_().getProperty('ssId');
  return id ? SpreadsheetApp.openById(id) : SpreadsheetApp.getActiveSpreadsheet();
}

// ---------- 預設值 ----------
function tDefaultShop_() {
  var links = typeof LINKS !== 'undefined' ? LINKS : {};
  var web = tWebUrl_();
  return {
    name: typeof shopCfg_ === 'function' ? shopCfg_().name : '弘林早午餐',
    tagline: typeof shopCfg_ === 'function' ? shopCfg_().tagline : '中壢 25 年在地好味道',
    primary: typeof shopCfg_ === 'function' ? shopCfg_().primary : '#1B4F8A',
    accent: typeof shopCfg_ === 'function' ? shopCfg_().accent : '#E8762A',
    chips: '會員累點折抵；支援 LINE Pay·街口支付',
    hours: typeof saas_ === 'function' && saas_() ? (shopCfg_().hours || '') : '06:00–13:00',
    knockUrl: web ? web + (typeof saas_ === 'function' && saas_() ? '?s=' + CTX.shopId + '&p=knock' : '?p=knock') : '',
    lineUrl: (typeof shopCfg_ === 'function' ? shopCfg_().lineUrl : links.line) || ''
  };
}

// ---------- 頁面 ----------
/** 由 Code.gs 的 doGet 呼叫（鑰匙已在 doGet 檢查過，這裡再確認一次）。 */
function toolsPage_(e) {
  var key = (e && e.parameter && (e.parameter.t || e.parameter.staff)) || '';
  tGuardRead_(key);
  var t = HtmlService.createTemplateFromFile('Tools');
  var st = tState_(key);
  st.wm = (typeof saas_ === 'function' && saas_() && typeof CTX !== 'undefined' && CTX.lic && CTX.lic.watermark) ? 1 : 0;   /* 試用版：所有輸出加浮水印 */
  if (e && e.parameter && e.parameter.hiring) st.openHiring = true;
  if (e && e.parameter && ['hand', 'cal', 'notice', 'table', 'wifi', 'card', 'rich', 'logo'].indexOf(e.parameter.tab) >= 0) st.openTab = e.parameter.tab;
  t.boot = tJs_(st);
  t.key = tJs_(key);
  return t.evaluate()
    .setTitle('店家工具')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function tMenuUrl_(key) {
  if (!tWebUrl_()) return '';
  if (typeof saas_ === 'function' && saas_()) return tWebUrl_() + '?t=' + key;
  return typeof STAFF_KEY !== 'undefined' ? tWebUrl_() + '?staff=' + STAFF_KEY : '';
}
function tStaffUrl_(key) {
  if (!tWebUrl_() || typeof staffPage_ !== 'function') return '';
  if (typeof saas_ === 'function' && saas_()) return CTX.role === 'owner' ? tWebUrl_() + '?p=staff&t=' + key : '';
  return typeof STAFF_KEY !== 'undefined' ? tWebUrl_() + '?p=staff&staff=' + STAFF_KEY : '';
}
function tState_(key) {
  var shop = tGetJson_('t_shop', null) || {};
  var d = tDefaultShop_();
  Object.keys(d).forEach(function (k) { if (shop[k] == null || shop[k] === '') shop[k] = d[k]; });
  return {
    shop: shop,
    logo: tGetJson_('t_logo', null),
    tables: tGetJson_('t_tables', []),
    tableOpt: tGetJson_('t_tableOpt', {}),
    notices: tListNotices_(30),
    wifi: tGetJson_('t_wifi', null),
    card: tGetJson_('t_card', null),
    cardInfo: tCardInfo_(),
    cats: T_NOTICE_CATS,
    rule: T_LOGO_RULE,
    openDays: tOpenDays_(),
    closures: tListClosures_(),
    handover: tListHandover_(),
    summary: tShiftSummary_(),
    menuUrl: tMenuUrl_(key),
    staffUrl: tStaffUrl_(key),
    applyUrl: typeof stApplyUrl_ === 'function' ? stApplyUrl_() : '',
    hire: typeof stHire_ === 'function' ? stHire_() : null
  };
}

/** 重新讀取全部設定（需要鑰匙）。 */
function tGetState(key) { tGuardRead_(key); return tState_(key); }

// ---------- ① Logo ----------
/** 讀 Logo 圖片（data URL）。沒上傳過就用原本 LOGO_FILE_ID 的吉祥物圖。 */
function tGetLogo(key) {
  tGuardRead_(key);
  var meta = tGetJson_('t_logo', null), id = meta && meta.fileId;
  if (!id && typeof LOGO_FILE_ID !== 'undefined') id = LOGO_FILE_ID;
  if (!id) return null;
  try {
    var b = DriveApp.getFileById(id).getBlob();
    return { dataUrl: 'data:' + b.getContentType() + ';base64,' + Utilities.base64Encode(b.getBytes()), meta: meta, fallback: !(meta && meta.fileId) };
  } catch (err) {
    return null;
  }
}

/** 讀出 PNG / JPEG 的實際寬高（伺服器端再把關一次，不只相信前端）。 */
function tImageSize_(bytes) {
  function u8(i) { return bytes[i] & 0xFF; }
  if (u8(0) === 0x89 && u8(1) === 0x50 && u8(2) === 0x4E && u8(3) === 0x47) {
    return { type: 'image/png', w: (u8(16) << 24 | u8(17) << 16 | u8(18) << 8 | u8(19)) >>> 0, h: (u8(20) << 24 | u8(21) << 16 | u8(22) << 8 | u8(23)) >>> 0 };
  }
  if (u8(0) === 0xFF && u8(1) === 0xD8) {
    var i = 2;
    while (i + 9 < bytes.length) {
      if (u8(i) !== 0xFF) { i++; continue; }
      var mk = u8(i + 1), len = u8(i + 2) << 8 | u8(i + 3);
      if (mk >= 0xC0 && mk <= 0xCF && mk !== 0xC4 && mk !== 0xC8 && mk !== 0xCC) {
        return { type: 'image/jpeg', h: u8(i + 5) << 8 | u8(i + 6), w: u8(i + 7) << 8 | u8(i + 8) };
      }
      i += 2 + len;
    }
  }
  return null;
}

/** 依標準檢查尺寸。回傳 {ok, level:'ok'|'warn'|'reject', msgs:[]}；前端也用同一套邏輯。 */
function tCheckLogoSize_(w, h, origW, origH) {
  var R = T_LOGO_RULE, msgs = [], level = 'ok';
  var ow = origW || w, oh = origH || h;
  var L = Math.max(ow, oh), S = Math.min(ow, oh);
  if (L < R.minLong) { level = 'reject'; msgs.push('長邊只有 ' + L + 'px，最低需要 ' + R.minLong + 'px'); }
  if (S < R.minShort) { level = 'reject'; msgs.push('短邊只有 ' + S + 'px，最低需要 ' + R.minShort + 'px'); }
  if (S > 0 && L / S > R.maxRatio) { level = 'reject'; msgs.push('長寬比 ' + (L / S).toFixed(1) + ':1 太細長（上限 ' + R.maxRatio + ':1）'); }
  if (level !== 'reject' && L < R.recLong) { level = 'warn'; msgs.push('長邊 ' + L + 'px 可以使用，建議 ' + R.recLong + 'px 以上印刷更清楚'); }
  return { ok: level !== 'reject', level: level, msgs: msgs };
}

/**
 * 上傳 Logo。
 * f = {b64, origW, origH, origType, origBytes, name, bgMode:'transparent'|'solid'|'mixed', bg:'#RRGGBB'|null, bgManual:'#RRGGBB'|''}
 */
function tSaveLogo(f, key) {
  tGuard_(key);
  var R = T_LOGO_RULE;
  if (!f || !f.b64) throw new Error('沒有收到圖片');
  if (R.types.indexOf(f.origType) < 0) throw new Error('格式不支援，請用 PNG、JPG 或 WebP');
  if (Number(f.origBytes) > R.maxBytes) throw new Error('原始檔超過 5MB，請壓縮後再上傳');
  var bytes = Utilities.base64Decode(String(f.b64));
  var sz = tImageSize_(bytes);
  if (!sz) throw new Error('看不懂這張圖片，請改存成 PNG 再上傳');
  // 存檔版本是原圖等比縮小（長邊最多 2000），所以原圖尺寸要以存檔尺寸換算驗證，避免前端被竄改
  var L = Math.max(sz.w, sz.h);
  var oL = Math.max(Number(f.origW) || 0, Number(f.origH) || 0);
  if (L < R.saveLong && oL > L + 2) throw new Error('圖片尺寸資料不一致，請重新選擇檔案');
  var chk = tCheckLogoSize_(sz.w, sz.h, Number(f.origW) || sz.w, Number(f.origH) || sz.h);
  if (!chk.ok) throw new Error('Logo 解析度不符合標準：' + chk.msgs.join('；'));

  var hex = /^#[0-9A-F]{6}$/i;
  var meta = {
    w: sz.w, h: sz.h, origW: Number(f.origW) || sz.w, origH: Number(f.origH) || sz.h,
    type: sz.type, name: tClean_(f.name, 80),
    bgMode: ['transparent', 'solid', 'mixed'].indexOf(f.bgMode) >= 0 ? f.bgMode : 'transparent',
    bg: hex.test(f.bg || '') ? f.bg.toUpperCase() : null,
    bgManual: hex.test(f.bgManual || '') ? f.bgManual.toUpperCase() : '',
    level: chk.level, updatedAt: new Date().toISOString()
  };
  var old = tGetJson_('t_logo', null);
  var stamp = Date.now();
  var file = tFolder_().createFile(Utilities.newBlob(bytes, sz.type, 'logo_' + stamp + (sz.type === 'image/png' ? '.png' : '.jpg')));
  meta.fileId = file.getId();
  // 網頁用小圖（長邊 480 以內、70KB 以內）：菜單工具與顧客頁直接嵌入，不用每次讀大圖
  if (f.webB64) {
    var wb = Utilities.base64Decode(String(f.webB64)), ws = tImageSize_(wb);
    if (ws && wb.length <= 70000 && Math.max(ws.w, ws.h) <= 480) {
      meta.webId = tFolder_().createFile(Utilities.newBlob(wb, ws.type, 'logo_web_' + stamp + (ws.type === 'image/png' ? '.png' : '.jpg'))).getId();
    }
  }
  tSetJson_('t_logo', meta);
  [old && old.fileId, old && old.webId].forEach(function (id) { if (id) { try { DriveApp.getFileById(id).setTrashed(true); } catch (e) {} } });
  tClearLogoCache_();
  return { meta: meta, check: chk };
}

function tClearLogoCache_() { try { CacheService.getScriptCache().remove(typeof ck_ === 'function' ? ck_('logo') : 'logo'); } catch (e) {} }

/** 只改底色設定（自動／手動），不用重新上傳。 */
function tSetLogoBg(bgManual, key) {
  tGuard_(key);
  var meta = tGetJson_('t_logo', null);
  if (!meta) throw new Error('還沒有上傳 Logo');
  meta.bgManual = /^#[0-9A-F]{6}$/i.test(bgManual || '') ? bgManual.toUpperCase() : '';
  tSetJson_('t_logo', meta);
  tClearLogoCache_();
  return meta;
}

/** 店家資料：名稱、標語、主色、強調色、海報底部標籤、敲敲老闆／LINE 網址。 */
function tSaveShop(s, key) {
  tGuard_(key);
  return tShopSave_(s);
}
/** 同上，但不檢查權限（給種子資料用，驗證規則完全一樣）。 */
function tShopSave_(s) {
  s = s || {};
  var hex = /^#[0-9A-F]{6}$/i, d = tDefaultShop_();
  var out = {
    name: tClean_(s.name, 30) || d.name,
    tagline: tClean_(s.tagline, 40),
    hours: tClean_(s.hours, 40),
    primary: hex.test(s.primary) ? s.primary.toUpperCase() : d.primary,
    accent: hex.test(s.accent) ? s.accent.toUpperCase() : d.accent,
    chips: tClean_(s.chips, 80),
    knockUrl: tUrlOk_(s.knockUrl),
    lineUrl: tUrlOk_(s.lineUrl)
  };
  tSetJson_('t_shop', out);
  return out;
}

// ---------- ③ 桌號 QR ----------
/** 存桌號清單 list = [{type:'table'|'wait'|'take', name, url}] 與版面選項。 */
function tSaveTables(list, opt, key) {
  tGuard_(key);
  return tTablesSave_(list, opt);
}
/** 同上，但不檢查權限（給種子資料／內部流程用，驗證規則完全一樣）。 */
function tTablesSave_(list, opt) {
  if (!Array.isArray(list)) throw new Error('資料格式不對');
  if (list.length > 200) throw new Error('一次最多 200 筆');
  var seen = {}, out = [], errs = [];
  list.forEach(function (r, i) {
    var name = tClean_(r.name, 20), url = tUrlOk_(r.url);
    if (!name && !url) return;
    if (!url) { errs.push('第 ' + (i + 1) + ' 列網址不正確'); return; }
    if (seen[url]) errs.push('「' + name + '」和「' + seen[url] + '」網址重複');
    seen[url] = name;
    out.push({ type: ['table', 'wait', 'take'].indexOf(r.type) >= 0 ? r.type : 'table', name: name, url: url });
  });
  if (errs.length) throw new Error(errs.join('\n'));
  tSetJson_('t_tables', out);
  if (opt) tSetJson_('t_tableOpt', { layout: tClean_(opt.layout, 10), headline: opt.headline || {} });
  return out;
}

// ---------- Wi-Fi 卡 ----------
/** w = {ssid, pass, enc:'WPA'|'WEP'|'nopass', hidden, title, note, showPass, layout} */
function tSaveWifi(w, key) {
  tGuard_(key);
  return tWifiSave_(w);
}
/** 同上，但不檢查權限（給種子資料用）。 */
function tWifiSave_(w) {
  var ssid = String(w.ssid || '').trim(), pass = String(w.pass || '');
  var enc = ['WPA', 'WEP', 'nopass'].indexOf(w.enc) >= 0 ? w.enc : 'WPA';
  if (!ssid) throw new Error('請填 Wi-Fi 名稱');
  if (Utilities.newBlob(ssid).getBytes().length > 32) throw new Error('Wi-Fi 名稱太長（最多 32 位元組）');
  if (enc === 'WPA' && (pass.length < 8 || pass.length > 63)) throw new Error('WPA 密碼要 8～63 個字');
  if (enc === 'WEP' && [5, 10, 13, 26].indexOf(pass.length) < 0) throw new Error('WEP 密碼長度要是 5、10、13 或 26');
  var out = {
    ssid: ssid, pass: enc === 'nopass' ? '' : pass, enc: enc, hidden: w.hidden === true,
    title: tClean_(w.title, 20), note: tClean_(w.note, 60), showPass: w.showPass !== false,
    layout: ['a6x4', 'a5x2', 'a4'].indexOf(w.layout) >= 0 ? w.layout : 'a6x4'
  };
  tSetJson_('t_wifi', out);
  return out;
}

// ---------- 名片 ----------
/** 名片預設帶入的店家資料（地址、電話、營業時間、LINE ID 來自「店家設定」）。 */
function tCardInfo_() {
  var c = typeof shopCfg_ === 'function' ? shopCfg_() : {}, web = tWebUrl_(), saas = typeof saas_ === 'function' && saas_();
  var phone = c.phone || '';
  if (saas) phone = String(phone).replace(/（.*$/, '');
  return {
    phone: String(phone).replace(/（.*$/, ''), address: c.address || '', hours: c.hours || '', lineId: c.lineId || '',
    menuUrl: web ? web + (saas ? '?s=' + CTX.shopId + '&p=menu' : '?p=menu') : '',
    mapUrl: c.mapUrl || '',
    shopUrl: web ? web + (saas ? '?s=' + CTX.shopId : '') : '',
    preUrl: web ? web + (saas ? '?s=' + CTX.shopId + '&p=pre' : '?p=pre') : ''
  };
}

/** 名片設定：tpl 範本、pal 配色（shop＝跟店家配色）、cp／ca 主色與強調色，其餘為文字欄位與 QR 目標 */
function tSaveCard(c, key) {
  tGuard_(key);
  c = c || {};
  var hex = function (v) { return /^#[0-9a-fA-F]{6}$/.test(String(v || '')) ? String(v).toUpperCase() : ''; };
  var lines = String(c.backLines || '').split(/\r?\n/).map(function (x) { return tClean_(x, 30); }).filter(String).slice(0, 4);
  var out = {
    tpl: ['side', 'top', 'bar', 'solid'].indexOf(c.tpl) >= 0 ? c.tpl : 'side',
    pal: tClean_(c.pal, 12) || 'shop', cp: hex(c.cp), ca: hex(c.ca),
    name: tClean_(c.name, 30), tagline: tClean_(c.tagline, 40), person: tClean_(c.person, 20), title: tClean_(c.title, 30),
    phone: tClean_(c.phone, 40), address: tClean_(c.address, 60), hours: tClean_(c.hours, 50), lineId: tClean_(c.lineId, 30),
    email: tClean_(c.email, 60), web: tClean_(c.web, 60),
    payments: tClean_(c.payments, 40), sides: c.sides === 'front' ? 'front' : 'double',
    qr: ['menu', 'line', 'knock', 'map', 'custom'].indexOf(c.qr) >= 0 ? c.qr : 'line',
    qrUrl: tUrlOk_(c.qrUrl), qrCap: tClean_(c.qrCap, 16), qrFront: c.qrFront !== false,
    backTitle: tClean_(c.backTitle, 24), backLines: lines.join('\n'),
    sheets: Math.min(20, Math.max(1, parseInt(c.sheets, 10) || 1))
  };
  if (out.qr === 'custom' && !out.qrUrl) throw new Error('自訂網址不正確（要以 http 或 https 開頭）');
  tSetJson_('t_card', out);
  return out;
}

// ---------- ④ 公告 ----------
function tNoticeSheet_() {
  var ss = tSs_(), sh = ss.getSheetByName(T_NOTICE_SHEET);
  if (!sh) {
    sh = ss.insertSheet(T_NOTICE_SHEET);
    sh.getRange(1, 1, 1, T_NOTICE_HEAD.length).setValues([T_NOTICE_HEAD]).setFontWeight('bold');
    sh.setFrozenRows(1);
    sh.setColumnWidth(8, 300);
  } else if (sh.getRange(1, 10).getValue() !== '類別') {
    sh.getRange(1, 10).setValue('類別');
  }
  return sh;
}
function tListNotices_(limit) {
  var sh;
  try { sh = tNoticeSheet_(); } catch (e) { return []; }
  var n = sh.getLastRow() - 1;
  if (n < 1) return [];
  var rows = sh.getRange(2, 1, n, T_NOTICE_HEAD.length).getValues();
  var out = rows.map(function (r) {
    var c = {};
    try { c = JSON.parse(r[7] || '{}'); } catch (e) {}
    var cat = tCat_(c.cat || r[9] || 'general');
    return { id: String(r[0]), cat: cat.key, created: tDate_(r[1]), updated: tDate_(r[2]), title: String(r[3]), start: tDay_(r[4]), end: tDay_(r[5]), show: r[6] === true, content: c, pdf: String(r[8] || '') };
  }).filter(function (x) { return x.id; });
  out.reverse();
  return out.slice(0, limit || 30);
}
function tDate_(v) { return v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy/MM/dd HH:mm') : String(v || ''); }
function tDay_(v) { return v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd') : String(v || ''); }

/** 新增或更新公告。n = {id?, title, start, end, show, content:{…海報欄位}} */
function tSaveNotice(n, key) {
  tGuard_(key);
  return tNoticeSave_(n);
}
/** 同上，但不檢查權限（給種子資料用）。 */
function tNoticeSave_(n) {
  var sh = tNoticeSheet_(), now = new Date();
  var day = /^\d{4}-\d{2}-\d{2}$/;
  var cat = tCat_((n.content && n.content.cat) || n.cat || 'general');
  if (n.content) n.content.cat = cat.key;
  var content = JSON.stringify(n.content || {});
  if (content.length > 40000) throw new Error('公告內容太長');
  var row = [
    '', now, now, tClean_(n.title, 60) || '公告',
    day.test(n.start || '') ? n.start : '', day.test(n.end || '') ? n.end : '',
    n.show === true, content.replace(/[<>]/g, ''), tUrlOk_(n.pdf), cat.name
  ];
  var lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var last = sh.getLastRow(), ids = last > 1 ? sh.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return String(r[0]); }) : [];
    var at = n.id ? ids.indexOf(String(n.id)) : -1;
    if (at >= 0) {
      var r = at + 2;
      row[0] = String(n.id); row[1] = sh.getRange(r, 2).getValue();
      if (!row[8]) row[8] = sh.getRange(r, 9).getValue();
      sh.getRange(r, 1, 1, row.length).setValues([row]);
    } else {
      var p = tProps_(), k = 'seq_N' + Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyMMdd');
      var seq = Number(p.getProperty(k) || 0) + 1; p.setProperty(k, String(seq));
      row[0] = 'N' + k.slice(5) + ('0' + seq).slice(-2);
      sh.appendRow(row);
    }
  } finally { lock.releaseLock(); }
  sh.getRange(2, 7, Math.max(1, sh.getLastRow() - 1), 1).insertCheckboxes();
  return { id: row[0], notices: tListNotices_(30) };
}

function tDeleteNotice(id, key) {
  tGuard_(key);
  var sh = tNoticeSheet_(), last = sh.getLastRow();
  if (last < 2) return tListNotices_(30);
  var ids = sh.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return String(r[0]); });
  var at = ids.indexOf(String(id));
  if (at >= 0) sh.deleteRow(at + 2);
  return tListNotices_(30);
}

/**
 * 顧客頁用（不需鑰匙）：目前有效、勾選「顧客頁顯示」的公告，只回傳要顯示的文字。
 * Customer.html 之後可以呼叫 google.script.run.tGetNotices() 顯示橫幅。
 */
function tGetNotices(sid) {
  if (typeof saas_ === 'function' && saas_() && sid) useShop_(sid);
  var today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  return tListNotices_(50).filter(function (x) {
    return x.show && (!x.start || x.start <= today) && (!x.end || x.end >= today);
  }).map(function (x) {
    var c = x.content || {}, cat = tCat_(x.cat);
    return { id: x.id, cat: cat.key, catName: cat.name, color: cat.color, pri: cat.pri, tag: c.tag || cat.name, title: x.title, text: c.lead || '', big: c.hiBig || '', end: x.end };
  }).sort(function (a, b) { return a.pri - b.pri; });
}

// ---------- PDF 存檔（桌號海報、公告海報共用）----------
/** kind = 'table' | 'notice'；noticeId 有值時把 PDF 連結寫回公告列。 */
function tSavePdf(b64, filename, kind, noticeId, key) {
  tGuard_(key);
  var name = tClean_(filename, 80).replace(/[\\\/:*?"|]/g, '_') || '海報';
  if (!/\.pdf$/i.test(name)) name += '.pdf';
  var blob = Utilities.newBlob(Utilities.base64Decode(String(b64)), 'application/pdf', name);
  var file = tFolder_().createFile(blob);
  try { file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch (e) {}
  var id = file.getId();
  var out = { fileId: id, url: file.getUrl(), dl: 'https://drive.google.com/uc?export=download&id=' + id };
  if (kind === 'notice' && noticeId) {
    var sh = tNoticeSheet_(), last = sh.getLastRow();
    if (last > 1) {
      var ids = sh.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return String(r[0]); });
      var at = ids.indexOf(String(noticeId));
      if (at >= 0) sh.getRange(at + 2, 9).setValue(out.url);
    }
  }
  return out;
}

/** 寄信：有 Mail.gs 就用品牌版型（單店模式或單頁測試沒有時，照舊寄純文字） */
function tMail_(to, subject, body, x) {
  if (typeof mailSend_ === 'function') return mailSend_(to, subject, body, null, x);
  MailApp.sendEmail({ to: to, subject: subject, body: body });
}
/** 寄海報 PDF（沿用原本 emailPdf 的做法；只寄工具資料夾內的檔案）。 */
function tEmailPdf(fileId, to, key) {
  tGuard_(key);
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(to || ''))) throw new Error('Email 格式不對');
  var f = DriveApp.getFileById(fileId), inFolder = false, it = f.getParents(), fid = tFolder_().getId();
  while (it.hasNext()) if (it.next().getId() === fid) inFolder = true;
  if (!inFolder) throw new Error('只能寄店家工具資料夾內的檔案');
  if (typeof mailSend_ === 'function') mailSend_(to, f.getName(), '附件是 ' + f.getName() + '，可直接列印。', null, { brand: 'shop', attachments: [f.getBlob()] });
  else MailApp.sendEmail({ to: to, subject: f.getName(), body: '附件是 ' + f.getName() + '，可直接列印。', attachments: [f.getBlob()] });
  return true;
}

// ======================================================================
// 店休行事曆：每週固定公休（Code.gs 的 OPEN_DAYS）＋特別店休＋特別營業
// ======================================================================
var T_TZ = 'Asia/Taipei';
var T_CLOSE_SHEET = '店休行事曆';
var T_CLOSE_HEAD = ['編號', '開始日', '結束日', '類型', '原因', '顧客頁顯示', '建立時間'];

function tOpenDays_() { return typeof shopCfg_ === 'function' ? shopCfg_().openDays : (typeof OPEN_DAYS !== 'undefined' ? OPEN_DAYS : [0, 1, 2, 3, 4, 5, 6]); }
function tToday_() { return Utilities.formatDate(new Date(), T_TZ, 'yyyy-MM-dd'); }
function tAddDays_(day, n) {
  var d = new Date(day + 'T00:00:00+08:00');
  d.setTime(d.getTime() + n * 86400000);
  return Utilities.formatDate(d, T_TZ, 'yyyy-MM-dd');
}
function tWeekday_(day) { return new Date(day + 'T00:00:00Z').getUTCDay(); }
function tSeq_(prefix) {
  var p = tProps_(), k = 'seq_' + prefix + Utilities.formatDate(new Date(), T_TZ, 'yyMMdd');
  var n = Number(p.getProperty(k) || 0) + 1; p.setProperty(k, String(n));
  return prefix + k.slice(4 + prefix.length) + ('0' + n).slice(-2);
}
function tSheet_(name, head) {
  var ss = tSs_(), sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.getRange(1, 1, 1, head.length).setValues([head]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}
function tRows_(sh, ncol) {
  var n = sh.getLastRow() - 1;
  return n < 1 ? [] : sh.getRange(2, 1, n, ncol).getValues();
}
function tFindRow_(sh, id) {
  var last = sh.getLastRow();
  if (last < 2) return -1;
  var ids = sh.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return String(r[0]); });
  var at = ids.indexOf(String(id));
  return at < 0 ? -1 : at + 2;
}

function tListClosures_() {
  var sh;
  try { sh = tSheet_(T_CLOSE_SHEET, T_CLOSE_HEAD); } catch (e) { return []; }
  return tRows_(sh, T_CLOSE_HEAD.length).filter(function (r) { return r[0]; }).map(function (r) {
    return { id: String(r[0]), s: tDay_(r[1]), e: tDay_(r[2]), type: r[3] === '特別營業' ? 'open' : 'closed', reason: String(r[4] || ''), show: r[5] === true };
  }).sort(function (a, b) { return a.s < b.s ? -1 : a.s > b.s ? 1 : 0; });
}

/** 顧客頁用（不需鑰匙）：今天以後的店休／特別營業。show=false 的不顯示橫幅，但預訂一樣會擋。 */
function tPublicClosures_() {
  var t = tToday_();
  return tListClosures_().filter(function (c) { return c.e >= t; }).map(function (c) {
    return { s: c.s, e: c.e, type: c.type, reason: c.reason, show: c.show };
  });
}

/** 某一天有沒有營業：特別營業 > 特別店休 > 每週公休。day = 'yyyy-MM-dd' */
function tClosedInfo_(day) {
  var list = tListClosures_();
  for (var i = 0; i < list.length; i++) {
    var c = list[i];
    if (c.type === 'open' && c.s <= day && c.e >= day) return { closed: false, reason: c.reason || '特別營業', type: 'open' };
  }
  for (var j = 0; j < list.length; j++) {
    var d = list[j];
    if (d.type === 'closed' && d.s <= day && d.e >= day) return { closed: true, reason: d.reason || '店休', type: 'closed' };
  }
  var open = tOpenDays_().indexOf(tWeekday_(day)) >= 0;
  return { closed: !open, reason: open ? '' : '每週公休', type: open ? '' : 'weekly' };
}

/** 新增或修改店休／特別營業。c = {id?, s, e, type:'closed'|'open', reason, show} */
function tSaveClosure(c, key) {
  tGuard_(key);
  return tClosureSave_(c);
}
/** 同上，但不檢查權限（給種子資料用）。 */
function tClosureSave_(c) {
  var day = /^\d{4}-\d{2}-\d{2}$/;
  if (!day.test(c.s || '')) throw new Error('請選開始日');
  var e = day.test(c.e || '') ? c.e : c.s;
  if (e < c.s) throw new Error('結束日不能早於開始日');
  if ((new Date(e) - new Date(c.s)) / 86400000 > 180) throw new Error('一次最多設定 180 天');
  var row = ['', c.s, e, c.type === 'open' ? '特別營業' : '店休', tClean_(c.reason, 40), c.show === true, new Date()];
  var sh = tSheet_(T_CLOSE_SHEET, T_CLOSE_HEAD);
  var lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var r = c.id ? tFindRow_(sh, c.id) : -1;
    if (r > 0) { row[0] = String(c.id); row[6] = sh.getRange(r, 7).getValue(); sh.getRange(r, 1, 1, row.length).setValues([row]); }
    else { row[0] = tSeq_('C'); sh.appendRow(row); }
  } finally { lock.releaseLock(); }
  sh.getRange(2, 6, Math.max(1, sh.getLastRow() - 1), 1).insertCheckboxes();
  return { id: row[0], closures: tListClosures_() };
}

function tDeleteClosure(id, key) {
  tGuard_(key);
  var sh = tSheet_(T_CLOSE_SHEET, T_CLOSE_HEAD), r = tFindRow_(sh, id);
  if (r > 0) sh.deleteRow(r);
  return tListClosures_();
}

// ======================================================================
// 交接紀錄：每班寫下要交代的事，下一班確認「已看過」或處理完按「完成」
// ======================================================================
var T_HAND_SHEET = '交接紀錄';
var T_HAND_HEAD = ['編號', '時間', '日期', '班別', '填寫人', '類型', '內容', '需下一班處理', '狀態', '完成人', '完成時間', '已看過', '優先級', '指定交給', '已提醒'];
var T_SHIFTS = ['早班', '午班', '打烊', '其他'];
var T_HAND_PRIOS = ['急', '一般', '緩'];
var T_HAND_TYPES = ['現金／零用金', '叫貨補貨', '設備', '顧客／客訴', '預訂', '其他'];

/** 取得交接分頁；舊的分頁補上新增的欄位標題 */
function tHandSheet_() {
  var sh = tSheet_(T_HAND_SHEET, T_HAND_HEAD);
  if (sh.getRange(1, 13).getValue() !== T_HAND_HEAD[12]) sh.getRange(1, 13, 1, 3).setValues([T_HAND_HEAD.slice(12)]).setFontWeight('bold');
  return sh;
}
function tListHandover_() {
  var sh;
  try { sh = tHandSheet_(); } catch (e) { return []; }
  var since = tAddDays_(tToday_(), -14);
  var out = tRows_(sh, T_HAND_HEAD.length).filter(function (r) { return r[0]; }).map(function (r) {
    return {
      id: String(r[0]), at: tDate_(r[1]), day: tDay_(r[2]), shift: String(r[3]), who: String(r[4]),
      types: String(r[5] || '').split('、').filter(String), text: String(r[6] || ''), todo: r[7] === true || r[7] === '是',
      status: String(r[8] || ''), doneBy: String(r[9] || ''), doneAt: tDate_(r[10]),
      seen: String(r[11] || '').split('、').filter(String),
      prio: T_HAND_PRIOS.indexOf(String(r[12])) >= 0 ? String(r[12]) : '一般', to: String(r[13] || ''), reminded: String(r[14] || '')
    };
  }).filter(function (h) { return h.day >= since || h.status === '待處理'; });
  out.reverse();
  out.sort(function (a, b) { return (b.status === '待處理') - (a.status === '待處理') || T_HAND_PRIOS.indexOf(a.prio) - T_HAND_PRIOS.indexOf(b.prio); });
  return out.slice(0, 80);
}

/** 新增交接。h = {day, shift, who, types:[], text, todo} */
function tAddHandover(h, key) {
  tGuard_(key);
  var text = tClean_(h.text, 1000).trim(), who = tClean_(h.who, 20).trim();
  if (!text) throw new Error('請寫交接內容');
  if (!who) throw new Error('請填你的名字');
  var day = /^\d{4}-\d{2}-\d{2}$/.test(h.day || '') ? h.day : tToday_();
  var types = (h.types || []).filter(function (t) { return T_HAND_TYPES.indexOf(t) >= 0; });
  var shift = T_SHIFTS.indexOf(h.shift) >= 0 ? h.shift : '其他';
  var sh = tHandSheet_(), prio = T_HAND_PRIOS.indexOf(h.prio) >= 0 ? h.prio : '一般', to = tClean_(h.to, 20).trim();
  var lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    sh.appendRow([tSeq_('S'), new Date(), day, shift, who, types.join('、'), text, h.todo === true, h.todo === true ? '待處理' : '已記錄', '', '', '', prio, to, '']);
  } finally { lock.releaseLock(); }
  return tGetHandover(key);
}

/** 待處理事項按「完成」 */
function tDoneHandover(id, who, key) {
  tGuard_(key);
  tHandMark_(id, who);
  return tGetHandover(key);
}
function tHandMark_(id, who) {
  var sh = tHandSheet_(), r = tFindRow_(sh, id);
  if (r < 0) throw new Error('找不到這筆交接');
  sh.getRange(r, 9, 1, 3).setValues([['已完成', tClean_(who, 20) || '夥伴', new Date()]]);
}
/** 隔天提醒：每天 9 點後，把還沒處理的交接（急的在最前面）寄給店主，指定了人且有信箱的也寄給他；一天一次 */
function tHandRemind_() {
  var today = tToday_();
  if (Number(Utilities.formatDate(new Date(Date.now()), T_TZ, 'HH')) < 9) return { sent: 0 };
  if (tGetJson_('hand_last', '') === today) return { sent: 0 };
  var pend = tListHandover_().filter(function (h) { return h.status === '待處理' && h.day < today; });
  tSetJson_('hand_last', today);
  if (!pend.length) return { sent: 0 };
  var line = function (h) { return '【' + h.prio + '】' + h.day + ' ' + h.shift + '（' + h.who + '）' + (h.to ? ' → ' + h.to : '') + '：' + h.text; };
  var body = '以下是還沒處理的交接事項，共 ' + pend.length + ' 筆（急的在前）：\n\n' + pend.map(line).join('\n') + '\n\n處理完請到「店家工具」→「交接」按「處理完成」。';
  var sent = 0, to = typeof notifyTo_ === 'function' ? notifyTo_('hand') : (typeof shopCfg_ === 'function' ? shopCfg_().notifyEmail : ''), done = {};
  if (to && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(to)) { tMail_(to, '【交接提醒】還有 ' + pend.length + ' 筆沒處理', body); sent++; done[to] = 1; }
  if (typeof stEmps_ === 'function' && (typeof notifyOn_ !== 'function' || notifyOn_('handEmp'))) {
    var onDuty = {};
    stRows_('shift').forEach(function (r) { if (stStr_(r['日期']) === today) onDuty[String(r['員工編號'])] = 1; });
    stEmps_().filter(function (e) { return e.status === '在職' && e.email && !done[e.email]; }).forEach(function (e) {
      var mine = pend.filter(function (h) { return h.to === e.name || (!h.to && onDuty[e.id]); });
      if (!mine.length) return;
      tMail_(e.email, '【交接提醒】有 ' + mine.length + ' 筆交接要處理', e.name + ' 你好，\n\n' + mine.map(line).join('\n') + '\n\n處理完請在員工入口的班表頁按「處理完成」。', { brand: 'shop' }); sent++;
    });
  }
  return { sent: sent, items: pend.length };
}

/** 下一班按「已看過」，記下名字 */
function tAckHandover(id, who, key) {
  tGuard_(key);
  who = tClean_(who, 20).trim();
  if (!who) throw new Error('請填你的名字');
  var sh = tHandSheet_(), r = tFindRow_(sh, id);
  if (r < 0) throw new Error('找不到這筆交接');
  var cell = sh.getRange(r, 12), seen = String(cell.getValue() || '').split('、').filter(String);
  if (seen.indexOf(who) < 0) seen.push(who);
  cell.setValue(seen.join('、'));
  return tGetHandover(key);
}

function tGetHandover(key) {
  tGuardRead_(key);
  return { handover: tListHandover_(), summary: tShiftSummary_() };
}

/** 今日摘要：今明兩天的預訂、待確認預訂、待處理異常、敲敲老闆、近期店休、今天有沒有營業 */
function tShiftSummary_() {
  var t = tToday_(), tm = tAddDays_(t, 1), out = { today: t, tomorrow: tm, pre: [], preNew: 0, helpOpen: 0, knockOpen: 0, closures: [], todayInfo: null };
  try { out.todayInfo = tClosedInfo_(t); out.tomorrowInfo = tClosedInfo_(tm); } catch (e) {}
  var lim = tAddDays_(t, 14);
  try { out.closures = tListClosures_().filter(function (c) { return c.e >= t && c.s <= lim; }); } catch (e) {}
  if (typeof CUSTOMER_SHEETS === 'undefined') return out;
  var ss = tSs_();
  function sheetRows(cfg) {
    var sh = ss.getSheetByName(cfg.name);
    if (!sh || sh.getLastRow() < 2) return [];
    return sh.getRange(2, 1, sh.getLastRow() - 1, cfg.head.length).getValues();
  }
  var P = CUSTOMER_SHEETS.pre, pi = function (n) { return P.head.indexOf(n); };
  sheetRows(P).forEach(function (r) {
    var st = String(r[pi('狀態')] || ''), d = tDay_(r[pi('取餐日期')]);
    if (st === '取消' || st === '已完成') return;
    if (st === '待確認' && d >= t) out.preNew++;
    if (d === t || d === tm) {
      var tm0 = r[pi('取餐時間')];
      out.pre.push({ id: String(r[0]), day: d, time: tm0 instanceof Date ? Utilities.formatDate(tm0, T_TZ, 'HH:mm') : String(tm0 || ''),
        name: String(r[pi('姓名')] || ''), count: Number(r[pi('總件數')]) || 0, total: Number(r[pi('預估金額')]) || 0, status: st });
    }
  });
  out.pre.sort(function (a, b) { return (a.day + a.time) < (b.day + b.time) ? -1 : 1; });
  function openCount(cfg) {
    var si = cfg.head.indexOf('狀態');
    return sheetRows(cfg).filter(function (r) { var s = String(r[si] || ''); return s === '待處理' || s === '處理中'; }).length;
  }
  out.helpOpen = openCount(CUSTOMER_SHEETS.help);
  out.knockOpen = openCount(CUSTOMER_SHEETS.knock);
  return out;
}
