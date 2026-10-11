/**
 * 每家店自己的設定（Shop.gs）：店家資料（店名、地址、電話、營業日、LINE…）與菜單分類。
 * 線上服務模式的新店家一開始只有一組通用分類，店長可以自己改名、增減、調整規格欄。
 * 弘林（單店模式或轉入後）沒有存過分類時，仍然用 Page.html 內建的那一組。
 */

/* ---------- 格式統一：電話、LINE 網址、地址 ---------- */
var AREA_CODES = ['02', '03', '037', '04', '049', '05', '06', '07', '08', '082', '0836', '089'];
/* 市話：區碼＋7～8 碼 → 02-2222-3333（8 碼）或 03-458-8229（7 碼） */
function landFmt_(area, num) {
  area = String(area || '').replace(/\D/g, ''); num = String(num || '').replace(/\D/g, '');
  if (!num) return '';
  if (AREA_CODES.indexOf(area) < 0) throw new Error('請選擇市話區碼');
  if (num.length < 7 || num.length > 8) throw new Error('市話號碼要 7～8 碼（不含區碼）');
  return area + '-' + (num.length === 8 ? num.slice(0, 4) + '-' + num.slice(4) : num.slice(0, 3) + '-' + num.slice(3));
}
/* 手機：09 開頭 10 碼 → 0912-345-678 */
function mobileFmt_(s) {
  var d = String(s || '').replace(/\D/g, '');
  if (!d) return '';
  if (!/^09\d{8}$/.test(d)) throw new Error('手機號碼要 10 碼、09 開頭');
  return d.slice(0, 4) + '-' + d.slice(4, 7) + '-' + d.slice(7);
}
/* LINE ID → 官方帳號加好友網址（ID 前面的 @ 要寫成 %40）；ID 格式不對回傳空字串 */
function lineIdNorm_(id) { id = String(id || '').replace(/\s/g, ''); if (!id) return ''; if (!/^@?[A-Za-z0-9._-]{3,20}$/.test(id)) return null; return id.charAt(0) === '@' ? id : '@' + id; }
function lineUrlOf_(id) { var n = lineIdNorm_(id); return n ? 'https:' + '/' + '/line.me/R/ti/p/%40' + n.slice(1) : ''; }

/* ---------- 公司名稱與統編（精靈第一步順便登錄）----------
   一般店家註冊時已經填好，這裡只能看、不能改（改名要 180 天後或客服審核）。
   只有「統編還是佔位的 00000000」（例如原單店轉入）才允許補填一次。 */
function ownCompanySave(token, f) {
  var c = authGuard_(token, true);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以登錄公司資料');
  f = f || {};
  var s = c.shop, company = cfgClean_(f.company, 40), taxId = String(f.taxId || '').replace(/\D/g, '');
  if (s.taxId !== '00000000') return fail_('locked', '公司名稱與統編已登錄，不能自行修改；需要修改請聯絡客服。');
  if (!company) return fail_('bad', '請填公司（或商號）名稱');
  if (!taxIdOk_(taxId)) return fail_('bad', '統編不正確，請再確認 8 碼數字');
  if (shopByTaxId_(taxId)) return fail_('exists', '這個統編已經登錄在別的帳號');
  s.name = company; s.taxId = taxId; s.nameLock = addDaysStr_(todayStr_(), 180);
  saveShop_(s, ['name', 'taxId', 'nameLock']);
  cLog_(s.id, 'owner', '登錄公司資料', '成功', company + ' / ' + taxId);
  return { ok: true, company: company, taxId: taxId };
}

