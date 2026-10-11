/**
 * 人員與班表（StaffServer.gs；前綴 st）：員工、排班、打卡、請假、文件下載區。
 * 管理頁 ?p=staff（店主）、員工打卡頁 ?p=clock（員工用姓名＋PIN，不用登入帳號）。
 * 資料存在每家店自己的試算表：員工／班表／打卡／請假／文件 五個分頁（全部純文字格式）。
 */
var ST_SHEETS = {
  emp: { name: '員工', head: ['編號', '姓名', '職稱', 'PIN雜湊', 'PIN版本', '狀態', '建立日期', '備註', '電子郵件', '電話', '夥伴編號', '建檔碼雜湊', '建檔到期', '緊急聯絡人', '緊急電話', '到職日', '地址', '證件正面', '證件反面', '存摺', '資料夾'] },
  shift: { name: '班表', head: ['日期', '員工編號', '班別', '開始', '結束', '備註'] },
  punch: { name: '打卡', head: ['編號', '日期', '員工編號', '上班', '下班', '備註', '來源'] },
  leave: { name: '請假', head: ['編號', '申請時間', '員工編號', '類別', '開始日', '結束日', '事由', '狀態', '審核時間', '回覆'] },
  apply: { name: '應徵', head: ['編號', '登記時間', '姓名', '電話', '電子郵件', '應徵職位', '希望面試時段', '自我介紹', '狀態', '備註'] },
  vendor: { name: '廠商', head: ['編號', '名稱', '分類', '付款方式', '常用金額', '狀態', '排序', '置頂', '叫貨日', '叫貨時間', '負責人'] },
  ledger: { name: '收支', head: ['編號', '日期', '類型', '分類', '廠商編號', '廠商名稱', '金額', '付款方式', '結清', '備註', '記錄者', '建立時間', '發票號碼', '購買品項', '應稅金額', '稅額', '採購人員', '憑證', '收據檔案', '正本'] },
  doc: { name: '文件', head: ['編號', '標題', '分類', '檔案編號', '連結', '對象', '上傳時間', '檔名', '大小KB', '必讀'] },
  docread: { name: '文件已讀', head: ['文件編號', '員工編號', '時間'] },
  order: { name: '叫貨紀錄', head: ['日期', '廠商編號', '狀態', '時間', '記錄者'] },
  avail: { name: '預期排班', head: ['期間', '員工編號', '日期', '備註', '提交時間'] }
};
var ST_APPLY_STATUS = ['新登記', '已聯絡', '約定面試', '錄取', '未錄取'];
var ST_LEAVE_TYPES = ['事假', '病假', '特休', '公假', '其他'];
var ST_DOC_CATS = ['工作守則', '教育訓練', '常用文件', '規章制度', '表單', '作業流程', '菜單與價目', '證照與許可', '其他'];
var ST_DEFAULT_SHIFTS = [{ n: '早班', s: '06:00', e: '13:00' }, { n: '晚班', s: '13:00', e: '20:00' }, { n: '全天', s: '06:00', e: '20:00' }];
var ST_LATE_GRACE = 5;                 // 超過上班時間幾分鐘才算遲到
var ST_MAX_EMP = 60;
var ST_DOC_MAX = 10 * 1024 * 1024;
var ST_DOC_EXT = { pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', doc: 'application/msword', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', xls: 'application/vnd.ms-excel', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', ppt: 'application/vnd.ms-powerpoint', pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', txt: 'text/plain', csv: 'text/csv' };

/* ---------- 日期時間（一律台北時間，字串） ---------- */
function stNow_() { return new Date(Date.now()); }
function stToday_() { return Utilities.formatDate(stNow_(), 'Asia/Taipei', 'yyyy-MM-dd'); }
function stClock_() { return Utilities.formatDate(stNow_(), 'Asia/Taipei', 'HH:mm'); }
function stDayOk_(d) { return /^\d{4}-\d{2}-\d{2}$/.test(String(d || '')) && !isNaN(Date.parse(d + 'T00:00:00Z')); }
function stTimeOk_(t) { return /^([01]\d|2[0-3]):[0-5]\d$/.test(String(t || '')); }
function stAdd_(day, n) { var d = new Date(Date.parse(day + 'T00:00:00Z') + n * 86400000); return d.toISOString().slice(0, 10); }
function stDow_(day) { return new Date(Date.parse(day + 'T00:00:00Z')).getUTCDay(); }
function stWeekStart_(day) { var w = stDow_(day); return stAdd_(day, -((w + 6) % 7)); }
function stMin_(t) { return Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5)); }
function stStr_(v) {
  if (v instanceof Date) return v.getUTCFullYear() < 1950 ? Utilities.formatDate(v, 'Asia/Taipei', 'HH:mm') : Utilities.formatDate(v, 'Asia/Taipei', 'yyyy-MM-dd');
  return v == null ? '' : String(v);
}
function stT_(v) { return v instanceof Date ? Utilities.formatDate(v, 'Asia/Taipei', 'HH:mm') : stStr_(v); }

/* ---------- 試算表讀寫 ---------- */
function stSheet_(k) {
  var def = ST_SHEETS[k], ss = tSs_(), sh = ss.getSheetByName(def.name);
  if (!sh) {
    sh = ss.insertSheet(def.name);
    sh.getRange(1, 1, 1, def.head.length).setNumberFormat('@');
    sh.getRange(1, 1, 1, def.head.length).setValues([def.head]).setFontWeight('bold');
    sh.setFrozenRows(1);
    try { sh.getRange(1, 1, Math.max(sh.getMaxRows ? sh.getMaxRows() : 1000, 1000), def.head.length).setNumberFormat('@'); } catch (e) {}
  } else if (sh.getLastColumn && sh.getLastColumn() < def.head.length) {
    var from = sh.getLastColumn() + 1;
    sh.getRange(1, from, 1, def.head.length - from + 1).setNumberFormat('@');
    sh.getRange(1, from, 1, def.head.length - from + 1).setValues([def.head.slice(from - 1)]).setFontWeight('bold');
  }
  return sh;
}
function stRows_(k) {
  var def = ST_SHEETS[k], sh = stSheet_(k), n = sh.getLastRow() - 1, out = [];
  if (n < 1) return out;
  sh.getRange(2, 1, n, def.head.length).getValues().forEach(function (r, i) {
    if (r[0] === '' && r[1] === '') return;
    var o = { _r: i + 2 };
    def.head.forEach(function (h, j) { o[h] = r[j]; });
    out.push(o);
  });
  return out;
}
function stPut_(k, row, vals) {
  var sh = stSheet_(k), n = ST_SHEETS[k].head.length;
  var rg = sh.getRange(row || sh.getLastRow() + 1, 1, 1, n);
  rg.setNumberFormat('@'); rg.setValues([vals]);
}
function stDel_(k, rows) {
  var sh = stSheet_(k);
  rows.slice().sort(function (a, b) { return b - a; }).forEach(function (r) { sh.deleteRow(r); });
}
function stNextId_(k, prefix, width) {
  var head = ST_SHEETS[k].head[0], max = 0;
  stRows_(k).forEach(function (r) { var m = String(r[head]).match(/(\d+)$/); if (m && Number(m[1]) > max) max = Number(m[1]); });
  var s = String(max + 1); while (s.length < width) s = '0' + s;
  return prefix + s;
}
function stLocked_(fn) {
  var lock = LockService.getScriptLock(); lock.waitLock(15000);
  try { return fn(); } finally { lock.releaseLock(); }
}

/* ---------- 設定（班別範本） ---------- */
var ST_REASONS = ['交通延誤', '忘記打卡', '臨時支援'];
function stCfg_() {
  var c = tGetJson_('st_cfg', null) || {};
  return {
    shifts: Array.isArray(c.shifts) && c.shifts.length ? c.shifts : ST_DEFAULT_SHIFTS, grace: Number(c.grace) >= 0 ? Number(c.grace) : ST_LATE_GRACE,
    reasons: Array.isArray(c.reasons) && c.reasons.length ? c.reasons : ST_REASONS,           // 補打卡原因選項（另有「其他」可自填）
    missMins: Number(c.missMins) > 0 ? Number(c.missMins) : 15,                              // 上班後幾分鐘還沒打卡就提醒
    missRemind: c.missRemind !== false,                                                       // 是否自動提醒未打卡
    avail: { on: !!(c.avail && c.avail.on), mode: c.avail && c.avail.mode === 'biweek' ? 'biweek' : 'month', day: c.avail && Number(c.avail.day) >= 1 && Number(c.avail.day) <= 28 ? Number(c.avail.day) : 25 }
  };
}
function stPinHash_(pin, id) { return sha256_(String(pin) + '|' + id + '|' + secret_()); }

