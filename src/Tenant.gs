/**
 * 多店家核心（Tenant.gs）：店家情境、每店設定儲存、簽章通行證、授權狀態、權限檢查。
 *
 * 兩種模式：
 *  - 單店模式（Script Properties 沒有 centerId）：完全照舊，用 STAFF_KEY，資料在這份試算表。
 *  - 線上服務模式（有 centerId）：每家店一份試算表，用「通行證」登入，授權狀態由授權中心試算表決定。
 *
 * 線上服務模式下，所有「每店資料」都經過 props_()／book_()／subFolder_()，
 * 沒有店家情境（CTX）時一律丟錯，不會悄悄讀到別家店的資料。
 */

/* ================= 授權中心的分頁與欄位 ================= */
var CENTER = {
  shops: { name: '店家', head: ['店家編號', '公司名稱', '統編', '負責人', '登入Email', '方案', '狀態', '到期日', '試算表ID', '資料夾ID', '密碼鹽', '密碼雜湊', '通行證版本', '建立時間', '最後使用', '名稱鎖定至', '備註', 'Email已驗證', '品牌編號', '角色'] },
  partners: { name: '夥伴', head: ['夥伴編號', '店家編號', '名稱', '角色', '邀請碼雜湊', '邀請到期', '綁定裝置', '狀態', '建立時間', '最後使用'] },
  logs: { name: '登入紀錄', head: ['時間', '店家編號', '誰', '動作', '結果', '備註'] },
  pays: { name: '付款', head: ['付款編號', '店家編號', '方案', '週期', '金額', '供應商', '外部單號', '狀態', '建立時間', '付款時間', '期間起', '期間迄', '發票號碼', '備註'] }
};
var ST_LABEL = { pending: '待啟用', trial: '試用', pilot: '試營運', active: '使用中', grace: '寬限', readonly: '唯讀', suspended: '停用' };
var GRACE_DAYS = 7;        /* 到期後寬限幾天（照常使用） */
var READONLY_DAYS = 90;    /* 寬限後唯讀幾天（只能看，不能改），之後停用 */
var OWNER_DAYS = 30, STAFF_DAYS = 365, ADMIN_DAYS = 1;   /* 通行證有效天數 */

var CTX = {};              /* 這次執行的店家情境：{ shopId, ssId, role, uid, shop, lic } */
var _saas = null, _spMap = null;

/* ================= 小工具 ================= */
function nowD_() { return new Date(Date.now()); }
function todayStr_() { return Utilities.formatDate(nowD_(), 'Asia/Taipei', 'yyyy-MM-dd'); }
function addDaysStr_(day, n) {
  var d = new Date(day + 'T00:00:00+08:00'); d.setTime(d.getTime() + n * 86400000);
  return Utilities.formatDate(d, 'Asia/Taipei', 'yyyy-MM-dd');
}
function daysBetween_(a, b) { return Math.round((new Date(b + 'T00:00:00+08:00') - new Date(a + 'T00:00:00+08:00')) / 86400000); }
function dayOf_(v) { return v instanceof Date ? Utilities.formatDate(v, 'Asia/Taipei', 'yyyy-MM-dd') : String(v || ''); }
function stampOf_(v) { return v instanceof Date ? Utilities.formatDate(v, 'Asia/Taipei', 'yyyy-MM-dd HH:mm') : String(v || ''); }
function hex_(bytes) { var s = ''; for (var i = 0; i < bytes.length; i++) s += ('0' + (bytes[i] & 255).toString(16)).slice(-2); return s; }
function sha256_(s) { return hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(s), Utilities.Charset.UTF_8)); }
function hmacHex_(s, key) { return hex_(Utilities.computeHmacSha256Signature(String(s), String(key))); }
function rand_(n) { var s = ''; while (s.length < n) s += Utilities.getUuid().replace(/-/g, ''); return s.slice(0, n); }
function randDigits_(n) { var h = rand_(n * 2), s = ''; for (var i = 0; i < n; i++) s += String(parseInt(h.substr(i * 2, 2), 16) % 10); return s; }
function sp0_() { return PropertiesService.getScriptProperties(); }
function secret_() {
  var p = sp0_(), k = p.getProperty('hmacKey');
  if (!k) { k = rand_(48); p.setProperty('hmacKey', k); }
  return k;
}
function b64u_(s) { return Utilities.base64EncodeWebSafe(s).replace(/=+$/, ''); }
function unb64u_(s) { while (s.length % 4) s += '='; return Utilities.newBlob(Utilities.base64DecodeWebSafe(s)).getDataAsString(); }