/* ---------- 店家資料 ---------- */
function cfgClean_(s, max) { return String(s == null ? '' : s).replace(/[<>]/g, '').trim().slice(0, max || 100); }
function ownCfgGet(token) {
  var c = authGuard_(token, false);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以修改店家資料');
  return { ok: true, cfg: shopCfg_(), notifyTypes: NOTIFY_TYPES };
}
function ownCfgSave(token, f) {
  var c = authGuard_(token, true);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以修改店家資料');
  var r = cfgSave_(f);
  cLog_(c.shopId, 'owner', '修改店家資料', '成功', '');
  return r;
}
/** 同上，但不檢查權限、不寫紀錄（給種子資料／內部流程用，驗證規則完全一樣）。 */
function cfgSave_(f) {
  f = f || {};
  var out = {};
  ['name', 'tagline', 'address', 'phone', 'hours', 'closedText', 'lineId', 'heroTag'].forEach(function (k) { out[k] = cfgClean_(f[k], k === 'address' ? 80 : 60); });
  /* 地址：縣市＋區＋路號（精靈）；沒帶這三個欄位時沿用自由輸入的 address */
  if (f.addrCity !== undefined || f.addrDist !== undefined || f.addrRoad !== undefined) {
    out.addrCity = cfgClean_(f.addrCity, 6); out.addrDist = cfgClean_(f.addrDist, 8); out.addrRoad = cfgClean_(f.addrRoad, 60);
    out.address = out.addrCity + out.addrDist + out.addrRoad;
  } else { out.addrCity = out.addrDist = out.addrRoad = ''; }
  /* 電話：市話（區碼＋號碼）與手機分開，格式統一；沒帶這些欄位時沿用自由輸入的 phone */
  if (f.phoneLandArea !== undefined || f.phoneLandNum !== undefined || f.phoneMobile !== undefined) {
    out.phoneLandArea = String(f.phoneLandArea || '').replace(/\D/g, ''); out.phoneLandNum = String(f.phoneLandNum || '').replace(/\D/g, '');
    out.phoneMobile = String(f.phoneMobile || '').replace(/\D/g, '');
    out.phone = [landFmt_(out.phoneLandArea, out.phoneLandNum), mobileFmt_(out.phoneMobile)].filter(String).join('／');
  } else { out.phoneLandArea = out.phoneLandNum = out.phoneMobile = ''; }
  /* LINE：填 ID 就自動產生官方網址；有自訂網址（例如 lin.ee 短網址）以自訂的為準 */
  var lid = lineIdNorm_(f.lineId);
  if (lid === null) throw new Error('LINE ID 格式不正確（英文、數字、. _ -，3～20 個字，可以加 @）');
  out.lineId = lid;
  ['lineUrl', 'orderUrl', 'mapUrl', 'fbUrl'].forEach(function (k) {
    var u = String(f[k] || '').trim();
    if (u && !/^https?:\/\/[^\s]+\.[^\s]+$/i.test(u)) throw new Error('網址格式不正確（要以 https 開頭）：' + k);
    out[k] = u.slice(0, 500);
  });
  if (!out.lineUrl && lid) out.lineUrl = lineUrlOf_(lid);
  var days = (f.openDays || []).map(Number).filter(function (d, i, a) { return d >= 0 && d <= 6 && a.indexOf(d) === i; });
  if (!days.length) throw new Error('至少要有一天營業');
  out.openDays = days;
  out.minDays = Math.max(0, Math.min(30, parseInt(f.minDays, 10) || 0));
  out.channels = (f.channels || []).map(function (x) { return cfgClean_(x, 20); }).filter(String).slice(0, 8);
  ['notifyEmail', 'menuEmail'].forEach(function (k) {
    var m = String(f[k] || '').trim();
    if (m && !emailOk_(m)) throw new Error('Email 格式不正確');
    out[k] = m;
  });
  if (Array.isArray(f.notifyOff)) {
    var keys = notifyKeys_();
    out.notifyOff = f.notifyOff.map(String).filter(function (k, i, a) { return keys.indexOf(k) >= 0 && a.indexOf(k) === i; });
  }
  var old = {}; try { old = JSON.parse(props_().getProperty('cfg') || '{}'); } catch (e) {}
  props_().setProperty('cfg', JSON.stringify(Object.assign(old, out)));
  try { CacheService.getScriptCache().remove(ck_('logo')); } catch (e) {}
  return { ok: true, cfg: shopCfg_() };
}

/* ---------- 菜單分類 ----------
   每個分類：{ id, t（名稱）, cols（規格欄，例如 ['中杯','大杯']；只有一個價格就 ['價格']）, note?（說明文字）, hl?（藍色強調）} */