/* ---------- 員工 ---------- */
function stEmps_() {
  return stRows_('emp').map(function (r) {
    return { id: String(r['編號']), name: String(r['姓名']), title: String(r['職稱']), hash: String(r['PIN雜湊']), pinv: String(r['PIN版本'] || '1'), status: String(r['狀態'] || '在職'), created: stStr_(r['建立日期']), note: String(r['備註'] || ''), email: String(r['電子郵件'] || ''), phone: String(r['電話'] || ''), partner: String(r['夥伴編號'] || ''), codeHash: String(r['建檔碼雜湊'] || ''), codeExp: stStr_(r['建檔到期']), emName: String(r['緊急聯絡人'] || ''), emPhone: String(r['緊急電話'] || ''),
      hired: stStr_(r['到職日']), addr: String(r['地址'] || ''), idF: String(r['證件正面'] || ''), idB: String(r['證件反面'] || ''), bank: String(r['存摺'] || ''), dir: String(r['資料夾'] || ''), _r: r._r };
  });
}
function stEmpPut_(e) {
  stPut_('emp', e._r || 0, [e.id, e.name, e.title, e.hash || '', e.pinv || '1', e.status, e.created, e.note || '', e.email || '', e.phone || '', e.partner || '', e.codeHash || '', e.codeExp || '', e.emName || '', e.emPhone || '',
    e.hired || '', e.addr || '', e.idF || '', e.idB || '', e.bank || '', e.dir || '']);
}
function stEmpById_(id) { return stEmps_().filter(function (e) { return e.id === String(id); })[0] || null; }
function stEmpPub_(e, pmap) {
  var p = e.partner && pmap ? pmap[e.partner] : null;
  return { id: e.id, name: e.name, title: e.title, status: e.status, note: e.note, pinSet: !!e.hash, created: e.created, email: e.email, phone: e.phone,
    emName: e.emName, emPhone: e.emPhone, waiting: e.status === '待填寫', codeExp: e.codeExp,
    invite: !e.partner ? '' : (p ? p.status : '已移除'),
    hired: e.hired, addr: e.addr, files: { idF: stFileUrl_(e.idF), idB: stFileUrl_(e.idB), bank: stFileUrl_(e.bank) }, dir: e.dir ? 'https://drive.google.com/drive/folders/' + e.dir : '' };
}
function stFileUrl_(id) { return id ? 'https://drive.google.com/file/d/' + id + '/view' : ''; }
function stPartnerMap_() {
  var m = {};
  if (typeof saas_ !== 'function' || !saas_()) return m;
  cRows_('partners').forEach(function (r) { if (String(r['店家編號']) === CTX.shopId) m[String(r['夥伴編號'])] = { status: String(r['狀態']), _r: r._r }; });
  return m;
}
function stPhoneOk_(v) { return /^[0-9+\-() #]{8,20}$/.test(String(v || '')); }

/* ---------- 管理者權限：只有店主（單店模式的鑰匙視同店主） ---------- */
function stOwner_(key, write) {
  if (write) tGuard_(key); else tGuardRead_(key);
  if (typeof isOwner_ === 'function' && !isOwner_()) throw new Error('只有店主可以使用「人員與班表」');
}
function stClockUrl_() {
  var web = tWebUrl_(); if (!web) return '';
  return web + (typeof saas_ === 'function' && saas_() ? '?s=' + CTX.shopId + '&p=clock' : '?p=clock');
}

/* ================= 管理端 ================= */
function stState(key, weekStart) {
  stOwner_(key, false);
  var today = stToday_(), ws = stDayOk_(weekStart) ? stWeekStart_(weekStart) : stWeekStart_(today);
  var we = stAdd_(ws, 6), emps = stEmps_();
  var shifts = stRows_('shift').filter(function (r) { var d = stStr_(r['日期']); return d >= ws && d <= we; })
    .map(function (r) { return { d: stStr_(r['日期']), e: String(r['員工編號']), n: String(r['班別']), s: stT_(r['開始']), t: stT_(r['結束']), note: String(r['備註'] || '') }; });
  var leaves = stLeaves_(), pending = leaves.filter(function (l) { return l.status === '待審'; });
  var okLeaves = leaves.filter(function (l) { return l.status === '核准' && l.end >= ws && l.start <= we; });
  var punches = stRows_('punch'), on = [];
  punches.forEach(function (p) { if (stT_(p['下班']) === '' && stStr_(p['日期']) >= stAdd_(today, -1)) on.push({ e: String(p['員工編號']), d: stStr_(p['日期']), t: stT_(p['上班']) }); });
  var pm = stPartnerMap_(), todayOn = {};
  stRows_('shift').forEach(function (r) { if (stStr_(r['日期']) === today) todayOn[String(r['員工編號'])] = 1; });
  var onLeave = {};
  leaves.forEach(function (l) { if (l.status === '核准' && l.start <= today && l.end >= today) onLeave[l.e] = 1; });
  var offDuty = emps.filter(function (e) { return e.status === '在職' && !todayOn[e.id]; })
    .map(function (e) { return { id: e.id, name: e.name, title: e.title, phone: e.phone, email: e.email, why: onLeave[e.id] ? '請假' : '休息' }; });
  var applies = stApplies_();
  return { today: today, week: ws, att: stAttendance_(), avail: stAvailSummary_(stCfg_()), emps: emps.map(function (x) { return stEmpPub_(x, pm); }), offDuty: offDuty, hire: stHire_(), applyUrl: stApplyUrl_(), newApplies: applies.filter(function (a) { return a.status === '新登記'; }).length, cfg: stCfg_(), shifts: shifts, leaves: okLeaves, pending: pending, on: on,
    joinUrl: stJoinGeneralUrl_(), joinOn: stJoinCfg_().on, clockUrl: stClockUrl_(), leaveTypes: ST_LEAVE_TYPES, docCats: ST_DOC_CATS, docs: (function () { var rm = stDocReadMap_(); return stDocs_().map(function (d) { var p = stDocPub_(d); p.readN = Object.keys(rm[d.id] || {}).length; return p; }); })(), maxEmp: ST_MAX_EMP };
}

function stEmpSave(e, key) {
  stOwner_(key, true);
  return stEmpSave_(e);
}
/** 同上，但不檢查權限（給種子資料用，驗證規則完全一樣）。 */
function stEmpSave_(e) {
  e = e || {};
  var name = tClean_(e.name, 20).trim(), title = tClean_(e.title, 20).trim(), note = tClean_(e.note, 60);
  var email = tClean_(e.email, 60).trim(), phone = tClean_(e.phone, 20).trim();
  if (email && !emailOk_(email)) throw new Error('電子郵件格式不對');
  if (phone && !stPhoneOk_(phone)) throw new Error('電話格式不對（只能有數字、+、-、括號）');
  var emName = tClean_(e.emName, 20).trim(), emPhone = tClean_(e.emPhone, 20).trim();
  if (emPhone && !stPhoneOk_(emPhone)) throw new Error('緊急聯絡電話格式不對');
  var status = e.status === '離職' ? '離職' : '在職', pin = String(e.pin == null ? '' : e.pin).trim();
  var hired = e.hired == null ? null : String(e.hired).trim(), addr = e.addr == null ? null : tClean_(e.addr, 80).trim();
  if (hired && !stDayOk_(hired)) throw new Error('到職日格式不對（要 yyyy-MM-dd）');
  if (!name) throw new Error('請填員工姓名');
  if (pin && !/^\d{4,6}$/.test(pin)) throw new Error('PIN 要是 4～6 位數字');
  return stLocked_(function () {
    var all = stEmps_(), cur = e.id ? all.filter(function (x) { return x.id === String(e.id); })[0] : null;
    if (e.id && !cur) throw new Error('找不到這位員工');
    if (!cur && all.length >= ST_MAX_EMP) throw new Error('員工最多 ' + ST_MAX_EMP + ' 位');
    if (!cur && !pin) throw new Error('新員工要設定 PIN（4～6 位數字）');
    if (status === '在職' && all.some(function (x) { return x.status === '在職' && x.name === name && (!cur || x.id !== cur.id); })) throw new Error('已經有一位在職的「' + name + '」，請加上區別（例如 小明A）');
    if (cur) {
      var hash = cur.hash, pinv = cur.pinv;
      if (cur.status === '待填寫' || cur.status === '待確認') { if (!pin && !hash) throw new Error('這位員工還沒設定 PIN，請輸入 PIN 才能直接建立'); }
      if (pin) { hash = stPinHash_(pin, cur.id); pinv = String(Number(pinv) + 1); }
      else if (status === '離職' && cur.status !== '離職') pinv = String(Number(pinv) + 1);
      stEmpPut_(Object.assign({}, cur, { name: name, title: title, hash: hash, pinv: pinv, status: status, note: note, email: email, phone: phone, emName: emName, emPhone: emPhone, codeHash: '', codeExp: '',
        hired: hired == null ? cur.hired : hired, addr: addr == null ? cur.addr : addr }));
    } else {
      var id = stNextId_('emp', 'E', 3);
      stEmpPut_({ id: id, name: name, title: title, hash: stPinHash_(pin, id), pinv: '1', status: status, created: stToday_(), note: note, email: email, phone: phone, partner: '', emName: emName, emPhone: emPhone, hired: hired || '', addr: addr || '' });
    }
    var pm = stPartnerMap_();
    return stEmps_().map(function (x) { return stEmpPub_(x, pm); });
  });
}

/** 排班：整週覆蓋。rows = [{d, e, n, s, t, note}]（t＝結束時間；結束早於開始表示跨夜班） */
function stShiftSave(weekStart, rows, key) {
  stOwner_(key, true);
  return stShiftSave_(weekStart, rows);
}
/** 同上，但不檢查權限（給種子資料用）。 */
function stShiftSave_(weekStart, rows) {
  if (!stDayOk_(weekStart)) throw new Error('週別不正確');
  var ws = stWeekStart_(weekStart), we = stAdd_(ws, 6), emps = stEmps_(), ids = {};
  emps.forEach(function (x) { ids[x.id] = x; });
  if (!Array.isArray(rows)) throw new Error('資料格式不對');
  if (rows.length > 500) throw new Error('一週最多 500 筆班');
  var clean = [];
  rows.forEach(function (r) {
    if (!stDayOk_(r.d) || r.d < ws || r.d > we) throw new Error('班表日期超出這一週');
    if (!ids[r.e]) throw new Error('找不到員工 ' + tClean_(r.e, 10));
    if (!stTimeOk_(r.s) || !stTimeOk_(r.t)) throw new Error('班別時間格式不對（要 HH:mm）');
    if (r.s === r.t) throw new Error('開始與結束時間不能一樣');
    clean.push([r.d, r.e, tClean_(r.n, 12) || '班', r.s, r.t, tClean_(r.note, 40)]);
  });
  return stLocked_(function () {
    var old = stRows_('shift').filter(function (r) { var d = stStr_(r['日期']); return d >= ws && d <= we; }).map(function (r) { return r._r; });
    stDel_('shift', old);
    clean.sort(function (a, b) { return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[3] < b[3] ? -1 : 1; });
    clean.forEach(function (c) { stPut_('shift', 0, c); });
    return { saved: clean.length, week: ws };
  });
}

function stCfgSave(cfg, key) {
  stOwner_(key, true);
  return stCfgSave_(cfg);
}
/** 同上，但不檢查權限（給種子資料用）。 */
function stCfgSave_(cfg) {
  var list = ((cfg && cfg.shifts) || stCfg_().shifts).slice(0, 8).map(function (x) {
    if (!stTimeOk_(x.s) || !stTimeOk_(x.e) || x.s === x.e) throw new Error('班別「' + tClean_(x.n, 12) + '」的時間不正確');
    return { n: tClean_(x.n, 12) || '班', s: x.s, e: x.e };
  });
  if (!list.length) throw new Error('至少要有一種班別');
  var cur = stCfg_(), g = cfg.grace != null ? Math.min(60, Math.max(0, parseInt(cfg.grace, 10) || 0)) : cur.grace;
  var reasons = Array.isArray(cfg.reasons) ? cfg.reasons.map(function (x) { return tClean_(x, 12).trim(); }).filter(String).slice(0, 8) : cur.reasons;
  var av = cfg.avail ? { on: !!cfg.avail.on, mode: cfg.avail.mode === 'biweek' ? 'biweek' : 'month', day: Math.min(28, Math.max(1, parseInt(cfg.avail.day, 10) || 25)) } : cur.avail;
  tSetJson_('st_cfg', { shifts: list, grace: g, reasons: reasons.length ? reasons : ST_REASONS,
    missMins: cfg.missMins != null ? Math.min(180, Math.max(1, parseInt(cfg.missMins, 10) || 15)) : cur.missMins,
    missRemind: cfg.missRemind != null ? cfg.missRemind !== false : cur.missRemind, avail: av });
  return stCfg_();
}

/* ---------- 員工自己填資料（建檔連結）----------
   個人連結：店主先建一筆「待填寫」，產生一次性連結（7 天內有效，可寄信或自己用 LINE 傳）；員工填好就直接成為在職。
   通用連結：一條連結給所有新員工，填完進「待確認」，店主核准後才能打卡（連結可隨時關閉或換新）。 */
function stJoinCfg_() { var c = tGetJson_('st_join', null) || {}; return { on: c.on === true, code: String(c.code || '') }; }
function stJoinHash_(code) { return sha256_(String(code) + '|join|' + secret_()); }
function stJoinUrl_(code) {
  var web = tWebUrl_(); if (!web) return '';
  return web + (typeof saas_ === 'function' && saas_() ? '?s=' + CTX.shopId + '&p=join&jc=' : '?p=join&jc=') + code;
}
function stJoinGeneralUrl_() { var c = stJoinCfg_(); return c.on && c.code ? stJoinUrl_(c.code) : ''; }
/** 開啟／關閉通用建檔連結；reset 為真就換一條新的（舊的立刻失效） */
function stJoinSet(on, reset, key) {
  stOwner_(key, true);
  return stJoinSet_(on, reset);
}
/** 同上，但不檢查權限（給種子資料用）。 */
function stJoinSet_(on, reset) {
  var c = stJoinCfg_();
  if (on && (!c.code || reset)) c.code = rand_(14).toUpperCase().replace(/[^A-Z0-9]/g, 'X');
  tSetJson_('st_join', { on: !!on, code: c.code });
  return { on: !!on, url: on ? stJoinUrl_(c.code) : '' };
}
/** 建立「待填寫」員工並產生個人建檔連結。reissueId 有值＝替既有的待填寫員工換新連結。email 有填就寄信。 */
function stEmpInviteForm(label, email, reissueId, key, hired) {
  stOwner_(key, true);
  return stEmpInviteForm_(label, email, reissueId, hired);
}
/** 同上，但不檢查權限（給種子資料用）。email 空白就不寄信。hired＝到職日（特休天數依此計算，可事後補）。 */
function stEmpInviteForm_(label, email, reissueId, hired) {
  label = tClean_(label, 20).trim(); email = tClean_(email, 60).trim(); hired = String(hired || '').trim();
  if (hired && !stDayOk_(hired)) throw new Error('到職日格式不對（要 yyyy-MM-dd）');
  if (email && !emailOk_(email)) throw new Error('電子郵件格式不對');
  if (email && stMailLeft_() < 3) throw new Error('今天的寄信額度用完了，請明天再試，或改用複製連結傳給員工');
  var code = rand_(14).toUpperCase().replace(/[^A-Z0-9]/g, 'X'), exp = stAdd_(stToday_(), 7);
  var id = stLocked_(function () {
    var all = stEmps_(), cur = reissueId ? all.filter(function (x) { return x.id === String(reissueId) && x.status === '待填寫'; })[0] : null;
    if (reissueId && !cur) throw new Error('找不到這筆待填寫的邀請');
    if (!cur && all.length >= ST_MAX_EMP) throw new Error('員工最多 ' + ST_MAX_EMP + ' 位');
    if (cur) { stEmpPut_(Object.assign({}, cur, { codeHash: stJoinHash_(code), codeExp: exp, email: email || cur.email, name: label || cur.name, hired: hired || cur.hired })); return cur.id; }
    var nid = stNextId_('emp', 'E', 3);
    stEmpPut_({ id: nid, name: label || '（待填寫）', title: '', hash: '', pinv: '1', status: '待填寫', created: stToday_(), note: '', email: email, phone: '', partner: '', codeHash: stJoinHash_(code), codeExp: exp, hired: hired });
    return nid;
  });
  var url = stJoinUrl_(code), mailed = false;
  if (email) {
    mail_(email, '【' + stShopName_() + '】請填寫你的員工資料',
      (label ? label + ' 你好，\n\n' : '你好，\n\n') + stShopName_() + ' 邀請你建立員工資料（姓名、聯絡方式、證件與存摺照片，並設定打卡用的 PIN）。\n\n請點下面的連結填寫（' + exp + ' 前有效，只能用一次）：\n' + url + '\n\n填好後會再寄一封「登陸完成」信給你，附上你專屬的員工入口，可以加到手機主畫面，之後用手機打卡、看班表、請假。如果你不認識這家店，請忽略這封信。', null, { brand: 'shop', btn: '填寫員工資料' });
    mailed = true;
  }
  return { id: id, url: url, expires: exp, mailed: mailed };
}
function stJoinInfo_(sid, code) {
  code = String(code || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  var lk = 'join:' + (sid || 'x');
  if (lockedOut_(lk)) return { ok: false, msg: LOCK_MSG };
  if (code.length >= 10) {
    var gen = stJoinCfg_();
    if (gen.on && gen.code === code) return { ok: true, mode: 'general' };
    var h = stJoinHash_(code), today = stToday_();
    var e = stEmps_().filter(function (x) { return x.codeHash && x.codeHash === h && x.status === '待填寫'; })[0];
    if (e) {
      if (e.codeExp && e.codeExp < today) return { ok: false, msg: '這個連結已經過期了，請向店長重新索取。' };
      return { ok: true, mode: 'personal', emp: e, name: e.name === '（待填寫）' ? '' : e.name, email: e.email };
    }
  }
  failBump_(lk);
  return { ok: false, msg: '這個連結無效或已經用過了，請向店長重新索取。' };
}
/** 員工在公開頁自己填資料。f = {name, title, phone, email, emName, emPhone, pin} */
function stJoinSubmit(sid, code, f) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  var info = stJoinInfo_(sid, code);
  if (!info.ok) throw new Error(info.msg);
  f = f || {};
  var name = tClean_(f.name, 20).trim(), title = tClean_(f.title, 20).trim(), phone = tClean_(f.phone, 20).trim(), email = tClean_(f.email, 60).trim();
  var emName = tClean_(f.emName, 20).trim(), emPhone = tClean_(f.emPhone, 20).trim(), pin = String(f.pin == null ? '' : f.pin).trim();
  if (!name) throw new Error('請填姓名');
  if (!phone || !stPhoneOk_(phone)) throw new Error('請填正確的手機或電話（緊急聯絡用）');
  if (email && !emailOk_(email)) throw new Error('電子郵件格式不對');
  if (emPhone && !stPhoneOk_(emPhone)) throw new Error('緊急聯絡人電話格式不對');
  if (!/^\d{4,6}$/.test(pin)) throw new Error('PIN 要是 4～6 位數字');
  var addr = tClean_(f.addr, 80).trim(), files = stCheckFiles_(f.files);
  var c = CacheService.getScriptCache(), hk = 'joinn:' + (sid || 'x') + ':' + stToday_() + stClock_().slice(0, 2);
  if (info.mode === 'general') { var n = Number(c.get(hk) || 0); if (n >= 20) throw new Error('目前填寫的人太多，請稍後再試'); }
  var res = stLocked_(function () {
    var all = stEmps_();
    if (all.some(function (x) { return (x.status === '在職' || x.status === '待確認') && x.name === name && (!info.emp || x.id !== info.emp.id); })) throw new Error('已經有一位「' + name + '」了，請在姓名後面加上區別（例如 ' + name + 'A），或請店長處理');
    if (info.mode === 'personal') {
      var cur = stEmpById_(info.emp.id);
      if (!cur || cur.status !== '待填寫') throw new Error('這個連結已經用過了');
      stEmpPut_(Object.assign({}, cur, { name: name, title: title, phone: phone, email: email || cur.email, emName: emName, emPhone: emPhone, addr: addr, hash: stPinHash_(pin, cur.id), pinv: '1', status: '在職', codeHash: '', codeExp: '' }));
      return { id: cur.id, mode: 'personal' };
    }
    if (all.length >= ST_MAX_EMP) throw new Error('目前無法再新增，請聯絡店長');
    if (all.filter(function (x) { return x.status === '待確認'; }).length >= 20) throw new Error('目前待確認的人太多，請先請店長處理');
    var id = stNextId_('emp', 'E', 3);
    stEmpPut_({ id: id, name: name, title: title, hash: stPinHash_(pin, id), pinv: '1', status: '待確認', created: stToday_(), note: '自行填寫', email: email, phone: phone, partner: '', emName: emName, emPhone: emPhone, addr: addr });
    return { id: id, mode: 'general' };
  });
  if (info.mode === 'general') { try { c.put(hk, String(Number(c.get(hk) || 0) + 1), 3600); } catch (e) {} }
  var saved = stSaveEmpFiles_(res.id, files);
  var emp = stEmpById_(res.id);
  try { if (emp && emailOk_(emp.email)) stMailJoined_(emp, res.mode === 'personal'); } catch (err2) {}
  try {
    var to = typeof notifyTo_ === 'function' ? notifyTo_('join') : (typeof shopCfg_ === 'function' ? shopCfg_().notifyEmail : '');
    if (to && emailOk_(to)) mail_(to, '【員工資料】' + name + (res.mode === 'general' ? ' 填寫了員工資料，等你確認' : ' 完成了員工資料'), name + (res.mode === 'general' ? ' 透過建檔連結填寫了資料，請到「人員與班表」→「員工」核准後才能打卡。' : ' 已完成員工資料並設定好 PIN，現在可以打卡了。'));
  } catch (err) {}
  return { ok: true, mode: res.mode, clockUrl: stClockUrl_(), portalUrl: res.mode === 'personal' && emp ? stEmpLinkUrl_(emp) : '', uploaded: saved };
}

/* ---------- 員工專屬入口（個人連結）：打開就是本人，不列出別人的名字 ----------
   連結裡是 365 天的員工通行證（用既有的 jc 網址參數）；PIN 一換或按「重設連結」，舊連結立刻失效。 */
function stEmpToken_(e) { return tokenMake_({ s: (typeof saas_ === 'function' && saas_()) ? CTX.shopId : '', r: 'emp', u: e.id, v: e.pinv }, 365); }
function stEmpLinkUrl_(e) {
  var web = tWebUrl_(); if (!web) return '';
  return web + (typeof saas_ === 'function' && saas_() ? '?s=' + CTX.shopId + '&p=clock&jc=' : '?p=clock&jc=') + stEmpToken_(e);
}
function stEmpLink(id, key) {
  stOwner_(key, true);
  var e = stEmpById_(id); if (!e || e.status !== '在職') throw new Error('找不到這位在職員工');
  return { url: stEmpLinkUrl_(e), name: e.name };
}
/** 重設專屬連結：舊連結與已登入的手機全部失效（PIN 不變），再給新連結 */
function stEmpLinkReset(id, key) {
  stOwner_(key, true);
  return stLocked_(function () {
    var e = stEmpById_(id); if (!e || e.status !== '在職') throw new Error('找不到這位在職員工');
    e.pinv = String(Number(e.pinv) + 1); stEmpPut_(e);
    return { url: stEmpLinkUrl_(e), name: e.name };
  });
}
function stEmpLinkMail(id, key) {
  stOwner_(key, true);
  var e = stEmpById_(id); if (!e || e.status !== '在職') throw new Error('找不到這位在職員工');
  if (!emailOk_(e.email)) throw new Error('請先填這位員工的電子郵件');
  if (stMailLeft_() < 3) throw new Error('今天的寄信額度用完了，請明天再試');
  stMailJoined_(e, true);
  return { sent: true };
}
/** 「登陸完成」信：附專屬入口與加入主畫面的說明（通用連結自行填寫的員工，要等店主核准後才寄） */
function stMailJoined_(e, active) {
  var shop = stShopName_();
  if (!active) {
    mail_(e.email, '【' + shop + '】已收到你的員工資料', e.name + ' 你好，\n\n' + shop + ' 已收到你填寫的員工資料，店長確認後會再寄一封信，附上你專屬的員工入口。\n\n謝謝！', null, { brand: 'shop' });
    return;
  }
  var url = stEmpLinkUrl_(e), o = null;
  if (typeof mailHtml_ === 'function') { var sh = mailShop_(); o = { brand: 'shop', shop: sh, eyebrow: 'WELCOME', title: e.name + '，這是你的員工入口', preheader: '打卡、班表、請假都在這裡',
    blocks: [mkP_('你的員工資料已完成，歡迎加入 ' + mkEsc_(shop) + '！這個入口只顯示你自己的資料：'),
      mkRows_([['打卡', '上班時按一下'], ['我的班表', '本週與下週'], ['請假與特休', '線上申請，看剩幾天'], ['交接與守則', '今天要注意的事']]),
      mkBtn_('打開我的員工入口', url, sh.accent || MK.amber, mkOn_(sh.accent || MK.amber)),
      mkP_('<b>加到手機主畫面</b>，之後一點就開：'), mkRows_([['iPhone', 'Safari →「分享」→「加入主畫面」'], ['Android', 'Chrome →「⋮」→「加到主畫面」']]),
      mkNote_('這個連結只屬於你，請不要轉給別人。換手機或連結不見，跟店長說就能重寄。')],
    why: '你收到這封信，是因為 ' + shop + ' 替你建立了員工資料。' }; }
  mail_(e.email, '【' + shop + '】登陸完成！這是你的員工入口',
    e.name + ' 你好，\n\n你的員工資料已經完成，歡迎加入 ' + shop + '！\n\n這是你專屬的員工入口（只有你自己的畫面：打卡、我的班表、請假與特休、工作守則、教育訓練、常用文件、交接事項）：\n' + url +
    '\n\n請不要把這個連結轉給別人。\n\n建議現在就把它加到手機主畫面，之後一點就開：\n・iPhone：用 Safari 打開連結 → 下方「分享」→「加入主畫面」\n・Android：用 Chrome 打開連結 → 右上角「⋮」→「加到主畫面」\n\n若手機換了或連結遺失，請跟店長說，店長可以重新傳給你。', o);
}
var ST_FILE_KINDS = { idF: '身分證正面', idB: '身分證反面', bank: '存摺封面' };
var ST_FILE_MAX = 4 * 1024 * 1024;
/** 檢查員工上傳的檔案：f = {idF:{name,b64}, idB:{...}, bank:{...}}；只收 jpg／png／pdf、每份 4MB 內 */
function stCheckFiles_(f) {
  var out = {};
  Object.keys(ST_FILE_KINDS).forEach(function (k) {
    var x = f && f[k]; if (!x || !x.b64) return;
    var name = tClean_(x.name, 60) || 'file', ext = (name.split('.').pop() || '').toLowerCase();
    if (['jpg', 'jpeg', 'png', 'pdf'].indexOf(ext) < 0) throw new Error(ST_FILE_KINDS[k] + '：只收 JPG、PNG、PDF');
    var bytes;
    try { bytes = Utilities.base64Decode(String(x.b64)); } catch (e) { throw new Error(ST_FILE_KINDS[k] + '：檔案讀取失敗，請重新選擇'); }
    if (!bytes.length) throw new Error(ST_FILE_KINDS[k] + '：檔案是空的');
    if (bytes.length > ST_FILE_MAX) throw new Error(ST_FILE_KINDS[k] + '：檔案太大（上限 4MB），請重新拍照或選小一點的檔案');
    out[k] = { ext: ext, bytes: bytes, mime: ext === 'pdf' ? 'application/pdf' : ext === 'png' ? 'image/png' : 'image/jpeg' };
  });
  return out;
}
/** 把證件與存摺存進「店主自己的雲端」資料夾（不開公開連結，只有店主看得到）。失敗不影響建檔，回傳哪些成功 */
function stSaveEmpFiles_(empId, files) {
  var kinds = Object.keys(files || {}), ok = [];
  if (!kinds.length) return ok;
  try {
    var e = stEmpById_(empId), root = subFolder_('員工資料', '員工資料'), nm = e.id + ' ' + e.name.replace(/[\\\/:*?"|]/g, '_'), it = root.getFoldersByName(nm), dir = it.hasNext() ? it.next() : root.createFolder(nm);
    kinds.forEach(function (k) {
      var x = files[k], file = dir.createFile(Utilities.newBlob(x.bytes, x.mime, ST_FILE_KINDS[k] + '.' + x.ext));
      e[k] = file.getId(); ok.push(k);
    });
    e.dir = dir.getId(); stEmpPut_(e);
  } catch (err) {
    try { var e2 = stEmpById_(empId); if (e2) { e2.note = ((e2.note || '') + '（證件上傳失敗，請請對方再傳）').slice(0, 60); stEmpPut_(e2); } } catch (x) {}
  }
  return ok;
}
/** 核准（ok=true）或退回（ok=false，刪除這筆）自行填寫的員工；也可用來取消沒人填的邀請 */
function stEmpApprove(id, ok, key) {
  stOwner_(key, true);
  return stLocked_(function () {
    var e = stEmpById_(id);
    if (!e) throw new Error('找不到這位員工');
    if (e.status !== '待確認' && e.status !== '待填寫') throw new Error('這位員工不是待處理狀態');
    if (ok) {
      if (e.status !== '待確認') throw new Error('還沒填寫完成，不能核准');
      stEmpPut_(Object.assign({}, e, { status: '在職' }));
      try { if (emailOk_(e.email)) stMailJoined_(Object.assign({}, e, { status: '在職' }), true); } catch (err) {}
    } else stDel_('emp', [e._r]);
    var pm = stPartnerMap_();
    return stEmps_().map(function (x) { return stEmpPub_(x, pm); });
  });
}

/* ---------- 邀請員工成為夥伴（店主備用）---------- */
function stMailLeft_() { try { return typeof MailApp.getRemainingDailyQuota === 'function' ? MailApp.getRemainingDailyQuota() : 100; } catch (e) { return 100; } }
function stShopName_() { return (typeof shopCfg_ === 'function' ? shopCfg_().name : '') || '本店'; }
function stEmpInvite(empId, key) {
  stOwner_(key, true);
  if (typeof saas_ !== 'function' || !saas_()) throw new Error('單店模式沒有夥伴邀請：請直接把夥伴網址傳給對方');
  var e = stEmpById_(empId);
  if (!e) throw new Error('找不到這位員工');
  if (!emailOk_(e.email)) throw new Error('請先填這位員工的電子郵件，再邀請');
  if (stMailLeft_() < 3) throw new Error('今天的寄信額度用完了，請明天再試');
  var rows = cRows_('partners').filter(function (r) { return String(r['店家編號']) === CTX.shopId; });
  var mine = e.partner ? rows.filter(function (r) { return String(r['夥伴編號']) === e.partner; })[0] : null;
  if (mine && mine['狀態'] === '使用中') throw new Error('這位員工已經是夥伴了');
  if (mine && mine['狀態'] === '邀請中') cUpdate_('partners', mine._r, { '狀態': '停用', '邀請碼雜湊': '' });
  if (rows.filter(function (r) { return r['狀態'] !== '停用'; }).length >= 30) throw new Error('夥伴帳號已達上限（30 個）');
  var inv = invitePartner_(CTX.shopId, e.name, e.email);
  stEmpPut_(Object.assign({}, e, { partner: inv.id }));
  mail_(e.email, '【' + stShopName_() + '】邀請你成為店家夥伴',
    e.name + ' 你好，\n\n' + stShopName_() + ' 邀請你成為店家夥伴：需要時可以協助查看與更新菜單價格、店家工具，作為店主的備用聯絡與支援。\n\n' +
    '請用要常用的手機或電腦，打開下面的連結完成綁定（連結 ' + inv.expires + ' 前有效，只能綁定第一個打開的裝置）：\n' + inv.link + '\n\n如果你不認識這家店，請忽略這封信。', null, { brand: 'shop', btn: '綁定這支手機' });
  cLog_(CTX.shopId, 'owner', '邀請員工為夥伴', '成功', e.name);
  return { ok: true, expires: inv.expires };
}

/* ---------- 寄班表給員工（本週或當月）---------- */
function stScheduleText_(e, from, to, shifts, leaves) {
  var days = [], d = from, wd = ['日', '一', '二', '三', '四', '五', '六'], tot = 0, lines = [];
  while (d <= to) {
    var mine = shifts.filter(function (s) { return s.e === e.id && s.d === d; });
    var lv = leaves.some(function (l) { return l.e === e.id && l.status === '核准' && l.start <= d && l.end >= d; });
    if (mine.length || lv) {
      var md = Number(d.slice(5, 7)) + '/' + Number(d.slice(8, 10)) + '（' + wd[stDow_(d)] + '）';
      lines.push(md + '　' + (lv ? '請假' : '') + mine.map(function (s) { tot += (stMin_(s.t) - stMin_(s.s) + 1440) % 1440; return s.n + ' ' + s.s + '–' + s.t; }).join('、'));
    }
    d = stAdd_(d, 1);
  }
  return { lines: lines, mins: tot };
}
/** scope = 'week' | 'month'；base = 該週／該月內任一天；ids = 員工編號陣列（空＝全部在職員工） */
function stScheduleMail(scope, base, ids, key) {
  stOwner_(key, true);
  if (!stDayOk_(base)) throw new Error('日期不正確');
  var from, to, label;
  if (scope === 'month') {
    from = base.slice(0, 8) + '01';
    var nx = new Date(Date.UTC(Number(base.slice(0, 4)), Number(base.slice(5, 7)), 1)); to = stAdd_(nx.toISOString().slice(0, 10), -1);
    label = Number(base.slice(5, 7)) + ' 月班表';
  } else { from = stWeekStart_(base); to = stAdd_(from, 6); label = from.slice(5).replace('-', '/') + '～' + to.slice(5).replace('-', '/') + ' 這週班表'; }
  var emps = stEmps_().filter(function (e) { return e.status === '在職' && (!ids || !ids.length || ids.indexOf(e.id) >= 0); });
  var shifts = stRows_('shift').map(function (r) { return { d: stStr_(r['日期']), e: String(r['員工編號']), n: String(r['班別']), s: stT_(r['開始']), t: stT_(r['結束']) }; }).filter(function (s) { return s.d >= from && s.d <= to; });
  var leaves = stLeaves_(), sent = [], skipped = [];
  var todo = emps.filter(function (e) {
    if (!emailOk_(e.email)) { skipped.push(e.name + '（沒有電子郵件）'); return false; }
    var t = stScheduleText_(e, from, to, shifts, leaves);
    if (!t.lines.length) { skipped.push(e.name + '（這段時間沒有班）'); return false; }
    return true;
  });
  if (todo.length > stMailLeft_() - 2) throw new Error('今天的寄信額度不夠（還剩 ' + stMailLeft_() + ' 封），請明天再寄或減少人數');
  var clock = stClockUrl_();
  todo.forEach(function (e) {
    var t = stScheduleText_(e, from, to, shifts, leaves);
    mail_(e.email, '【' + stShopName_() + '】' + e.name + ' 的' + label,
      e.name + ' 你好，以下是你的' + label + '：\n\n' + t.lines.join('\n') + '\n\n合計約 ' + (Math.round(t.mins / 6) / 10) + ' 小時（請假日不計）。' +
      (clock ? '\n\n隨時可以在這裡看班表、打卡、請假：\n' + clock : '') + '\n\n若有問題請聯絡店長。', stSchedMailO_(e, label, t, clock, false));
    sent.push(e.name);
  });
  cLog_(CTX.shopId, 'owner', '寄班表', '成功', label + '：' + sent.length + ' 人');
  return { sent: sent, skipped: skipped, label: label };
}

/* ---------- 預期排班：自動提醒夥伴填「方便上班的日子」→ 店主看全部、自行協調 → 一鍵寄出班表 ----------
   夥伴只看得到、只改得到自己填的；填寫連結是 45 天的個人通行證（內含期間），重設專屬連結會讓它一起失效。 */
function stPad_(n) { return (n < 10 ? '0' : '') + n; }
function stMd_(d) { return Number(d.slice(5, 7)) + '/' + Number(d.slice(8, 10)); }
function stMonthEnd_(day) { return new Date(Date.UTC(Number(day.slice(0, 4)), Number(day.slice(5, 7)), 0)).toISOString().slice(0, 10); }
/** 下一個要排的期間：month＝下個月；biweek＝從下週一起算兩週 */
function stAvailPeriod_(today, mode) {
  if (mode === 'biweek') {
    var f = stAdd_(stWeekStart_(today), 7);
    return { id: 'b:' + f, mode: 'biweek', from: f, to: stAdd_(f, 13), label: stMd_(f) + '～' + stMd_(stAdd_(f, 13)) + ' 兩週' };
  }
  var y = Number(today.slice(0, 4)), m = Number(today.slice(5, 7)); if (m === 12) { y++; m = 1; } else m++;
  var f2 = y + '-' + stPad_(m) + '-01';
  return { id: 'm:' + f2.slice(0, 7), mode: 'month', from: f2, to: stMonthEnd_(f2), label: m + ' 月' };
}
function stPeriodById_(id) {
  var m = /^([mb]):(\d{4}-\d{2}(?:-\d{2})?)$/.exec(String(id || '')); if (!m) return null;
  if (m[1] === 'b') { if (!stDayOk_(m[2])) return null; return { id: id, mode: 'biweek', from: m[2], to: stAdd_(m[2], 13), label: stMd_(m[2]) + '～' + stMd_(stAdd_(m[2], 13)) + ' 兩週' }; }
  var f = m[2] + '-01'; if (!stDayOk_(f)) return null;
  return { id: id, mode: 'month', from: f, to: stMonthEnd_(f), label: Number(m[2].slice(5)) + ' 月' };
}
function stAvailRows_(perId) {
  return stRows_('avail').filter(function (r) { return String(r['期間']) === perId; })
    .map(function (r) { return { e: String(r['員工編號']), days: stStr_(r['日期']).split(',').filter(String), note: String(r['備註'] || ''), at: stStr_(r['提交時間']), _r: r._r }; });
}
function stAvailToken_(e, per) { return tokenMake_({ s: (typeof saas_ === 'function' && saas_()) ? CTX.shopId : '', r: 'emp', u: e.id, v: e.pinv, p: per.id }, 45); }
function stAvailUrl_(e, per) {
  var web = tWebUrl_(); if (!web) return '';
  return web + (typeof saas_ === 'function' && saas_() ? '?s=' + CTX.shopId + '&p=avail&jc=' : '?p=avail&jc=') + stAvailToken_(e, per);
}
/** 今天該不該寄提醒：month＝每月固定幾號；biweek＝每隔一個週一 */
function stAvailDue_(cfg, today) {
  if (!cfg.avail.on) return false;
  if (cfg.avail.mode === 'biweek') return stDow_(today) === 1 && Math.round((Date.parse(today + 'T00:00:00Z') - Date.parse('2026-01-05T00:00:00Z')) / 604800000) % 2 === 0;
  return Number(today.slice(8, 10)) === cfg.avail.day;
}
/* 班表信的版型：日期與班別排成表格，最後一列合計時數 */
function stSchedMailO_(e, label, t, url, att) {
  if (typeof mailHtml_ !== 'function') return null;
  var sh = mailShop_(), rows = t.lines.map(function (l) { var p = l.split('　'); var r = [p[0], p.slice(1).join(' ') || '-']; if (/^請假/.test(r[1])) r.off = 1; return r; });
  return { brand: 'shop', shop: sh, eyebrow: 'SCHEDULE', title: e.name + '的' + label, preheader: '共 ' + t.lines.length + ' 天、合計約 ' + (Math.round(t.mins / 6) / 10) + ' 小時',
    blocks: [mkP_(mkEsc_(e.name) + ' 你好，以下是你的' + mkEsc_(label) + '：'), mkTable_(['日期', '班別與時間'], rows, '合計約 ' + (Math.round(t.mins / 6) / 10) + ' 小時（請假日不計）')]
      .concat(att ? [mkP_('<span style="font-size:14px;color:' + MK.mute + '">完整班表在附件：PDF 可以列印，圖檔可以直接轉傳 LINE。</span>')] : [])
      .concat(url ? [mkBtn_('打開我的員工入口', url, sh.accent || MK.amber, mkOn_(sh.accent || MK.amber))] : []),
    why: '店長寄出班表時，排到班的人都會收到。有問題請聯絡店長。' };
}
function stAvailMail_(e, per) {
  var url = stAvailUrl_(e, per);
  mail_(e.email, '【' + stShopName_() + '】請填 ' + per.label + ' 方便上班的日子',
    e.name + ' 你好，\n\n' + stShopName_() + ' 要排 ' + per.label + '（' + per.from + ' ～ ' + per.to + '）的班了。請點下面的連結，選你方便上班的日子（只有你和店長看得到你選的）：\n' + url + '\n\n店長會依大家的預期排好班表，確定後再寄給你。如果這段時間有特別的事，可以在備註寫。', null, { brand: 'shop', btn: '選我方便上班的日子' });
}
/** 每小時掃描時呼叫：到了設定的日子（台北時間 9 點後）就寄給所有在職、有信箱的員工；同一個期間只寄一次 */
function stAvailRemind_() {
  var cfg = stCfg_(), today = stToday_();
  if (!stAvailDue_(cfg, today) || Number(stClock_().slice(0, 2)) < 9) return { sent: [] };
  if (typeof saas_ === 'function' && saas_() && CTX.lic && CTX.lic.mode === 'readonly') return { sent: [] };
  var per = stAvailPeriod_(today, cfg.avail.mode), last = tGetJson_('st_avail_last', null);
  if (last && last.id === per.id) return { sent: [], period: per.id };
  var list = stEmps_().filter(function (e) { return e.status === '在職' && emailOk_(e.email); });
  if (list.length > stMailLeft_() - 3) return { sent: [], err: '寄信額度不夠' };
  var sent = []; list.forEach(function (e) { try { stAvailMail_(e, per); sent.push(e.name); } catch (err) {} });
  tSetJson_('st_avail_last', { id: per.id, at: today });
  try {
    var to = typeof notifyTo_ === 'function' ? notifyTo_('avail') : (typeof shopCfg_ === 'function' ? shopCfg_().notifyEmail : '');
    if (to && emailOk_(to) && sent.length) mail_(to, '【預期排班】已提醒 ' + sent.length + ' 位夥伴填 ' + per.label, '系統已寄出「請填方便上班的日子」給：' + sent.join('、') + '\n\n大家填好後，到「人員與班表」→「班表」可以看到每個人的預期，再自行協調排班。');
  } catch (err2) {}
  return { sent: sent, period: per.id };
}
/** 店主手動提醒：只寄給「這個期間還沒回覆」的人 */
function stAvailRemindNow(key) {
  stOwner_(key, true);
  var cfg = stCfg_(), per = stAvailPeriod_(stToday_(), cfg.avail.mode), done = {};
  stAvailRows_(per.id).forEach(function (r) { done[r.e] = 1; });
  var list = stEmps_().filter(function (e) { return e.status === '在職' && !done[e.id]; }), sent = [], skipped = [];
  var mailable = list.filter(function (e) { if (emailOk_(e.email)) return true; skipped.push(e.name + '（沒有電子郵件）'); return false; });
  if (mailable.length > stMailLeft_() - 2) throw new Error('今天的寄信額度不夠（還剩 ' + stMailLeft_() + ' 封）');
  mailable.forEach(function (e) { stAvailMail_(e, per); sent.push(e.name); });
  return { sent: sent, skipped: skipped, period: per.label };
}
function stAvailCtx_(token, write) {
  var e = stEmpCtx_(token, !!write), p = tokenRead_(token), per = stPeriodById_(p.p);
  if (!per) throw new Error('這個連結沒有指定期間，請向店長重新索取');
  return { e: e, per: per };
}
/** 夥伴打開填寫頁：只回傳自己的選擇 */
function stAvailInfo(token) {
  var c = stAvailCtx_(token), mine = stAvailRows_(c.per.id).filter(function (r) { return r.e === c.e.id; })[0];
  return { name: c.e.name, shop: stShopName_(), period: c.per, days: mine ? mine.days : [], note: mine ? mine.note : '', replied: !!mine, open: stToday_() < c.per.from, today: stToday_() };
}
function stAvailSubmit(token, days, note) {
  var c = stAvailCtx_(token, true), today = stToday_();
  if (today >= c.per.from) throw new Error('這個期間已經開始了，要調整請直接跟店長說');
  if (!Array.isArray(days)) throw new Error('資料格式不對');
  var clean = {}; days.forEach(function (d) { if (stDayOk_(d) && d >= c.per.from && d <= c.per.to) clean[d] = 1; });
  var list = Object.keys(clean).sort();
  return stLocked_(function () {
    var old = stAvailRows_(c.per.id).filter(function (r) { return r.e === c.e.id; }).map(function (r) { return r._r; });
    if (old.length) stDel_('avail', old);
    stPut_('avail', 0, [c.per.id, c.e.id, list.join(','), tClean_(note, 100), today + ' ' + stClock_()]);
    return { ok: true, count: list.length };
  });
}
function stAvailSummary_(cfg) {
  var per = stAvailPeriod_(stToday_(), cfg.avail.mode), rows = stAvailRows_(per.id), map = {}, act = stEmps_().filter(function (e) { return e.status === '在職'; });
  rows.forEach(function (r) { map[r.e] = { days: r.days, note: r.note, at: r.at }; });
  return { period: per, replied: act.filter(function (e) { return map[e.id]; }).length, total: act.length, map: map, on: cfg.avail.on, mode: cfg.avail.mode, day: cfg.avail.day };
}
function stAvailList(key, perId) {
  stOwner_(key, false);
  var cfg = stCfg_(), per = (perId && stPeriodById_(perId)) || stAvailPeriod_(stToday_(), cfg.avail.mode), rows = stAvailRows_(per.id), em = {};
  stEmps_().forEach(function (e) { em[e.id] = e; });
  var got = {}; rows.forEach(function (r) { got[r.e] = 1; });
  return { period: per, rows: rows.filter(function (r) { return em[r.e]; }).map(function (r) { return { e: r.e, name: em[r.e].name, days: r.days, note: r.note, at: r.at }; }),
    missing: stEmps_().filter(function (e) { return e.status === '在職' && !got[e.id]; }).map(function (e) { return { e: e.id, name: e.name, hasMail: emailOk_(e.email) }; }) };
}
function availPage_(sid, jc) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  var t = HtmlService.createTemplateFromFile('Avail');
  t.boot = tJs_({ sid: (typeof saas_ === 'function' && saas_() ? CTX.shopId : ''), brand: typeof brand_ === 'function' ? brand_() : {}, tok: String(jc || '') });
  return t.evaluate().setTitle('預期排班')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/* ---------- 班表輸出：資料給前端畫 PDF／1:1 圖檔，確定後一鍵寄給員工（可附檔）---------- */
function stScheduleRange_(scope, base) {
  if (!stDayOk_(base)) throw new Error('日期不正確');
  if (scope === 'month') { var f = base.slice(0, 8) + '01'; return { from: f, to: stMonthEnd_(f), label: Number(base.slice(5, 7)) + ' 月班表' }; }
  if (scope === 'biweek') { var f2 = stWeekStart_(base); return { from: f2, to: stAdd_(f2, 13), label: stMd_(f2) + '～' + stMd_(stAdd_(f2, 13)) + ' 兩週班表' }; }
  var f3 = stWeekStart_(base); return { from: f3, to: stAdd_(f3, 6), label: stMd_(f3) + '～' + stMd_(stAdd_(f3, 6)) + ' 這週班表' };
}
/** 前端要畫班表圖用：指定範圍的員工、班與請假 */
function stScheduleData(scope, base, key) {
  stOwner_(key, false);
  var r = stScheduleRange_(scope, base), emps = stEmps_().filter(function (e) { return e.status === '在職'; });
  var shifts = stRows_('shift').map(function (x) { return { d: stStr_(x['日期']), e: String(x['員工編號']), n: String(x['班別']), s: stT_(x['開始']), t: stT_(x['結束']) }; }).filter(function (s) { return s.d >= r.from && s.d <= r.to; });
  var leaves = stLeaves_().filter(function (l) { return l.status === '核准' && l.end >= r.from && l.start <= r.to; }).map(function (l) { return { e: l.e, start: l.start, end: l.end }; });
  return { from: r.from, to: r.to, label: r.label, shop: stShopName_(), emps: emps.map(function (e) { return { id: e.id, name: e.name, hasMail: emailOk_(e.email) }; }), shifts: shifts, leaves: leaves };
}
function stMailAtt_(to, subject, body, blobs, o) {
  if (typeof mailSend_ === 'function') return mailSend_(to, subject, body, o, { brand: 'shop', attachments: blobs });
  MailApp.sendEmail({ to: to, subject: subject, body: body, name: typeof productName_ === 'function' ? productName_() : '', attachments: blobs });
}
/** 一鍵寄班表給員工 Email。files = {pdf:{b64}, png:{b64}}（前端畫好的），沒給就只寄文字。ids 空白＝全部在職且有班的人 */
function stScheduleSend(scope, base, ids, files, key) {
  stOwner_(key, true);
  var r = stScheduleRange_(scope, base), from = r.from, to = r.to, label = r.label;
  var emps = stEmps_().filter(function (e) { return e.status === '在職' && (!ids || !ids.length || ids.indexOf(e.id) >= 0); });
  var shifts = stRows_('shift').map(function (x) { return { d: stStr_(x['日期']), e: String(x['員工編號']), n: String(x['班別']), s: stT_(x['開始']), t: stT_(x['結束']) }; }).filter(function (s) { return s.d >= from && s.d <= to; });
  var leaves = stLeaves_(), sent = [], skipped = [], blobs = [];
  files = files || {};
  var tag = from.replace(/-/g, '') + '_' + to.replace(/-/g, '');
  if (files.pdf && files.pdf.b64) { var pb = Utilities.base64Decode(String(files.pdf.b64)); if (pb.length > 6 * 1024 * 1024) throw new Error('PDF 太大'); blobs.push(Utilities.newBlob(pb, 'application/pdf', '班表_' + tag + '.pdf')); }
  if (files.png && files.png.b64) { var gb = Utilities.base64Decode(String(files.png.b64)); if (gb.length > 6 * 1024 * 1024) throw new Error('圖檔太大'); blobs.push(Utilities.newBlob(gb, 'image/png', '班表_' + tag + '_1x1.png')); }
  var todo = emps.filter(function (e) {
    if (!emailOk_(e.email)) { skipped.push(e.name + '（沒有電子郵件）'); return false; }
    if (!stScheduleText_(e, from, to, shifts, leaves).lines.length) { skipped.push(e.name + '（這段時間沒有班）'); return false; }
    return true;
  });
  if (todo.length > stMailLeft_() - 2) throw new Error('今天的寄信額度不夠（還剩 ' + stMailLeft_() + ' 封），請明天再寄或減少人數');
  var portal = stClockUrl_();
  todo.forEach(function (e) {
    var t = stScheduleText_(e, from, to, shifts, leaves), body = e.name + ' 你好，以下是你的' + label + '：\n\n' + t.lines.join('\n') + '\n\n合計約 ' + (Math.round(t.mins / 6) / 10) + ' 小時（請假日不計）。' + (blobs.length ? '\n\n完整班表請看附件（PDF 可列印，圖檔可直接轉傳 LINE）。' : '') + (portal ? '\n\n你的員工入口：\n' + stEmpLinkUrl_(e) : '') + '\n\n若有問題請聯絡店長。';
    var subj = '【' + stShopName_() + '】' + e.name + ' 的' + label;
    var so = stSchedMailO_(e, label, t, portal ? stEmpLinkUrl_(e) : '', blobs.length > 0);
    if (blobs.length) stMailAtt_(e.email, subj, body, blobs, so); else mail_(e.email, subj, body, so);
    sent.push(e.name);
  });
  cLog_(CTX.shopId || '', 'owner', '寄班表', '成功', label + '：' + sent.length + ' 人' + (blobs.length ? '（附檔 ' + blobs.length + '）' : ''));
  return { sent: sent, skipped: skipped, label: label, attached: blobs.length };
}

/* ---------- 徵才與面試登記 ---------- */
function stHire_() {
  var h = tGetJson_('st_hire', null) || {};
  return { open: h.open !== false, positions: Array.isArray(h.positions) && h.positions.length ? h.positions : ['外場', '內場'] };
}
function stHireSave(h, key) {
  stOwner_(key, true);
  var pos = ((h && h.positions) || []).map(function (x) { return tClean_(x, 12).trim(); }).filter(String).slice(0, 8);
  if (!pos.length) throw new Error('至少要有一個職缺名稱');
  tSetJson_('st_hire', { open: !h || h.open !== false, positions: pos });
  return stHire_();
}
function stApplyUrl_() {
  var web = tWebUrl_(); if (!web) return '';
  return web + (typeof saas_ === 'function' && saas_() ? '?s=' + CTX.shopId + '&p=apply' : '?p=apply');
}
function stApplies_() {
  return stRows_('apply').map(function (r) {
    return { id: String(r['編號']), at: stStr_(r['登記時間']), name: String(r['姓名']), phone: String(r['電話'] || ''), email: String(r['電子郵件'] || ''), pos: String(r['應徵職位'] || ''), when: String(r['希望面試時段'] || ''), intro: String(r['自我介紹'] || ''), status: String(r['狀態'] || '新登記'), note: String(r['備註'] || ''), _r: r._r };
  });
}
/** 應徵者在公開頁面登記面試（不需登入）。f = {name, phone, email, pos, when, intro, hp(蜜罐)} */
function stApplySubmit(sid, f) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  f = f || {};
  if (f.hp) return { ok: true };                                    /* 機器人填了隱藏欄位：假裝成功 */
  if (!stHire_().open) throw new Error('目前沒有招募，謝謝你的關心');
  var name = tClean_(f.name, 20).trim(), phone = tClean_(f.phone, 20).trim(), email = tClean_(f.email, 60).trim();
  if (!name) throw new Error('請填姓名');
  if (!phone && !email) throw new Error('請至少留一種聯絡方式（電話或電子郵件）');
  if (phone && !stPhoneOk_(phone)) throw new Error('電話格式不對');
  if (email && !emailOk_(email)) throw new Error('電子郵件格式不對');
  var pos = stHire_().positions.indexOf(f.pos) >= 0 ? f.pos : '不限／其他';
  var c = CacheService.getScriptCache(), dk = 'apply:' + (sid || 'x') + ':' + (phone || email), hk = 'applyn:' + (sid || 'x') + ':' + stToday_() + stClock_().slice(0, 2);
  if (c.get(dk)) throw new Error('你已經登記過了，我們會盡快聯絡你');
  var n = Number(c.get(hk) || 0); if (n >= 30) throw new Error('目前登記的人太多，請稍後再試');
  var id = stLocked_(function () {
    var nid = stNextId_('apply', 'A', 4);
    stPut_('apply', 0, [nid, stToday_() + ' ' + stClock_(), name, phone, email, pos, tClean_(f.when, 60), tClean_(f.intro, 200), '新登記', '']);
    return nid;
  });
  try { c.put(dk, '1', 21600); c.put(hk, String(n + 1), 3600); } catch (e) {}
  try {
    var to = typeof notifyTo_ === 'function' ? notifyTo_('apply') : (typeof shopCfg_ === 'function' ? shopCfg_().notifyEmail : '');
    if (to && emailOk_(to)) mail_(to, '【面試登記】' + name + ' 應徵 ' + pos, name + ' 在網路上登記面試\n職位：' + pos + '\n電話：' + (phone || '-') + '\n電子郵件：' + (email || '-') + '\n希望時段：' + (tClean_(f.when, 60) || '-') + '\n\n請到「人員與班表」→「徵才」查看並聯絡。');
  } catch (err) {}
  return { ok: true, id: id };
}
function stApplyList(key) { stOwner_(key, false); return stApplies_().sort(function (a, b) { return a.at < b.at ? 1 : -1; }); }
function stApplySet(id, status, note, key) {
  stOwner_(key, true);
  if (ST_APPLY_STATUS.indexOf(status) < 0) throw new Error('狀態不正確');
  var a = stApplies_().filter(function (x) { return x.id === String(id); })[0];
  if (!a) throw new Error('找不到這筆登記');
  stPut_('apply', a._r, [a.id, a.at, a.name, a.phone, a.email, a.pos, a.when, a.intro, status, tClean_(note, 100)]);
  return stApplyList(key);
}
/** 約面試：定下時間，狀態改「約定面試」，並寄確認信給應徵者（有電子郵件的話）；when = 'yyyy-MM-ddTHH:mm' */
function stApplyInterview(id, when, key) {
  stOwner_(key, true);
  var m = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})$/.exec(String(when || ''));
  if (!m || !stDayOk_(m[1]) || !stTimeOk_(m[2])) throw new Error('請選面試的日期與時間');
  if (m[1] < stToday_()) throw new Error('面試日期不能是過去');
  var a = stApplies_().filter(function (x) { return x.id === String(id); })[0];
  if (!a) throw new Error('找不到這筆登記');
  var text = m[1] + ' ' + m[2];
  stPut_('apply', a._r, [a.id, a.at, a.name, a.phone, a.email, a.pos, a.when, a.intro, '約定面試', '面試：' + text]);
  var mailed = false, cfg = typeof shopCfg_ === 'function' ? shopCfg_() : {};
  if (a.email && emailOk_(a.email)) {
    mail_(a.email, '【' + stShopName_() + '】面試時間確認：' + text, a.name + ' 你好，\n\n謝謝你應徵 ' + stShopName_() + ' 的「' + a.pos + '」。\n面試時間：' + text + (cfg.address ? '\n地點：' + cfg.address : '') + (cfg.phone ? '\n聯絡電話：' + cfg.phone : '') + '\n\n如果這個時間不方便，請直接回覆這封信或來電，我們再另約。期待見到你！',
      typeof mailHtml_ === 'function' ? { brand: 'shop', shop: mailShop_(), eyebrow: 'INTERVIEW', title: '面試時間確認', preheader: text + '，' + stShopName_(),
        blocks: [mkP_(mkEsc_(a.name) + ' 你好，謝謝你應徵 ' + mkEsc_(stShopName_()) + ' 的「' + mkEsc_(a.pos) + '」。'),
          mkRows_([['面試時間', text, 1], ['職位', a.pos]].concat(cfg.address ? [['地點', cfg.address]] : []).concat(cfg.phone ? [['聯絡電話', cfg.phone, 1]] : [])),
          mkP_('如果這個時間不方便，請直接回覆這封信或來電，我們再另約。期待見到你！')],
        why: '你收到這封信，是因為你在網路上登記了 ' + stShopName_() + ' 的面試。' } : null);
    mailed = true;
  }
  return { list: stApplyList(key), mailed: mailed, when: text };
}
function stApplyDelete(id, key) {
  stOwner_(key, true);
  var a = stApplies_().filter(function (x) { return x.id === String(id); })[0];
  if (a) stDel_('apply', [a._r]);
  return stApplyList(key);
}
/** 把應徵者轉成員工（姓名、電話、電子郵件帶入，PIN 由店主設定） */
function stApplyHire(id, pin, key) {
  stOwner_(key, true);
  var a = stApplies_().filter(function (x) { return x.id === String(id); })[0];
  if (!a) throw new Error('找不到這筆登記');
  stEmpSave({ name: a.name, title: a.pos === '不限／其他' ? '' : a.pos, pin: pin, email: a.email, phone: a.phone, note: '由面試登記 ' + a.id + ' 轉入' }, key);
  stApplySet(id, '錄取', a.note, key);
  var pm = stPartnerMap_();
  return { emps: stEmps_().map(function (x) { return stEmpPub_(x, pm); }) };
}

/* ---------- 打卡紀錄 ---------- */
function stShiftFor_(shifts, emp, day, time) {
  var best = null, bd = 1e9;
  shifts.forEach(function (s) {
    if (s.e !== emp || s.d !== day) return;
    var d = Math.abs(stMin_(s.s) - stMin_(time));
    if (d < bd) { bd = d; best = s; }
  });
  return best;
}
function stPunchRows_(from, to) {
  var shifts = stRows_('shift').map(function (r) { return { d: stStr_(r['日期']), e: String(r['員工編號']), s: stT_(r['開始']), t: stT_(r['結束']) }; });
  var grace = stCfg_().grace;
  return stRows_('punch').map(function (r) {
    var o = { id: String(r['編號']), d: stStr_(r['日期']), e: String(r['員工編號']), in: stT_(r['上班']), out: stT_(r['下班']), note: String(r['備註'] || ''), src: String(r['來源'] || '') };
    o.mins = o.in && o.out ? ((stMin_(o.out) - stMin_(o.in)) + 1440) % 1440 : 0;
    o.reason = o.note.indexOf('【補打卡】') === 0 ? o.note.slice(5).replace('【未下班】', '') : '';
    var sh = o.in ? stShiftFor_(shifts, o.e, o.d, o.in) : null;
    o.plan = sh ? sh.s + '–' + sh.t : '';
    o.late = sh && stMin_(o.in) - stMin_(sh.s) > grace ? stMin_(o.in) - stMin_(sh.s) : 0;
    o.early = sh && o.out && sh.t > sh.s && stMin_(sh.t) - stMin_(o.out) > grace && stMin_(o.out) < stMin_(sh.t) ? stMin_(sh.t) - stMin_(o.out) : 0;
    return o;
  }).filter(function (o) { return o.d >= from && o.d <= to; })
    .sort(function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : a.in < b.in ? 1 : -1; });
}
function stPunchList(from, to, key) {
  stOwner_(key, false);
  if (!stDayOk_(from) || !stDayOk_(to) || from > to) throw new Error('日期範圍不正確');
  if (Date.parse(to + 'T00:00:00Z') - Date.parse(from + 'T00:00:00Z') > 93 * 86400000) throw new Error('一次最多查 3 個月');
  return stPunchRows_(from, to);
}
/** 補登或修改打卡。p = {id?, d, e, in, out, note}；id 空白＝新增。 */
function stPunchFix(p, key) {
  stOwner_(key, true);
  p = p || {};
  if (!stDayOk_(p.d)) throw new Error('日期不正確');
  if (!stEmpById_(p.e)) throw new Error('找不到員工');
  if (!stTimeOk_(p.in)) throw new Error('請填上班時間（HH:mm）');
  if (p.out && !stTimeOk_(p.out)) throw new Error('下班時間格式不對');
  return stLocked_(function () {
    var cur = p.id ? stRows_('punch').filter(function (r) { return String(r['編號']) === String(p.id); })[0] : null;
    if (p.id && !cur) throw new Error('找不到這筆打卡');
    var id = cur ? String(cur['編號']) : stNextId_('punch', 'P', 5);
    stPut_('punch', cur ? cur._r : 0, [id, p.d, p.e, p.in, p.out || '', tClean_(p.note, 60), '店家補登']);
    return { id: id };
  });
}
function stPunchDelete(id, key) {
  stOwner_(key, true);
  var cur = stRows_('punch').filter(function (r) { return String(r['編號']) === String(id); })[0];
  if (cur) stDel_('punch', [cur._r]);
  return true;
}