/* 密碼：每個人獨立的鹽＋伺服器密鑰，反覆雜湊 200 次（每次都是一次服務呼叫，太多會讓登入變慢） */
function pwHash_(pw, salt) {
  var h = String(pw) + '|' + salt;
  var key = secret_();
  for (var i = 0; i < 200; i++) h = sha256_(h + key);
  return h;
}
function pwOk_(pw, shop) { return !!shop.salt && pwHash_(pw, shop.salt) === shop.hash; }
function pwRule_(pw) {
  pw = String(pw || '');
  if (pw.length < 8) return '密碼至少 8 個字';
  if (pw.length > 64) return '密碼太長（最多 64 個字）';
  if (!/[A-Za-z]/.test(pw) || !/[0-9]/.test(pw)) return '密碼要同時有英文字母和數字';
  return '';
}

/* 統編檢查碼（財政部 2023/4 起新制：加權和被 5 整除；第 7 碼為 7 時另有特例） */
function taxIdOk_(id) {
  id = String(id || '');
  if (!/^\d{8}$/.test(id)) return false;
  var w = [1, 2, 1, 2, 1, 2, 4, 1], sum = 0, i;
  for (i = 0; i < 8; i++) { var p = Number(id[i]) * w[i]; sum += Math.floor(p / 10) + (p % 10); }
  if (sum % 5 === 0) return true;
  if (id[6] === '7') {
    var q = Number(id[6]) * 4; sum -= Math.floor(q / 10) + (q % 10);
    return (sum + 1) % 5 === 0 || sum % 5 === 0;
  }
  return false;
}

/* ================= 模式判斷 ================= */
function saas_() {
  if (_saas === null) _saas = !!sp0_().getProperty('centerId');
  return _saas;
}
function resetCtx_() { CTX = {}; _spMap = null; }