var STARTER_SECTIONS = [
  { id: 'main', t: '主餐', cols: ['價格'] },
  { id: 'drink', t: '飲料', cols: ['中杯', '大杯'] },
  { id: 'side', t: '點心', cols: ['價格'] }
];
function sectionsOf_() {
  if (!saas_()) return null;
  var raw = props_().getProperty('sections');
  if (raw) { try { var s = JSON.parse(raw); if (s && s.length) return s; } catch (e) {} }
  if (sp0_().getProperty('legacyShopId') === CTX.shopId) return null;      /* 弘林：用 Page.html 內建的分類 */
  return STARTER_SECTIONS;
}
function secClean_(list) {
  if (!Array.isArray(list) || !list.length) throw new Error('至少要有一個分類');
  if (list.length > 14) throw new Error('分類最多 14 個');
  var seen = {}, ids = {};
  list.forEach(function (s) { var x = String(s.id || '').replace(/[^a-z]/g, '').slice(0, 10); if (x) ids[x] = 1; });
  return list.map(function (s, i) {
    var id = String(s.id || '').replace(/[^a-z]/g, '').slice(0, 10), t = cfgClean_(s.t, 14);
    if (!t) throw new Error('第 ' + (i + 1) + ' 個分類沒有名稱');
    if (!id) { for (var k = 0; k < 676; k++) { id = 'c' + String.fromCharCode(97 + Math.floor(k / 26)) + String.fromCharCode(97 + k % 26); if (!seen[id] && !ids[id]) break; } }
    if (seen[id]) throw new Error('分類代碼重複：' + id);
    seen[id] = 1;
    var cols = (s.cols || []).map(function (c) { return cfgClean_(c, 5); }).filter(String);
    if (!cols.length || cols.length > 6) throw new Error('「' + t + '」的規格欄要 1～6 個');
    return { id: id, t: t, cols: cols, note: cfgClean_(s.note, 80), hl: s.hl ? 1 : 0, color: hexOk_(s.color) ? String(s.color).toUpperCase() : '' };
  });
}
function saveSections(list, key) {
  guard_(key);
  if (!saas_()) throw new Error('單店模式不能自訂分類');
  if (CTX.role !== 'owner') throw new Error('只有店長可以修改分類');
  var next = secClean_(list), cur = sectionsOf_() || [];
  /* 拿掉的分類裡如果還有品項，不讓刪（避免品項在畫面上消失） */
  var d = getData_(), used = {};
  d.rows.forEach(function (r) { used[r.k.split('|')[0]] = (used[r.k.split('|')[0]] || 0) + 1; });
  var keep = {}; next.forEach(function (s) { keep[s.id] = 1; });
  cur.forEach(function (s) { if (!keep[s.id] && used[s.id]) throw new Error('「' + s.t + '」裡還有 ' + used[s.id] + ' 個品項，請先刪除品項再刪分類'); });
  /* 改了規格欄數量：比現有品項用到的欄位還少就不行 */
  next.forEach(function (s) { d.rows.forEach(function (r) { var p = r.k.split('|'); if (p[0] === s.id && Number(p[2]) >= s.cols.length) throw new Error('「' + s.t + '」有品項用到第 ' + (Number(p[2]) + 1) + ' 個規格欄，不能減少欄數'); }); });
  props_().setProperty('sections', JSON.stringify(next));
  return { ok: true, sections: next };
}

/* ---------- AI 協助建立菜單初稿 ----------
   流程：店主上傳菜單照片或 PDF → aiMenuDraft（一次一個檔案，呼叫 Claude 辨識，回傳初稿，不寫入任何資料）
        → 店主在畫面上修改 → aiMenuApply（驗證後才寫進分類與價格表）。
   需要在 Script Properties 設定 anthropicKey（API 金鑰）；可選 aiModel（預設 claude-sonnet-5-5）。
   一次只送一個檔案：Apps Script 的 UrlFetch 單次最多等 60 秒，一頁菜單約 20～40 秒。 */