/* ---------- 今日出勤（店主看：誰打卡了、誰還沒）與未打卡提醒 ---------- */
function stAttendance_() {
  var today = stToday_(), now = stClock_(), cfg = stCfg_(), emps = stEmps_().filter(function (e) { return e.status === '在職'; });
  var shifts = stRows_('shift').map(function (r) { return { d: stStr_(r['日期']), e: String(r['員工編號']), s: stT_(r['開始']), t: stT_(r['結束']) }; }).filter(function (s) { return s.d === today; });
  var punches = stPunchRows_(today, today), leaves = stLeaves_().filter(function (l) { return l.status === '核准' && l.start <= today && l.end >= today; });
  var list = [];
  emps.forEach(function (e) {
    var sh = shifts.filter(function (s) { return s.e === e.id; }).sort(function (a, b) { return a.s < b.s ? -1 : 1; })[0];
    if (!sh || leaves.some(function (l) { return l.e === e.id; })) return;
    var p = punches.filter(function (x) { return x.e === e.id; }).sort(function (a, b) { return a.in < b.in ? -1 : 1; })[0];
    var o = { e: e.id, name: e.name, plan: sh.s + '–' + sh.t, state: p ? (p.out ? 'done' : 'in') : 'none', in: p ? p.in : '', out: p ? p.out : '', late: p ? p.late : 0, reason: p ? p.reason : '', missing: false, hasMail: emailOk_(e.email) };
    if (!p && stMin_(now) - stMin_(sh.s) >= cfg.missMins) o.missing = true;
    list.push(o);
  });
  return { today: today, now: now, list: list, total: list.length, punched: list.filter(function (o) { return o.state !== 'none'; }).length, missing: list.filter(function (o) { return o.missing; }).length };
}
function stMailMissing_(e) {
  var url = stEmpLinkUrl_(e);
  mail_(e.email, '【' + stShopName_() + '】你今天還沒打卡', e.name + ' 你好，\n\n系統看到你今天有排班，但還沒有打卡。請盡快打卡；如果已經超過上班時間，打卡時會請你選一個補打卡原因（交通延誤、忘記打卡、臨時支援，或自己填寫）。\n\n' + (url ? '你的員工入口：\n' + url + '\n\n' : '') + '如果今天不用上班，請跟店長說一聲。', null, { brand: 'shop', btn: '打開員工入口打卡' });
}
/** 自動提醒：上班後超過設定分鐘仍沒打卡的員工（每人每天只寄一次），並寄一封彙整給店主 */
function stRemindMissing_() {
  var cfg = stCfg_(); if (!cfg.missRemind) return { sent: [], owner: false };
  if (typeof saas_ === 'function' && saas_() && CTX.lic && CTX.lic.mode === 'readonly') return { sent: [], owner: false };
  var att = stAttendance_(), c = CacheService.getScriptCache(), sent = [], names = [];
  att.list.forEach(function (o) {
    if (!o.missing) return;
    var k = ck_('stmiss') + ':' + att.today + ':' + o.e;
    if (c.get(k)) return;
    names.push(o.name);
    var e = stEmpById_(o.e);
    if (e && emailOk_(e.email) && stMailLeft_() > 5 && (typeof notifyOn_ !== 'function' || notifyOn_('missEmp'))) { try { stMailMissing_(e); sent.push(o.name); } catch (err) {} }
    try { c.put(k, '1', 43200); } catch (err) {}
  });
  var owner = false;
  if (names.length) {
    try {
      var to = typeof notifyTo_ === 'function' ? notifyTo_('miss') : (typeof shopCfg_ === 'function' ? shopCfg_().notifyEmail : '');
      if (to && emailOk_(to) && stMailLeft_() > 5) { mail_(to, '【未打卡】' + names.join('、') + '（' + att.today + ' ' + att.now + '）', '以下員工今天有排班，但超過 ' + cfg.missMins + ' 分鐘還沒打卡：\n' + names.join('、') + '\n\n已自動提醒有填電子郵件的員工：' + (sent.join('、') || '（無）') + '\n\n到「人員與班表」可以看今日出勤，也可以手動提醒。'); owner = true; }
    } catch (err) {}
  }
  return { sent: sent, names: names, owner: owner };
}
/** 店主手動提醒某位員工打卡 */
function stRemindNow(empId, key) {
  stOwner_(key, true);
  var e = stEmpById_(empId); if (!e || e.status !== '在職') throw new Error('找不到這位在職員工');
  if (!emailOk_(e.email)) throw new Error(e.name + ' 沒有填電子郵件，請改用電話或 LINE 提醒');
  if (stMailLeft_() < 3) throw new Error('今天的寄信額度用完了');
  stMailMissing_(e);
  return { sent: true, name: e.name };
}
/** 每個整點執行一次（時間驅動觸發器）：掃每一家店的提醒工作。單店模式只掃自己。 */
function stTickShop_() {
  var out = {};
  try { out.miss = stRemindMissing_(); } catch (e) { out.missErr = String(e.message || e); }
  if (typeof stAvailRemind_ === 'function') { try { out.avail = stAvailRemind_(); } catch (e2) { out.availErr = String(e2.message || e2); } }
  if (typeof tHandRemind_ === 'function') { try { out.hand = tHandRemind_(); } catch (e4) { out.handErr = String(e4.message || e4); } }
  if (typeof lgOrderRemind_ === 'function') { try { out.order = lgOrderRemind_(); } catch (e3) { out.orderErr = String(e3.message || e3); } }
  return out;
}
function sfdTick() {
  resetCtx_();
  if (!saas_()) return stTickShop_();
  var n = 0;
  allShops_().forEach(function (s) {
    if (['trial', 'pilot', 'active', 'grace'].indexOf(s.status) < 0 || !s.ssId) return;
    try { useShop_(s.id); stTickShop_(); n++; } catch (e) {}
  });
  return n;
}
function ensureTickTrigger_() {
  var has = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'sfdTick'; });
  if (!has) ScriptApp.newTrigger('sfdTick').timeBased().everyHours(1).create();
  return !has;
}