/* ================= 授權中心試算表 ================= */
function center_() {
  var id = sp0_().getProperty('centerId');
  if (!id) throw new Error('還沒有建立授權中心（請在 Apps Script 執行 setupCenter）');
  if (!CTX._center) CTX._center = SpreadsheetApp.openById(id);
  return CTX._center;
}
function cSheet_(key) {
  var cfg = CENTER[key], ss = center_(), sh = ss.getSheetByName(cfg.name);
  if (sh && !CTX._headFixed) {                     /* 新版多了欄位時，替舊的授權中心補上標題 */
    try {
      var have = sh.getRange(1, 1, 1, cfg.head.length).getValues()[0];
      var miss = false; cfg.head.forEach(function (h, i) { if (have[i] !== h) miss = true; });
      if (miss) { sh.getRange(1, 1, 1, cfg.head.length).setValues([cfg.head]).setFontWeight('bold'); sh.getRange(2, 1, 998, cfg.head.length).setNumberFormat('@'); }
    } catch (e) {}
    CTX._headFixed = true;
  }
  if (!sh) {
    sh = ss.insertSheet(cfg.name);
    sh.getRange(1, 1, 1, cfg.head.length).setValues([cfg.head]).setFontWeight('bold');
    sh.setFrozenRows(1);
    sh.getRange(2, 1, 998, cfg.head.length).setNumberFormat('@');     /* 純文字：統編不掉 0、雜湊不被當成數字、日期不被轉型 */
  }
  return sh;
}
/* 讀整張表 → [{_r: 列號, 欄名: 值}] */
function cRows_(key) {
  var cfg = CENTER[key], sh = cSheet_(key), n = sh.getLastRow() - 1;
  if (n < 1) return [];
  var vals = sh.getRange(2, 1, n, cfg.head.length).getValues(), out = [];
  vals.forEach(function (r, i) {
    if (!String(r[0]).trim()) return;
    var o = { _r: i + 2 };
    cfg.head.forEach(function (h, j) { o[h] = r[j]; });
    out.push(o);
  });
  return out;
}
function cVal_(v) { return v instanceof Date ? Utilities.formatDate(v, 'Asia/Taipei', 'yyyy-MM-dd HH:mm:ss') : v; }
function cAppend_(key, obj) {
  var cfg = CENTER[key], sh = cSheet_(key);
  var row = cfg.head.map(function (h) { return obj[h] === undefined ? '' : cVal_(obj[h]); });
  var r = sh.getLastRow() + 1;
  sh.getRange(r, 1, 1, row.length).setNumberFormat('@').setValues([row]);
  return r;
}
function cUpdate_(key, r, obj) {
  var cfg = CENTER[key], sh = cSheet_(key);
  Object.keys(obj).forEach(function (h) {
    var c = cfg.head.indexOf(h); if (c < 0) return;
    sh.getRange(r, c + 1).setNumberFormat('@').setValue(cVal_(obj[h]));
  });
}
function cLog_(shopId, who, action, result, note) {
  try { cAppend_('logs', { '時間': nowD_(), '店家編號': shopId || '', '誰': who || '', '動作': action, '結果': result, '備註': note || '' }); } catch (e) {}
}

/* ================= 店家 ================= */
function shopFromRow_(r) {
  return {
    id: String(r['店家編號']), name: String(r['公司名稱']), taxId: String(r['統編']).replace(/\D/g, '').padStart(8, '0'),
    owner: String(r['負責人'] || ''), email: String(r['登入Email'] || ''), plan: String(r['方案'] || ''),
    status: stKey_(r['狀態']), expires: dayOf_(r['到期日']), ssId: String(r['試算表ID'] || ''), folderId: String(r['資料夾ID'] || ''),
    salt: String(r['密碼鹽'] || ''), hash: String(r['密碼雜湊'] || ''), tv: Number(r['通行證版本'] || 1),
    created: stampOf_(r['建立時間']), lastUsed: stampOf_(r['最後使用']), nameLock: dayOf_(r['名稱鎖定至']), note: String(r['備註'] || ''),
    verified: r['Email已驗證'] === true || r['Email已驗證'] === 'TRUE' || r['Email已驗證'] === '是', _r: r._r,
    brandId: String(r['品牌編號'] || ''), role: String(r['角色'] || '')
  };
}
function stKey_(label) {
  label = String(label || '').trim();
  for (var k in ST_LABEL) if (ST_LABEL[k] === label || k === label) return k;
  return 'pending';
}
function allShops_() { return cRows_('shops').map(shopFromRow_); }
function shopById_(id) {
  var c = CacheService.getScriptCache(), hit = c.get('shop:' + id);
  if (hit) { try { return JSON.parse(hit); } catch (e) {} }
  var s = allShops_().filter(function (x) { return x.id === String(id); })[0];
  if (s) { try { c.put('shop:' + id, JSON.stringify(s), 600); } catch (e) {} }
  return s || null;
}
function shopByTaxId_(taxId) {
  taxId = String(taxId || '').replace(/\D/g, '');
  return allShops_().filter(function (x) { return x.taxId === taxId && x.role !== '分店'; })[0] || null;      /* 分店跟總店同統編，不能用統編登入 */
}
function dropShopCache_(id) { try { CacheService.getScriptCache().remove('shop:' + id); } catch (e) {} }
function nextShopId_() {
  var max = 0;
  cRows_('shops').forEach(function (r) { var n = Number(String(r['店家編號']).replace(/\D/g, '')); if (n > max) max = n; });
  return 'S' + ('000' + (max + 1)).slice(-4);
}
function saveShop_(shop, fields) {
  var o = {};
  var map = { name: '公司名稱', taxId: '統編', owner: '負責人', email: '登入Email', plan: '方案', expires: '到期日', ssId: '試算表ID', folderId: '資料夾ID',
    salt: '密碼鹽', hash: '密碼雜湊', tv: '通行證版本', lastUsed: '最後使用', nameLock: '名稱鎖定至', note: '備註', brandId: '品牌編號', role: '角色' };
  (fields || Object.keys(map).concat(['status', 'verified'])).forEach(function (f) {
    if (f === 'status') o['狀態'] = ST_LABEL[shop.status];
    else if (f === 'verified') o['Email已驗證'] = shop.verified === true;
    else if (map[f]) o[map[f]] = shop[f];
  });
  cUpdate_('shops', shop._r, o);
  dropShopCache_(shop.id);
}