var AI_DAILY_LIMIT = 30;           /* 每家店每天最多辨識幾次 */
var AI_MAX_BYTES = 7 * 1024 * 1024;
var AI_SCHEMA = {
  type: 'object',
  properties: {
    sections: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string', description: '分類名稱，例如「飲料」「蛋餅」' },
      columns: { type: 'array', items: { type: 'string' }, description: '價格欄名稱。依大小或做法分欄時用欄名，例如 ["中杯","大杯"]；只有一個價格就用 ["價格"]' },
      note: { type: 'string', description: '這個分類的說明文字（例如「皆附小菜」），沒有就留空' },
      items: { type: 'array', items: { type: 'object', properties: {
        name: { type: 'string', description: '品項名稱，照菜單原文，不要改寫' },
        prices: { type: 'array', items: { type: ['number', 'null'] }, description: '每個欄位的價格（新台幣整數）；該欄不供應或看不清楚填 null；長度要等於 columns' },
        star: { type: 'boolean', description: '菜單上標示「推薦」「招牌」「人氣」才填 true' }
      }, required: ['name', 'prices'] } }
    }, required: ['title', 'columns', 'items'] } },
    warnings: { type: 'array', items: { type: 'string' }, description: '看不清楚、可能辨識錯誤的地方，請店主確認' }
  },
  required: ['sections']
};
var AI_PROMPT = '這是一份餐廳菜單（照片或掃描檔）。請把裡面所有「可以點的品項」整理成分類、品項與價格。規則：\n' +
  '1. 品項名稱、分類名稱照菜單原文，不要翻譯、不要改寫、不要自己新增菜單上沒有的東西。\n' +
  '2. 價格是新台幣整數；沒有標價或看不清楚填 null，並在 warnings 說明是哪一項。\n' +
  '3. 同一個品項有多種規格（例如中杯／大杯、蛋餅／抓餅）時，用 columns 當欄名，prices 依欄位順序填。\n' +
  '4. 套餐、加料、加價的說明如果很短，放進該分類的 note；不要把店名、地址、電話、營業時間當成品項。\n' +
  '5. 分類最多 14 個；看不出分類時用「餐點」「飲料」這類簡單名稱。';

function aiOn_() { return sp0_().getProperty('aiEnabled') === '1'; }      /* 預留功能：預設關閉，要開放時把 Script Properties 的 aiEnabled 設成 1 */
function aiKey_() { return sp0_().getProperty('anthropicKey') || ''; }
function aiModel_() { return sp0_().getProperty('aiModel') || 'claude-sonnet-5-5'; }

/* file = { mime: 'image/jpeg'|'image/png'|'image/webp'|'application/pdf', b64 } */
function aiMenuDraft(file, key) {
  guard_(key);
  if (!aiOn_()) throw new Error('這個功能還沒開放');
  if (!saas_()) throw new Error('單店模式沒有這個功能');
  if (CTX.role !== 'owner') throw new Error('只有店長可以用 AI 建立菜單');
  file = file || {};
  var mime = String(file.mime || ''), b64 = String(file.b64 || '');
  if (['image/jpeg', 'image/png', 'image/webp', 'application/pdf'].indexOf(mime) < 0) throw new Error('只支援 JPG、PNG、WebP 圖片或 PDF');
  if (!b64 || b64.length * 0.75 > AI_MAX_BYTES) throw new Error('檔案太大（上限約 7MB），請壓縮或分頁上傳');
  if (!aiKey_()) throw new Error('AI 功能還沒啟用（管理員需要先設定 anthropicKey）');
  var c = CacheService.getScriptCache(), ck = 'ai:' + CTX.shopId + ':' + todayStr_(), n = Number(c.get(ck) || 0);
  if (n >= AI_DAILY_LIMIT) throw new Error('今天的 AI 辨識次數用完了（每天 ' + AI_DAILY_LIMIT + ' 次），請明天再試');
  c.put(ck, String(n + 1), 86400);
  var src = mime === 'application/pdf' ? { type: 'document', source: { type: 'base64', media_type: mime, data: b64 } } : { type: 'image', source: { type: 'base64', media_type: mime, data: b64 } };
  var body = { model: aiModel_(), max_tokens: 4096,
    tools: [{ name: 'menu_draft', description: '把菜單整理成分類、品項、價格', input_schema: AI_SCHEMA }], tool_choice: { type: 'tool', name: 'menu_draft' },
    messages: [{ role: 'user', content: [src, { type: 'text', text: AI_PROMPT }] }] };
  var res = UrlFetchApp.fetch('https:' + '/' + '/api.anthropic.com/v1/messages', { method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    headers: { 'x-api-key': aiKey_(), 'anthropic-version': '2023-06-01' }, payload: JSON.stringify(body) });
  var code = res.getResponseCode(), text = res.getContentText();
  if (code !== 200) {
    var msg = ''; try { msg = JSON.parse(text).error.message; } catch (e) {}
    cLog_(CTX.shopId, 'owner', 'AI 菜單辨識', '失敗 ' + code, msg.slice(0, 120));
    if (code === 401 || code === 403) throw new Error('AI 金鑰無效，請聯絡客服');
    if (code === 429 || code === 529) throw new Error('AI 目前忙碌，請稍後再試');
    throw new Error('AI 辨識失敗（' + code + '）' + (msg ? '：' + msg : ''));
  }
  var out = JSON.parse(text), tu = (out.content || []).filter(function (x) { return x.type === 'tool_use'; })[0];
  if (!tu || !tu.input) throw new Error('AI 沒有辨識出菜單內容，請換一張更清楚的照片');
  var draft = draftClean_(tu.input);
  cLog_(CTX.shopId, 'owner', 'AI 菜單辨識', '成功', draft.sections.length + ' 個分類');
  return { ok: true, draft: draft, truncated: out.stop_reason === 'max_tokens' };
}