/* ---------- 請假 ---------- */
function stLeaves_() {
  return stRows_('leave').map(function (r) {
    return { id: String(r['編號']), at: stStr_(r['申請時間']), e: String(r['員工編號']), type: String(r['類別']), start: stStr_(r['開始日']), end: stStr_(r['結束日']), reason: String(r['事由'] || ''), status: String(r['狀態']), decided: stStr_(r['審核時間']), reply: String(r['回覆'] || ''), _r: r._r };
  });
}
/* ---------- 特休（勞基法第 38 條，週年制）：由到職日自動算 ----------
   滿 6 個月 3 天、滿 1 年 7 天、滿 2 年 10 天、滿 3 年 14 天、滿 5 年 15 天、滿 10 年起每年加 1 天最多 30 天。
   法規或公司制度有變動時只改 stAnnualDays_ 這一個階梯；上線前請會計確認。 */
function stMonthsBetween_(from, to) {
  var m = (Number(to.slice(0, 4)) - Number(from.slice(0, 4))) * 12 + (Number(to.slice(5, 7)) - Number(from.slice(5, 7)));
  if (Number(to.slice(8, 10)) < Number(from.slice(8, 10))) m--;
  return Math.max(m, 0);
}
function stAddMonths_(day, n) {
  var y = Number(day.slice(0, 4)), mo = Number(day.slice(5, 7)) - 1 + n, d = Number(day.slice(8, 10));
  y += Math.floor(mo / 12); mo = ((mo % 12) + 12) % 12;
  var last = new Date(Date.UTC(y, mo + 1, 0)).getUTCDate();
  var p = function (x) { return (x < 10 ? '0' : '') + x; };
  return y + '-' + p(mo + 1) + '-' + p(Math.min(d, last));
}
function stAnnualDays_(hired, on) {
  var m = stMonthsBetween_(hired, on), y = Math.floor(m / 12);
  if (m < 6) return 0; if (y < 1) return 3; if (y < 2) return 7; if (y < 3) return 10; if (y < 5) return 14; if (y < 10) return 15;
  return Math.min(15 + (y - 9), 30);
}
function stLeaveDaysCount_(l) { return Math.round((Date.parse(l.end + 'T00:00:00Z') - Date.parse(l.start + 'T00:00:00Z')) / 86400000) + 1; }
function stAnnual_(e, today) {
  if (!e.hired || !stDayOk_(e.hired)) return { ok: false };
  var m = stMonthsBetween_(e.hired, today), y = Math.floor(m / 12), days = stAnnualDays_(e.hired, today);
  var from = m < 6 ? e.hired : m < 12 ? stAddMonths_(e.hired, 6) : stAddMonths_(e.hired, 12 * y);
  var to = m < 6 ? stAddMonths_(e.hired, 6) : m < 12 ? stAddMonths_(e.hired, 12) : stAddMonths_(e.hired, 12 * (y + 1));
  var used = 0;
  stLeaves_().forEach(function (l) { if (l.e === e.id && l.type === '特休' && l.status === '核准' && l.start >= from && l.start < to) used += stLeaveDaysCount_(l); });
  return { ok: true, hired: e.hired, years: y, months: m, days: days, used: used, left: Math.max(days - used, 0), from: from, to: to };
}
function stLeaveDecide(id, ok, reply, key) {
  stOwner_(key, true);
  return stLocked_(function () {
    var l = stLeaves_().filter(function (x) { return x.id === String(id); })[0];
    if (!l) throw new Error('找不到這筆請假');
    if (l.status !== '待審') throw new Error('這筆已經處理過了（' + l.status + '）');
    if (ok && l.type === '特休') {
      var e0 = stEmpById_(l.e), an = e0 ? stAnnual_(e0, l.start) : { ok: false };
      if (an.ok && stLeaveDaysCount_(l) > an.left) throw new Error('特休不夠：目前剩 ' + an.left + ' 天，這筆要 ' + stLeaveDaysCount_(l) + ' 天');
    }
    stPut_('leave', l._r, [l.id, l.at, l.e, l.type, l.start, l.end, l.reason, ok ? '核准' : '駁回', stToday_() + ' ' + stClock_(), tClean_(reply, 60)]);
    try {
      var em = stEmpById_(l.e);
      if (em && emailOk_(em.email) && stMailLeft_() > 3) {
        var an2 = l.type === '特休' ? stAnnual_(em, l.start) : null;
        mail_(em.email, '【' + stShopName_() + '】你的' + l.type + (ok ? '已核准' : '被退回'),
          em.name + ' 你好，\n\n你申請的' + l.type + '（' + l.start + (l.end !== l.start ? ' ～ ' + l.end : '') + '）' + (ok ? '已經核准。' : '沒有通過。') +
          (tClean_(reply, 60) ? '\n店長回覆：' + tClean_(reply, 60) : '') + (ok && an2 && an2.ok ? '\n目前特休剩 ' + an2.left + ' 天。' : '') + '\n\n有問題請跟店長聯絡。',
          typeof mailHtml_ === 'function' ? { brand: 'shop', shop: mailShop_(), eyebrow: 'LEAVE', title: '你的' + l.type + (ok ? '已核准' : '沒有通過'), preheader: l.start + (l.end !== l.start ? ' ～ ' + l.end : ''),
            blocks: [mkP_(mkEsc_(em.name) + ' 你好，你申請的' + mkEsc_(l.type) + (ok ? '<b>已經核准</b>。' : '<b>沒有通過</b>。')),
              mkRows_([['假別', l.type], ['日期', l.start + (l.end !== l.start ? ' ～ ' + l.end : ''), 1]].concat(tClean_(reply, 60) ? [['店長回覆', tClean_(reply, 60)]] : []).concat(ok && an2 && an2.ok ? [['特休剩餘', an2.left + ' 天', 1]] : [])),
              mkP_('有問題請跟店長聯絡。')], why: '你收到這封信，是因為你在員工入口申請了請假。' } : null);
      }
    } catch (err) {}
    return stLeaves_().filter(function (x) { return x.status === '待審'; });
  });
}
function stLeaveList(from, to, key) {
  stOwner_(key, false);
  if (!stDayOk_(from) || !stDayOk_(to)) throw new Error('日期範圍不正確');
  return stLeaves_().filter(function (l) { return l.end >= from && l.start <= to; }).sort(function (a, b) { return a.start < b.start ? 1 : -1; });
}