/* ================= 授權狀態 =================
   到期日前＝全功能（試用／試營運／使用中；只有「試用」輸出加浮水印）→ 到期後 7 天寬限（照常，提醒續訂）→ 之後 90 天唯讀 → 再之後停用
   待啟用、停用＝blocked。mode：full／readonly／blocked */
function licOf_(shop) {
  if (shop.brandId && shop.brandId !== shop.id && shop.status !== 'suspended') {      /* 分店的授權跟著總店走（單獨停用某家分店仍然有效） */
    var hq = shopById_(shop.brandId);
    if (hq) shop = Object.assign({}, shop, { status: hq.status, expires: hq.expires });
  }
  var st = shop.status, t = todayStr_(), exp = shop.expires;
  var shown = st === 'grace' || st === 'readonly' ? 'active' : st;     /* 這兩個狀態只是每日工作寫上去的標示，實際以日期為準 */
  var out = { status: st, label: ST_LABEL[shown], expires: exp, mode: 'full', grace: false, daysLeft: null, watermark: st === 'trial', msg: '' };
  if (st === 'suspended') { out.mode = 'blocked'; out.msg = '這個帳號已停用，請聯絡客服。'; return out; }
  if (st === 'pending') { out.mode = 'blocked'; out.msg = '帳號尚未啟用，請先完成訂閱付款。'; return out; }
  if (!exp) return out;
  var past = daysBetween_(exp, t);
  out.daysLeft = -past;
  if (past <= 0) return out;
  if (past <= GRACE_DAYS) { out.grace = true; out.label = ST_LABEL.grace; out.msg = '訂閱已到期，還有 ' + (GRACE_DAYS - past + 1) + ' 天寬限期，請盡快續訂。'; return out; }
  if (past <= GRACE_DAYS + READONLY_DAYS) { out.mode = 'readonly'; out.label = ST_LABEL.readonly; out.msg = '訂閱已到期，目前只能查看，不能修改。請續訂後恢復編輯。'; return out; }
  out.mode = 'blocked'; out.label = ST_LABEL.suspended; out.msg = '訂閱已到期很久，帳號已停用。請聯絡客服。';
  return out;
}

/* ================= 通行證（HMAC 簽章） =================
   格式：base64url(JSON).簽章；內容 s 店家、r 角色 owner/staff/admin、u 誰、e 到期(秒)、v 版本 */