/* 清理初稿（AI 辨識、範本匯入共用，套用前再驗一次）：名稱去掉特殊字元、價格取整數、長度限制。
   品項可帶：prices（依欄位順序）、star（推薦）、tags（標示代碼）、side（附餐說明）、hidden（隱藏） */
function draftClean_(d) {
  var secs = [], total = 0;
  (d && d.sections || []).slice(0, 14).forEach(function (s) {
    var title = cfgClean_(s.title, 14), cols = (s.columns || []).map(function (x) { return cfgClean_(x, 5); }).filter(String).slice(0, 6);
    if (!title) return;
    if (!cols.length) cols = ['價格'];
    var items = [], seen = {};
    (s.items || []).slice(0, 150).forEach(function (it) {
      var name = cfgClean_(String(it.name || '').replace(/[|]/g, '／'), 30);
      if (!name || seen[name] || total >= 600) return;
      seen[name] = 1; total++;
      var prices = cols.map(function (_, i) {
        var v = it.prices && it.prices[i];
        if (v === null || v === undefined || v === '') return null;
        var n = Math.round(Number(v));
        return isNaN(n) || n < 0 ? null : Math.min(n, 9999);
      });
      items.push({ name: name, prices: prices, star: it.star === true, tags: tagsClean_(it.tags), side: cfgClean_(it.side, 30), hidden: it.hidden === true });
    });
    secs.push({ title: title, columns: cols, note: cfgClean_(s.note, 80), items: items });
  });
  return { sections: secs, warnings: (d && d.warnings || []).map(function (w) { return cfgClean_(w, 120); }).filter(String).slice(0, 30) };
}

/* 把店主確認過的初稿寫進去（AI 與範本匯入共用）。
   - 還沒有任何品項：用初稿的分類取代目前的分類
   - 已經有品項：同名分類併入（欄位名稱對得上、或欄數相同才併），其他當新分類加在後面
   - 已存在的品項：opt.update 為假就略過；為真就更新（價格空白＝不動、推薦／標示／附餐說明／隱藏以初稿為準） */