/* ---------- 文件下載區 ---------- */
function stDocs_() {
  return stRows_('doc').map(function (r) {
    return { id: String(r['編號']), title: String(r['標題']), cat: String(r['分類']), fileId: String(r['檔案編號']), url: String(r['連結']), aud: String(r['對象']), at: stStr_(r['上傳時間']), name: String(r['檔名']), kb: Number(r['大小KB']) || 0, must: String(r['必讀']) === '是', _r: r._r };
  }).sort(function (a, b) { return a.cat < b.cat ? -1 : a.cat > b.cat ? 1 : a.title < b.title ? -1 : 1; });
}
function stDocPub_(d) { return { id: d.id, title: d.title, cat: d.cat, url: d.url, name: d.name, kb: d.kb, at: d.at, must: !!d.must }; }
/** 每份文件幾位員工看完了（店主看）；每位員工自己看完了哪些（員工看） */
function stDocReadMap_() {
  var m = {};
  stRows_('docread').forEach(function (r) { var d = String(r['文件編號']), e = String(r['員工編號']); (m[d] = m[d] || {})[e] = stStr_(r['時間']); });
  return m;
}
/** 上傳文件。b64 = 檔案內容；aud = '員工'（只有員工打卡頁看得到）或 '公開'（顧客頁也顯示） */
function stDocAdd(b64, fileName, title, cat, aud, key) {
  stOwner_(key, true);
  var name = tClean_(fileName, 80).replace(/[\\\/:*?"|]/g, '_') || '文件', ext = (name.split('.').pop() || '').toLowerCase();
  if (!ST_DOC_EXT[ext]) throw new Error('不支援這種檔案（可用：PDF、圖片、Word、Excel、PowerPoint、文字檔）');
  var bytes = Utilities.base64Decode(String(b64 || ''));
  if (!bytes.length) throw new Error('檔案是空的');
  if (bytes.length > ST_DOC_MAX) throw new Error('檔案太大（上限 10MB）');
  if (stDocs_().length >= 100) throw new Error('文件最多 100 份，請先刪除不用的');
  var file = tFolder_().createFile(Utilities.newBlob(bytes, ST_DOC_EXT[ext], name));
  try { file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch (e) {}
  var id = stNextId_('doc', 'D', 3);
  stPut_('doc', 0, [id, tClean_(title, 40) || name, ST_DOC_CATS.indexOf(cat) >= 0 ? cat : '其他', file.getId(), file.getUrl(), aud === '公開' ? '公開' : '員工', stToday_() + ' ' + stClock_(), name, Math.ceil(bytes.length / 1024), '']);
  return stDocs_();
}
function stDocSet(id, title, cat, aud, key) {
  stOwner_(key, true);
  var d = stDocs_().filter(function (x) { return x.id === String(id); })[0];
  if (!d) throw new Error('找不到這份文件');
  stPut_('doc', d._r, [d.id, tClean_(title, 40) || d.title, ST_DOC_CATS.indexOf(cat) >= 0 ? cat : d.cat, d.fileId, d.url, aud === '公開' ? '公開' : '員工', d.at, d.name, d.kb, d.must ? '是' : '']);
  return stDocs_();
}
/** 設為「必讀」（員工入口會標出來，並統計誰看完了） */
function stDocMust(id, on, key) {
  stOwner_(key, true);
  var d = stDocs_().filter(function (x) { return x.id === String(id); })[0];
  if (!d) throw new Error('找不到這份文件');
  stPut_('doc', d._r, [d.id, d.title, d.cat, d.fileId, d.url, d.aud, d.at, d.name, d.kb, on ? '是' : '']);
  return stDocs_();
}
/** 員工按「我看完了」：記下時間，進度由系統統計 */
function stDocRead(token, id) {
  var e = stEmpCtx_(token, true), d = stDocs_().filter(function (x) { return x.id === String(id); })[0];
  if (!d) throw new Error('找不到這份文件');
  var m = stDocReadMap_();
  if (!(m[d.id] && m[d.id][e.id])) stPut_('docread', 0, [d.id, e.id, stToday_() + ' ' + stClock_()]);
  return { ok: true };
}
function stDocDelete(id, key) {
  stOwner_(key, true);
  var d = stDocs_().filter(function (x) { return x.id === String(id); })[0];
  if (d) {
    try { DriveApp.getFileById(d.fileId).setTrashed(true); } catch (e) {}
    stDel_('doc', [d._r]);
  }
  return stDocs_();
}
/** 顧客頁用（不需登入）：只列「公開」的文件 */
function stPublicDocs_() {
  try { return stDocs_().filter(function (d) { return d.aud === '公開'; }).map(stDocPub_); } catch (e) { return []; }
}

/* ================= 員工端（姓名＋PIN） ================= */
function stClockRoster(sid) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  return stEmps_().filter(function (e) { return e.status === '在職' && e.hash; }).map(function (e) { return { id: e.id, name: e.name }; });
}
function stEmpLogin(sid, empId, pin) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  var lk = 'stpin:' + (sid || 'x') + ':' + empId;
  if (lockedOut_(lk)) throw new Error(LOCK_MSG);
  var e = stEmpById_(empId);
  if (!e || e.status !== '在職' || !e.hash || stPinHash_(String(pin || '').trim(), e.id) !== e.hash) {
    failBump_(lk);
    throw new Error('PIN 不正確');
  }
  failClear_(lk);
  return { token: tokenMake_({ s: (typeof saas_ === 'function' && saas_()) ? CTX.shopId : '', r: 'emp', u: e.id, v: e.pinv }, 14), name: e.name };
}
function stEmpCtx_(token, write) {
  var p = tokenRead_(token);
  if (p.r !== 'emp') throw new Error('請重新登入');
  if (typeof saas_ === 'function' && saas_()) {
    useShop_(p.s);
    if (write && CTX.lic && CTX.lic.mode === 'readonly') throw new Error(CTX.lic.msg);
  }
  var e = stEmpById_(p.u);
  if (!e || e.status !== '在職' || e.pinv !== String(p.v)) throw new Error('登入已失效，請重新登入');
  return e;
}
function stOpenPunch_(empId) {
  var today = stToday_(), y = stAdd_(today, -1), found = null;
  stRows_('punch').forEach(function (r) {
    if (String(r['員工編號']) !== empId || stT_(r['下班']) !== '' || String(r['備註'] || '').indexOf('【未下班】') >= 0) return;
    var d = stStr_(r['日期']);
    if (d === today || d === y) { if (!found || d > found.d) found = { d: d, in: stT_(r['上班']), id: String(r['編號']), _r: r._r, row: r }; }
  });
  return found;
}
function stMyShifts_(empId, from, to) {
  return stRows_('shift').filter(function (r) { var d = stStr_(r['日期']); return String(r['員工編號']) === empId && d >= from && d <= to; })
    .map(function (r) { return { d: stStr_(r['日期']), n: String(r['班別']), s: stT_(r['開始']), t: stT_(r['結束']), note: String(r['備註'] || '') }; })
    .sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : a.s < b.s ? -1 : 1; });
}
/** 今天打卡的狀態：none＝還沒打卡、working＝已打卡（上班中）、done＝已完成。needReason＝現在打卡已超過上班時間，要選補打卡原因 */
function stTodayStatus_(e, open, today, now) {
  var mine = stPunchRows_(today, today).filter(function (p) { return p.e === e.id; }).sort(function (a, b) { return a.in < b.in ? -1 : 1; });
  var st = { state: 'none', in: '', out: '', needReason: false, lateMins: 0, day: today };
  if (open) { st.state = 'working'; st.in = open.in; st.day = open.d; }
  else if (mine.length) { var last = mine[mine.length - 1]; st.state = 'done'; st.in = mine[0].in; st.out = last.out; }
  if (st.state === 'none') {
    var shifts = stMyShifts_(e.id, today, today), cfg = stCfg_();
    if (shifts.length) {
      var late = stMin_(now) - stMin_(shifts[0].s);
      if (late > cfg.grace) { st.needReason = true; st.lateMins = late; }
    }
  }
  return st;
}
/** 員工在入口按「已叫貨」（只能按自己負責的廠商） */
function stOrderDone(token, vid) {
  var e = stEmpCtx_(token, true);
  var v = lgVendors_().filter(function (x) { return x.id === String(vid); })[0];
  if (!v) throw new Error('找不到這家廠商');
  if (v.assignee !== e.name) throw new Error('這家不是你負責的');
  lgOrderMark_(v.id, e.name);
  return { ok: true };
}
/** 員工在入口把交接事項標成處理完成 */
function stHandDone(token, id) {
  var e = stEmpCtx_(token, true);
  tHandMark_(id, e.name);
  return { ok: true };
}
function stEmpHome(token) {
  var e = stEmpCtx_(token, false), today = stToday_();
  var open = stOpenPunch_(e.id), recent = stPunchRows_(stAdd_(today, -14), today).filter(function (p) { return p.e === e.id; });
  var cfg = typeof shopCfg_ === 'function' ? shopCfg_() : {}, scfg = stCfg_();
  return {
    emp: { id: e.id, name: e.name, title: e.title, hired: e.hired }, shop: cfg.name || '', today: today, now: stClock_(),
    open: open ? { d: open.d, in: open.in } : null, status: stTodayStatus_(e, open, today, stClock_()), reasons: scfg.reasons, annual: stAnnual_(e, today),
    hand: tListHandover_().filter(function (h) { return h.status === '待處理'; }).slice(0, 20).map(function (h) { return { id: h.id, day: h.day, shift: h.shift, who: h.who, text: h.text, prio: h.prio, to: h.to, mine: h.to === e.name }; }),
    shifts: stMyShifts_(e.id, today, stAdd_(today, 20)),
    punches: recent.slice(0, 20).map(function (p) { return { d: p.d, in: p.in, out: p.out, mins: p.mins, late: p.late, reason: p.reason, missed: !p.out && p.note.indexOf('【未下班】') >= 0 }; }),
    leaves: stLeaves_().filter(function (l) { return l.e === e.id; }).sort(function (a, b) { return a.start < b.start ? 1 : -1; }).slice(0, 20)
      .map(function (l) { return { id: l.id, type: l.type, start: l.start, end: l.end, reason: l.reason, status: l.status, reply: l.reply }; }),
    docs: (function () { var rm = stDocReadMap_(); return stDocs_().map(function (d) { var p = stDocPub_(d); p.read = !!(rm[d.id] && rm[d.id][e.id]); return p; }); })(),
    orders: typeof lgOrders_ === 'function' ? lgOrdersFor_(e.name, today) : { today: [], overdue: [] }, leaveTypes: ST_LEAVE_TYPES
  };
}
/** 打卡。kind 可省略（沒上班就是上班、已上班就是下班）；超過上班時間（寬限之後）才打卡，要帶 reason（補打卡原因，可用選項或自填） */
function stPunch(token, kind, reason) {
  var e = stEmpCtx_(token, true);
  return stLocked_(function () {
    var today = stToday_(), now = stClock_(), open = stOpenPunch_(e.id);
    if (!kind) kind = open ? 'out' : 'in';
    if (kind === 'in') {
      if (open && open.d === today) throw new Error('你已經在 ' + open.in + ' 上班打卡了');
      var st = stTodayStatus_(e, null, today, now), why = tClean_(reason, 30).trim();
      if (st.needReason && !why) throw new Error('需要原因：已超過上班時間 ' + st.lateMins + ' 分鐘，請選補打卡原因');
      var note = st.needReason ? '【補打卡】' + why : '';
      if (open) stPut_('punch', open._r, [open.id, open.d, e.id, open.in, '', (String(open.row['備註'] || '') + '【未下班】').slice(0, 60), String(open.row['來源'] || '員工打卡')]);
      stPut_('punch', 0, [stNextId_('punch', 'P', 5), today, e.id, now, '', note, '員工打卡']);
      return { ok: true, kind: 'in', time: now, name: e.name, late: st.needReason ? st.lateMins : 0, reason: st.needReason ? why : '', warn: open ? '昨天 ' + open.in + ' 的班沒有下班打卡，請跟店長說一聲補登。' : '' };
    }
    if (kind === 'out') {
      if (!open) throw new Error('還沒有上班打卡，不能下班打卡');
      var r = open.row;
      stPut_('punch', open._r, [open.id, open.d, e.id, open.in, now, String(r['備註'] || ''), String(r['來源'] || '員工打卡')]);
      return { ok: true, kind: 'out', time: now, name: e.name, from: open.in };
    }
    throw new Error('不支援的操作');
  });
}
function stLeaveSubmit(token, l) {
  var e = stEmpCtx_(token, true);
  l = l || {};
  var today = stToday_(), type = ST_LEAVE_TYPES.indexOf(l.type) >= 0 ? l.type : '';
  if (!type) throw new Error('請選請假類別');
  if (!stDayOk_(l.start) || !stDayOk_(l.end)) throw new Error('請選請假日期');
  if (l.end < l.start) throw new Error('結束日不能早於開始日');
  if (l.start < stAdd_(today, -7)) throw new Error('只能申請 7 天內或之後的假；更早的請跟店長說');
  if (l.end > stAdd_(today, 366)) throw new Error('日期太遠了');
  if (Date.parse(l.end + 'T00:00:00Z') - Date.parse(l.start + 'T00:00:00Z') > 30 * 86400000) throw new Error('一次最多申請 31 天');
  var reason = tClean_(l.reason, 100).trim();
  if (type === '特休') {
    var an = stAnnual_(e, l.start);
    if (!an.ok) throw new Error('店長還沒填你的到職日，沒辦法算特休，請先跟店長說');
    var pend = 0; stLeaves_().forEach(function (x) { if (x.e === e.id && x.type === '特休' && x.status === '待審' && x.start >= an.from && x.start < an.to) pend += stLeaveDaysCount_(x); });
    var need = stLeaveDaysCount_({ start: l.start, end: l.end });
    if (need > an.left - pend) throw new Error('特休不夠：目前剩 ' + an.left + ' 天' + (pend ? '（另有 ' + pend + ' 天待審）' : '') + '，這次要 ' + need + ' 天');
  }
  return stLocked_(function () {
    var mine = stLeaves_().filter(function (x) { return x.e === e.id && (x.status === '待審' || x.status === '核准'); });
    if (mine.some(function (x) { return x.end >= l.start && x.start <= l.end; })) throw new Error('這段日期已經有請假申請了');
    var id = stNextId_('leave', 'L', 4);
    stPut_('leave', 0, [id, today + ' ' + stClock_(), e.id, type, l.start, l.end, reason, '待審', '', '']);
    try {
      var to = typeof notifyTo_ === 'function' ? notifyTo_('leave') : (typeof shopCfg_ === 'function' ? shopCfg_().notifyEmail : '');
      if (to && typeof emailOk_ === 'function' && emailOk_(to)) mail_(to, '【請假申請】' + e.name + ' ' + l.start + (l.end !== l.start ? '～' + l.end : ''), e.name + ' 申請 ' + type + '：' + l.start + (l.end !== l.start ? ' 到 ' + l.end : '') + '\n事由：' + (reason || '（未填）') + '\n\n請到「人員與班表」→「請假」核准或駁回。');
    } catch (err) {}
    return { id: id };
  });
}
function stLeaveCancel(token, id) {
  var e = stEmpCtx_(token, true);
  return stLocked_(function () {
    var l = stLeaves_().filter(function (x) { return x.id === String(id) && x.e === e.id; })[0];
    if (!l) throw new Error('找不到這筆請假');
    if (l.status !== '待審') throw new Error('已經審核過了，要取消請跟店長說');
    stPut_('leave', l._r, [l.id, l.at, l.e, l.type, l.start, l.end, l.reason, '已取消', stToday_() + ' ' + stClock_(), '']);
    return true;
  });
}