function tokenMake_(p, days) {
  p.e = Math.floor(Date.now() / 1000) + days * 86400;
  var body = b64u_(JSON.stringify(p));
  return body + '.' + hmacHex_(body, secret_()).slice(0, 40);
}
function tokenRead_(tok) {
  tok = String(tok || '');
  var i = tok.indexOf('.');
  if (i < 1) throw new Error('請重新登入');
  var body = tok.slice(0, i), sig = tok.slice(i + 1);
  if (hmacHex_(body, secret_()).slice(0, 40) !== sig) throw new Error('請重新登入');
  var p;
  try { p = JSON.parse(unb64u_(body)); } catch (e) { throw new Error('請重新登入'); }
  if (!p.e || p.e < Math.floor(Date.now() / 1000)) throw new Error('登入已過期，請重新登入');
  return p;
}

/* ================= 夥伴 ================= */
function partnerById_(id) {
  var c = CacheService.getScriptCache(), hit = c.get('pt:' + id);
  if (hit) { try { return JSON.parse(hit); } catch (e) {} }
  var r = cRows_('partners').filter(function (x) { return String(x['夥伴編號']) === String(id); })[0];
  var p = r ? { id: String(r['夥伴編號']), shopId: String(r['店家編號']), name: String(r['名稱']), role: String(r['角色']), status: String(r['狀態']), device: String(r['綁定裝置'] || '') } : null;
  if (p) { try { c.put('pt:' + id, JSON.stringify(p), 600); } catch (e) {} }
  return p;
}
function dropPartnerCache_(id) { try { CacheService.getScriptCache().remove('pt:' + id); } catch (e) {} }

/* ================= 權限檢查 =================
   key 是通行證（線上服務模式）或 STAFF_KEY（單店模式）。write=true 時，唯讀的店家也會被擋下。 */
function authGuard_(key, write) {
  resetCtx_();
  if (!saas_()) {
    if (key !== STAFF_KEY) throw new Error('沒有權限');
    return CTX;
  }
  var sid = '', role = 'owner', uid = 'owner', p;
  var legacy = sp0_().getProperty('legacyShopId');
  if (legacy && sp0_().getProperty('legacyKeyOn') === '1' && typeof STAFF_KEY !== 'undefined' && key === STAFF_KEY) { sid = legacy; role = 'staff'; uid = 'legacy-key'; }
  else {
    p = tokenRead_(key);
    if (p.r !== 'owner' && p.r !== 'staff') throw new Error('沒有權限');
    sid = p.s; role = p.r; uid = p.u;
  }
  var shop = shopById_(sid);
  if (!shop) throw new Error('找不到這家店');
  if (p && p.b) {                                    /* 品牌主以總店身分進入分店：總店的通行證版本要還有效 */
    var hq = shopById_(p.b);
    if (p.r !== 'owner' || !hq || shop.brandId !== hq.id || p.v !== hq.tv) throw new Error('登入已失效，請重新登入');
  } else if (p && p.r === 'owner' && p.v !== shop.tv) throw new Error('登入已失效，請重新登入');
  if (p && p.r === 'staff') {
    var pt = partnerById_(p.u);
    if (!pt || pt.shopId !== sid || pt.status !== '使用中') throw new Error('這個夥伴帳號已停用，請聯絡店長');
  }
  var lic = licOf_(shop);
  if (lic.mode === 'blocked') throw new Error(lic.msg);
  if (write && lic.mode === 'readonly') throw new Error(lic.msg);
  CTX = { shopId: sid, ssId: shop.ssId, role: role, uid: uid, shop: shop, lic: lic };
  touch_(shop, uid);
  return CTX;
}
function touch_(shop, uid) {
  try {
    var c = CacheService.getScriptCache(), k = 'seen:' + shop.id;
    if (c.get(k)) return;
    c.put(k, '1', 600);
    cUpdate_('shops', shop._r, { '最後使用': nowD_() });
  } catch (e) {}
}
function useShop_(sid) {
  resetCtx_();
  if (!saas_()) return null;
  var shop = shopById_(String(sid || ''));
  if (!shop || !shop.ssId) throw new Error('找不到這家店');
  var lic = licOf_(shop);
  if (lic.mode === 'blocked') throw new Error('這家店暫時停止服務');
  CTX = { shopId: shop.id, ssId: shop.ssId, role: 'public', uid: '', shop: shop, lic: lic };
  return shop;
}
function isOwner_() { return !saas_() || CTX.role === 'owner'; }