function menuApplyDraft_(draft, opt) {
  opt = opt || {};
  if (!saas_()) throw new Error('單店模式沒有這個功能');
  if (CTX.role !== 'owner') throw new Error('只有店長可以建立菜單');
  var d = draftClean_(draft);
  if (!d.sections.length) throw new Error('沒有可以建立的分類');
  var lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    var data = getData_(), cur = sectionsOf_() || [], have = {};
    data.rows.forEach(function (r) { var p = r.k.split('|'); have[p[0] + '|' + p[1]] = 1; });
    var next = [], added = 0, updated = 0, skipped = 0, rows = [], upd = [], pruned = false;
    var taken = {}; cur.forEach(function (s) { taken[s.id] = 1; });
    var newId = function () { for (var i = 0; i < 26 * 26; i++) { var id = 's' + String.fromCharCode(97 + Math.floor(i / 26)) + String.fromCharCode(97 + i % 26); if (!taken[id]) { taken[id] = 1; return id; } } throw new Error('分類太多'); };
    var replace = !data.rows.length;
    if (replace) { taken = {}; } else { next = cur.map(function (s) { return s; }); }
    d.sections.forEach(function (s) {
      var ex = replace ? null : cur.filter(function (c) { return c.t === s.title; })[0], sec, map;
      if (!ex && opt.pricesOnly) return;                     /* 只調價：不新增分類 */
      if (ex) {
        sec = ex;
        map = s.columns.map(function (_, i) { var at = ex.cols.indexOf(s.columns[i]); return at >= 0 ? at : (ex.cols.length === s.columns.length ? i : -1); });
      } else {
        if (next.length >= 14) throw new Error('分類最多 14 個，請先整理現有分類');
        sec = { id: newId(), t: s.title, cols: s.columns, note: s.note, hl: 0 }; next.push(sec);
        map = s.columns.map(function (_, i) { return i; });
      }
      var one = sec.cols.length === 1 && (sec.cols[0] === '價格' || sec.cols[0] === '加價');
      s.items.forEach(function (it) {
        var tg = it.tags.join(',');
        if (have[sec.id + '|' + it.name]) {
          if (opt.update) upd.push({ sid: sec.id, it: it, map: map, sec: sec, tg: tg, one: one }); else skipped++;
          return;
        }
        if (opt.pricesOnly) { skipped++; return; }           /* 只調價：不新增品項 */
        var made = 0;
        map.forEach(function (ci, i) {
          if (ci < 0) return;
          var p = it.prices[i];
          if (p === null && sec.cols.length > 1) return;                       /* 多規格：沒價格＝不供應，不建立那一欄 */
          rows.push([sec.id + '|' + it.name + '|' + ci, sec.t, it.name, one ? '' : sec.cols[ci], p === null ? '' : p, '', it.hidden, it.star, it.side, tg]);
          made++;
        });
        if (!made) rows.push([sec.id + '|' + it.name + '|0', sec.t, it.name, sec.cols.length === 1 ? '' : sec.cols[0], '', '', it.hidden, it.star, it.side, tg]);
        added++;
      });
    });
    if (replace) next = next.length ? next : STARTER_SECTIONS;
    if (!opt.dry) props_().setProperty('sections', JSON.stringify(next));
    var ss = book_(), sh = ss.getSheetByName(SHEET_NAME);
    if (!sh) throw new Error('找不到價格表');
    var removed = 0;
    /* 更新已存在的品項、移除總店沒有的品項：整塊讀進來改，一次寫回 */
    if (upd.length || opt.prune) {
      var n = sh.getLastRow() - HEAD, vals = n > 0 ? sh.getRange(HEAD + 1, 1, n, NCOL).getValues() : [], at = {};
      vals.forEach(function (r, i) { at[String(r[0]).trim()] = i; });
      upd.forEach(function (u) {
        var changed = false;
        u.map.forEach(function (ci, i) {
          if (ci < 0) return;
          var k = u.sid + '|' + u.it.name + '|' + ci, p = u.it.prices[i];
          if (at[k] === undefined) { if (p !== null && !opt.pricesOnly) { rows.push([k, u.sec.t, u.it.name, u.one ? '' : u.sec.cols[ci], p, '', u.it.hidden, u.it.star, u.it.side, u.tg]); changed = true; } return; }
          var r = vals[at[k]];
          if (p !== null && Number(r[4]) !== p) { r[4] = p; changed = true; }
        });
        for (var j = 0; !opt.pricesOnly && j < u.sec.cols.length; j++) {
          var rr = vals[at[u.sid + '|' + u.it.name + '|' + j]]; if (!rr) continue;
          if (rr[6] !== u.it.hidden || rr[7] !== u.it.star || String(rr[8] || '') !== u.it.side || String(rr[9] || '') !== u.tg) { changed = true; rr[6] = u.it.hidden; rr[7] = u.it.star; rr[8] = u.it.side; rr[9] = u.tg; }
        }
        if (changed) updated++; else skipped++;
      });
      if (opt.prune) {                                       /* 分類對得上的，品項要跟初稿一樣：初稿沒有的品項移除 */
        var keep = {}, touched = {};
        d.sections.forEach(function (s) { var sec = next.filter(function (c) { return c.t === s.title; })[0]; if (!sec) return; touched[sec.id] = 1; s.items.forEach(function (it) { keep[sec.id + '|' + it.name] = 1; }); });
        var gone = {};
        vals.forEach(function (r) { var k = String(r[0]).trim(); if (!k) return; var p = k.split('|'); if (touched[p[0]] && !keep[p[0] + '|' + p[1]]) gone[p[0] + '|' + p[1]] = 1; });
        removed = Object.keys(gone).length;
        if (removed && !opt.dry) {
          var kept = vals.filter(function (r) { var p = String(r[0]).trim().split('|'); return !gone[p[0] + '|' + p[1]]; });
          var blank = []; for (var z = 0; z < vals.length - kept.length; z++) blank.push(['', '', '', '', '', '', false, false, '', '']);
          vals = kept.concat(blank);
          updated = updated || 0; pruned = true;
        }
      }
      if ((updated || pruned) && !opt.dry) sh.getRange(HEAD + 1, 1, n, NCOL).setValues(vals);
    }
    if (opt.dry) return { ok: true, dry: true, added: added, updated: updated, skipped: skipped, removed: removed, sections: next };
    if (rows.length) {
      var r0 = sh.getLastRow() + 1;
      /* 空的價格表只有一列佔位（代碼空白）：從那一列開始寫 */
      if (replace && r0 === HEAD + 2 && !String(sh.getRange(HEAD + 1, 1).getValue())) r0 = HEAD + 1;
      sh.getRange(r0, 1, rows.length, NCOL).setValues(rows);
    }
    logItem_(ss, opt.label || '匯入菜單', '新增 ' + added + (updated ? '、更新 ' + updated : '') + (removed ? '、移除 ' + removed : '') + ' 個品項' + (skipped ? '，略過 ' + skipped + ' 個' : ''));
    return { ok: true, added: added, updated: updated, skipped: skipped, removed: removed, sections: next };
  } finally { lock.releaseLock(); }
}