/* ================= 頁面 ================= */
function staffPage_(key) {
  stOwner_(key, false);
  var t = HtmlService.createTemplateFromFile('Staff');
  var base = tWebUrl_();
  t.boot = tJs_({ token: key, back: base ? base + (typeof saas_ === 'function' && saas_() ? '?t=' : '?staff=') + key : '', toolsUrl: base ? base + '?p=tools&' + (typeof saas_ === 'function' && saas_() ? 't=' : 'staff=') + key : '', brand: typeof brand_ === 'function' ? brand_() : {} });
  return t.evaluate().setTitle('人員與班表')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
/** 員工入口頁。jc＝專屬連結裡的通行證（有就直接是本人）；沒有就請輸入員工編號與 PIN（不列出任何人的名字） */
function clockPage_(sid, jc) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  var t = HtmlService.createTemplateFromFile('Clock');
  t.boot = tJs_({ sid: (typeof saas_ === 'function' && saas_() ? CTX.shopId : ''), brand: typeof brand_ === 'function' ? brand_() : {}, tok: String(jc || '') });
  return t.evaluate().setTitle('員工打卡')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function applyPage_(sid) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  var t = HtmlService.createTemplateFromFile('Apply'), h = stHire_();
  t.boot = tJs_({ sid: (typeof saas_ === 'function' && saas_() ? CTX.shopId : ''), brand: typeof brand_ === 'function' ? brand_() : {}, positions: h.positions, open: h.open });
  return t.evaluate().setTitle('面試登記')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function joinPage_(sid, code) {
  if (typeof saas_ === 'function' && saas_()) useShop_(sid);
  var info = stJoinInfo_(sid, code), t = HtmlService.createTemplateFromFile('Join');
  t.boot = tJs_({ sid: (typeof saas_ === 'function' && saas_() ? CTX.shopId : ''), code: String(code || ''), brand: typeof brand_ === 'function' ? brand_() : {},
    ok: !!info.ok, msg: info.msg || '', mode: info.mode || '', name: info.name || '', email: info.email || '', clockUrl: info.ok ? stClockUrl_() : '' });
  return t.evaluate().setTitle('員工資料')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