/* ================= 每店設定儲存（線上服務模式：存在店家試算表的「系統設定」分頁；單店模式：Script Properties） ================= */
function props_() {
  if (!saas_()) return sp0_();
  if (!CTX.ssId) throw new Error('內部錯誤：沒有店家情境');
  return shopProps_();
}
var SP_SHEET = '系統設定';
function shopProps_() {
  var sid = CTX.shopId, cache = CacheService.getScriptCache(), ck = 'sp:' + sid;
  function sheet() {
    var ss = book_(), sh = ss.getSheetByName(SP_SHEET);
    if (!sh) { sh = ss.insertSheet(SP_SHEET); sh.getRange(1, 1, 1, 2).setValues([['設定', '值']]).setFontWeight('bold'); sh.setFrozenRows(1); try { sh.hideSheet(); } catch (e) {} }
    return sh;
  }
  function load() {
    if (_spMap) return _spMap;
    var hit = cache.get(ck);
    if (hit) { try { _spMap = JSON.parse(hit); return _spMap; } catch (e) {} }
    var sh = sheet(), n = sh.getLastRow() - 1, m = {};
    if (n > 0) sh.getRange(2, 1, n, 2).getValues().forEach(function (r) { if (r[0] !== '') m[String(r[0])] = String(r[1]); });
    _spMap = m;
    try { cache.put(ck, JSON.stringify(m), 600); } catch (e) {}
    return m;
  }
  function write(k, v) {
    var sh = sheet(), n = sh.getLastRow() - 1, at = -1;
    if (n > 0) { var ks = sh.getRange(2, 1, n, 1).getValues(); for (var i = 0; i < ks.length; i++) if (String(ks[i][0]) === k) { at = i + 2; break; } }
    if (v === null) { if (at > 0) sh.deleteRow(at); }
    else if (at > 0) sh.getRange(at, 2).setNumberFormat('@').setValue(v);
    else { var r = sh.getLastRow() + 1; sh.getRange(r, 1, 1, 2).setNumberFormat('@'); sh.getRange(r, 1, 1, 2).setValues([[k, v]]); }
    cache.remove(ck); _spMap = null;
  }
  return {
    getProperty: function (k) { var m = load(); return k in m ? m[k] : null; },
    setProperty: function (k, v) { write(String(k), String(v)); },
    deleteProperty: function (k) { write(String(k), null); }
  };
}
function ck_(name) { return saas_() ? name + ':' + CTX.shopId : name; }

/* ================= 每店試算表／資料夾 ================= */
function bookOf_(ssId) { return SpreadsheetApp.openById(ssId); }
/* 店家的 Drive 資料夾裡，取（或建立）某個子資料夾。單店模式照舊用名稱找 */
function subFolder_(legacyName, childName) {
  if (saas_()) {
    if (!CTX.shop || !CTX.shop.folderId) throw new Error('這家店還沒有資料夾');
    var root = DriveApp.getFolderById(CTX.shop.folderId), it = root.getFoldersByName(childName);
    return it.hasNext() ? it.next() : root.createFolder(childName);
  }
  var it2 = DriveApp.getFoldersByName(legacyName);
  return it2.hasNext() ? it2.next() : DriveApp.createFolder(legacyName);
}

/* ================= 每店設定（店名、聯絡方式、營業日…）=================
   單店模式用 Code.gs 上方的常數；線上服務模式存在「系統設定」的 cfg，沒填的欄位用預設值 */