function aiMenuApply(draft, key) {
  guard_(key);
  if (!aiOn_()) throw new Error('這個功能還沒開放');
  return menuApplyDraft_(draft, { label: 'AI 匯入菜單' });
}
/* 範本匯入：店主下載範本填好上傳，在畫面上檢查修改後才呼叫這裡 */
function menuImportApply(draft, key) {
  guard_(key);
  return menuApplyDraft_(draft, { update: true, label: '範本匯入菜單' });
}

/* 弘林內建品項（ITEMS）整理成初稿：測試帳號用「載入弘林範例菜單」一鍵匯入。分類、規格欄、推薦星號都帶入；分類下方的說明文字不帶 */
function honglingDraft_() {
  var secs = [], by = {};
  ITEMS.forEach(function (it) {
    var p = String(it[0]).split('|'), sid = p[0], name = p[1], ci = Number(p[2]) || 0, s = by[sid];
    if (!s) { s = by[sid] = { title: it[1], cols: [], items: [], idx: {} }; secs.push(s); }
    if (it[3] || s.cols[ci] === undefined) s.cols[ci] = it[3] || s.cols[ci] || '';
    var x = s.idx[name];
    if (!x) { x = s.idx[name] = { name: name, prices: [], star: false }; s.items.push(x); }
    x.prices[ci] = it[4] === '' ? null : Number(it[4]);
    if (it[5]) x.star = true;
  });
  return { sections: secs.map(function (s) {
    var n = Math.max(s.cols.length, 1), cols = [];
    for (var i = 0; i < n; i++) cols.push(s.cols[i] || (n === 1 ? '價格' : '規格' + (i + 1)));
    return { title: s.title, columns: cols, items: s.items.map(function (x) { var pr = []; for (var j = 0; j < n; j++) pr.push(x.prices[j] === undefined ? null : x.prices[j]); return { name: x.name, prices: pr, star: x.star }; }) };
  }), warnings: [] };
}
function ownDemoMenuLoad(key) {
  guard_(key);
  if (!saas_() || CTX.role !== 'owner') throw new Error('只有店長可以使用');
  if (typeof testAcct_ !== 'function' || !testAcct_(CTX.shop.taxId)) throw new Error('只有測試帳號可以載入範例菜單');
  var r = menuApplyDraft_(honglingDraft_(), { update: true, label: '載入弘林範例菜單' });
  return { added: r.added, updated: r.updated };
}

/* 目前這家店的菜單整理成「初稿」格式（複製到分店用）：分類、規格欄從價格表的列推出來，弘林這種內建分類也適用 */
function menuDraftOf_() {
  var d = getData_(), secs = [], by = {};
  d.rows.forEach(function (r) {
    var p = r.k.split('|'), sid = p[0], name = p[1], ci = Number(p[2]);
    var s = by[sid];
    if (!s) { s = by[sid] = { sid: sid, title: r.cat, cols: [], items: [], idx: {} }; secs.push(s); }
    if (r.spec || s.cols[ci] === undefined) s.cols[ci] = r.spec || s.cols[ci] || '';
    var it = s.idx[name];
    if (!it) { it = s.idx[name] = { name: name, prices: [], star: !!r.star, tags: tagsClean_(r.tags), side: r.side || '', hidden: !!r.hidden }; s.items.push(it); }
    it.prices[ci] = r.p === '' ? null : Number(r.p);
  });
  var cur = typeof sectionsOf_ === 'function' ? (sectionsOf_() || []) : [];
  return { sections: secs.map(function (s) {
    var c = cur.filter(function (x) { return x.id === s.sid; })[0] || cur.filter(function (x) { return x.t === s.title; })[0];
    var n = Math.max(s.cols.length, c ? c.cols.length : 0, 1), cols = [];
    for (var i = 0; i < n; i++) cols.push((c && c.cols[i]) || s.cols[i] || (n === 1 ? '價格' : '規格' + (i + 1)));
    return { title: s.title, columns: cols, note: c ? c.note : '', color: c ? c.color : '',
      items: s.items.map(function (it) { var pr = []; for (var j = 0; j < n; j++) pr.push(it.prices[j] === undefined ? null : it.prices[j]); return { name: it.name, prices: pr, star: it.star, tags: it.tags, side: it.side, hidden: it.hidden }; }) };
  }), warnings: [] };
}

/* ---------- 外觀：店家主色、強調色、各分類的區分顏色 ---------- */
function hexOk_(v) { return /^#[0-9A-Fa-f]{6}$/.test(String(v || '')); }
function ownThemeSave(token, f) {
  var c = authGuard_(token, true);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以修改外觀');
  var r = themeSave_(f);
  if (!r.ok) return r;
  cLog_(c.shopId, 'owner', '修改外觀顏色', '成功', r.primary + ' / ' + r.accent);
  return r;
}
/** 同上，但不檢查權限、不寫紀錄（給種子資料用）。 */
function themeSave_(f) {
  f = f || {};
  if (!hexOk_(f.primary) || !hexOk_(f.accent)) return fail_('bad', '顏色格式不正確');
  var old = {}; try { old = JSON.parse(props_().getProperty('cfg') || '{}'); } catch (e) {}
  old.primary = String(f.primary).toUpperCase(); old.accent = String(f.accent).toUpperCase();
  props_().setProperty('cfg', JSON.stringify(old));
  var secs = sectionsOf_();
  if (secs && f.colors) {
    secs = secs.map(function (s) { var v = f.colors[s.id]; return Object.assign({}, s, { color: hexOk_(v) ? String(v).toUpperCase() : '' }); });
    props_().setProperty('sections', JSON.stringify(secs));
  }
  return { ok: true, primary: old.primary, accent: old.accent, sections: secs };
}

/* 設定精靈完成：之後店主進來直接到菜單工具 */
function ownOnboardDone(token) {
  var c = authGuard_(token, true);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以設定');
  props_().setProperty('onboarded', '1');
  cLog_(c.shopId, 'owner', '完成店家設定精靈', '成功', '');
  return { ok: true };
}