var CFG_DEFAULT = {
  name: '我的餐廳', tagline: '', address: '', addrCity: '', addrDist: '', addrRoad: '', phone: '', phoneLandArea: '', phoneLandNum: '', phoneMobile: '', hours: '', closedText: '', lineId: '', lineUrl: '', orderUrl: '', mapUrl: '', fbUrl: '',
  primary: '#1B4F8A', accent: '#E8762A', menuQr: true,
  openDays: [1, 2, 3, 4, 5, 6, 0], channels: ['現場／電話／LINE 點餐'], minDays: 1, notifyEmail: '', menuEmail: '', heroTag: '', notifyOff: []
};
function legacyCfg_() {
    return {
      name: '弘林早午餐', nameA: '弘林', nameB: '早午餐', tagline: '中壢 25 年在地好味道',
      address: '桃園市中壢區廣州路11號（東興國中旁）', phone: '03-4588229（是我爸爸餓餓叫）', hours: '週一、二、五、六、日 06:00–13:00', closedText: '公休：週三、週四',
      lineId: '@322kwvxu', lineUrl: LINKS.line, orderUrl: LINKS.order, mapUrl: LINKS.map, fbUrl: LINKS.fb, openDays: OPEN_DAYS, channels: CHANNELS, minDays: PREORDER_MIN_DAYS,
      primary: '#1B4F8A', accent: '#E8762A',
      notifyEmail: NOTIFY_EMAIL, menuEmail: MENU_EMAIL, heroTag: '吃早餐，來找藍綿羊！', heroSub: '吃早餐，來找藍綿羊', brandLegacy: true
    };
}
/* ================= 通知信開關 =================
   店主在「帳號」頁勾選要收哪些通知；沒勾的那一類就完全不寄（cfg.notifyOff 存「關掉的」，預設全開）。
   寄給店主：通知信箱 → 沒填就寄登入信箱。寄給員工的排程提醒用 notifyOn_('xxxEmp') 判斷。 */
var NOTIFY_TYPES = [
  { k: 'pre', t: '顧客預訂', g: 'now' }, { k: 'help', t: '顧客異常回報', g: 'now' }, { k: 'knock', t: '敲敲老闆', g: 'now' }, { k: 'wish', t: '顧客許願', g: 'now' },
  { k: 'leave', t: '員工請假申請', g: 'now' }, { k: 'join', t: '員工填好資料', g: 'now' }, { k: 'apply', t: '面試登記', g: 'now' },
  { k: 'miss', t: '未打卡名單', g: 'auto', emp: 'missEmp' }, { k: 'avail', t: '預期排班已提醒', g: 'auto' },
  { k: 'hand', t: '交接提醒', g: 'auto', emp: 'handEmp' }, { k: 'order', t: '叫貨提醒', g: 'auto', emp: 'orderEmp' }
];
function notifyKeys_() {
  var out = [];
  NOTIFY_TYPES.forEach(function (x) { out.push(x.k); if (x.emp) out.push(x.emp); });
  return out;
}
function notifyOn_(type) {
  var off = shopCfg_().notifyOff;
  return !(Array.isArray(off) && off.indexOf(type) >= 0);
}
/** 這一類通知要寄給店主的信箱；店主關掉了就回傳空字串（不寄） */
function notifyTo_(type) {
  if (!notifyOn_(type)) return '';
  var c = shopCfg_();
  return c.notifyEmail || (saas_() && CTX.shop ? CTX.shop.email || '' : '');
}
function shopCfg_() {
  if (!saas_()) return legacyCfg_();
  var saved = {};
  try { saved = JSON.parse(props_().getProperty('cfg') || '{}'); } catch (e) {}
  var c = {};
  Object.keys(CFG_DEFAULT).forEach(function (k) { c[k] = saved[k] != null && saved[k] !== '' ? saved[k] : CFG_DEFAULT[k]; });
  if (!c.name || c.name === CFG_DEFAULT.name) c.name = (CTX.shop && CTX.shop.name) || CFG_DEFAULT.name;
  c.nameA = c.name; c.nameB = '';
  c.heroSub = c.tagline;
  if (!c.heroTag) c.heroTag = c.tagline;
  return c;
}
