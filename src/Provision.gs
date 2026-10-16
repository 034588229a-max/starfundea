/**
 * 開店與搬家（Provision.gs）：建立授權中心、替新店家建立試算表與資料夾、把原本的單店（弘林）轉成第一家店。
 * 這幾個函式由「我方」在 Apps Script 編輯器手動執行一次（setupCenter、adoptLegacyShop），或由程式在店家第一次登入時自動呼叫（ensureProvisioned_）。
 */

/* ---------- ① 建立授權中心（只做一次）---------- */
function setupCenter() {
  var p = sp0_();
  if (p.getProperty('centerId')) { Logger.log('授權中心已存在：' + p.getProperty('centerId')); return p.getProperty('centerId'); }
  var ss = SpreadsheetApp.create('授權中心（勿分享）');
  p.setProperty('centerId', ss.getId());
  _saas = null; CTX = {};
  Object.keys(CENTER).forEach(function (k) { cSheet_(k); });
  var first = ss.getSheetByName('Sheet1') || ss.getSheetByName('工作表1');
  if (first) { try { ss.deleteSheet(first); } catch (e) {} }
  secret_();
  if (!p.getProperty('adminEmails')) {
    var me = ''; try { me = Session.getEffectiveUser().getEmail(); } catch (e) {}
    if (me) p.setProperty('adminEmails', me);
  }
  try { ensureDailyTrigger_(); } catch (e) {}
  try { ensureTickTrigger_(); } catch (e) {}
  Logger.log('授權中心建好了：' + ss.getUrl() + '\n管理員 Email：' + p.getProperty('adminEmails') + '\n請部署網頁應用程式後，用「?p=admin」登入管理後台。');
  return ss.getId();
}

/* ---------- ② 每家店的資料夾與試算表 ---------- */
function rootFolder_() {
  var p = sp0_(), id = p.getProperty('rootFolderId');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) {} }
  var it = DriveApp.getFoldersByName('店家資料'), f = it.hasNext() ? it.next() : DriveApp.createFolder('店家資料');
  p.setProperty('rootFolderId', f.getId());
  return f;
}

function ensureProvisioned_(shop) {
  if (shop.ssId && shop.folderId) return shop;
  return provisionShop_(shop);
}

/* 替新店家建立資料夾＋試算表（有 templateId 就複製範本，沒有就建空白後初始化），寄開通信 */
function provisionShop_(shop) {
  var lock = LockService.getScriptLock(); lock.waitLock(30000);
  try {
    shop = shopById_(shop.id) || shop;
    if (shop.ssId && shop.folderId) return shop;
    var folder = shop.folderId ? DriveApp.getFolderById(shop.folderId) : rootFolder_().createFolder('店家_' + shop.id + '_' + shop.name);
    var ss;
    if (shop.ssId) ss = SpreadsheetApp.openById(shop.ssId);
    else {
      var tpl = sp0_().getProperty('templateId');
      if (tpl) ss = SpreadsheetApp.openById(DriveApp.getFileById(tpl).makeCopy('菜單資料_' + shop.name, folder).getId());
      else {
        ss = SpreadsheetApp.create('菜單資料_' + shop.name);
        try { var f = DriveApp.getFileById(ss.getId()); folder.addFile(f); DriveApp.getRootFolder().removeFile(f); } catch (e) {}
      }
    }
    shop.ssId = ss.getId(); shop.folderId = folder.getId();
    saveShop_(shop, ['ssId', 'folderId']);
    CTX = { shopId: shop.id, ssId: shop.ssId, role: 'system', shop: shop, lic: licOf_(shop) };
    initShopBook_(ss, shop);
    if (shop.role !== '分店') { shareToOwner_(shop); try { welcomeMail_(shop); } catch (e) {} }
    cLog_(shop.id, 'system', '建立店家資料', '成功', shop.ssId);
    return shop;
  } finally { lock.releaseLock(); }
}

/* 新店家試算表的初始內容：價格表（空的）、紀錄分頁、系統設定 */
function initShopBook_(ss, shop) {
  setupBook_(ss, [], { title: shop.name + '｜菜單價格表', fresh: true });
  props_().setProperty('cfg', JSON.stringify({}));      /* 店名沿用公司名稱，店家在「店家工具」自訂後才會覆蓋 */
  ['Sheet1', '工作表1'].forEach(function (n) { var s = ss.getSheetByName(n); if (s && ss.getSheets().length > 1) { try { ss.deleteSheet(s); } catch (e) {} } });
}

/* 把試算表分享給店主（預設只能查看，避免直接改壞資料；sheetShareRole=editor 可改成可編輯）。對方沒有 Google 帳號時會失敗，不影響開通 */
function shareToOwner_(shop) {
  try {
    var f = DriveApp.getFileById(shop.ssId), role = sp0_().getProperty('sheetShareRole');
    if (role === 'editor') f.addEditor(shop.email); else f.addViewer(shop.email);
    return true;
  } catch (e) { return false; }
}

function welcomeMail_(shop) {
  var tool = sp0_().getProperty('toolUrl') || '';
  mail_(shop.email, '【' + productName_() + '】「' + shop.name + '」已開通',
    '「' + shop.name + '」的菜單系統已建好。\n\n登入網址：' + webUrl_() + '\n登入方式：統編＋密碼，再按寄到這個信箱的登入信裡的「確認登入」。\n' +
    (tool ? '\n啟用工具下載：' + tool + '\n' : '') +
    '\n菜單資料試算表（唯讀備份）：https:' + '/' + '/docs.google.com/spreadsheets/d/' + shop.ssId + '\n\n登入後可以在「夥伴」頁產生邀請連結，讓店內夥伴用手機加入。',
    typeof mailHtml_ === 'function' ? { eyebrow: 'READY', title: shop.name + ' 已經建好了', preheader: '菜單、店務與人員工具都準備好了',
      blocks: [mkP_('「' + mkEsc_(shop.name) + '」的 SFD 系統已建好，菜單、店務收支、人員與班表都可以開始用。'),
        mkBtn_('登入 SFD 系統', webUrl_(), MK.amber, MK.navy),
        mkRows_([['登入方式', '統編＋密碼，再按登入信裡的「確認登入」'], ['資料備份', '一份唯讀試算表，隨時可以打開']]),
        mkList_(['登入後到「帳號」產生邀請連結，讓店內夥伴用手機加入', '先跑一次「設定精靈」：店家資料、Logo、配色'].concat(tool ? ['啟用工具：<a href="' + mkEsc_(tool) + '" style="color:' + MK.navy + '">下載</a>'] : [])),
        mkLink_('菜單資料試算表（唯讀備份）', 'https:' + '/' + '/docs.google.com/spreadsheets/d/' + shop.ssId)],
      why: '你收到這封信，是因為你的店在星樂創意開通了 SFD 系統。' } : null);
}

/* ---------- ③ 把原本的單店（弘林）轉成第一家店 ----------
   在 Apps Script 編輯器執行 adoptLegacyShop() 前，先執行 setupCenter()。
   做的事：建立店家 S0001（試算表＝目前這份）、把 Script Properties 的店家設定搬到「系統設定」分頁、保留舊鑰匙網址（legacyKeyOn=1）。
   確認新登入沒問題後，執行 disableLegacyKey() 關掉舊鑰匙。 */
var LEGACY_PROPS = ['ver', 'updatedAt', 'updatedBy', 'printedAt', 'deleted', 'priceFix', 't_shop', 't_logo', 't_tables', 't_tableOpt', 't_wifi'];
function adoptLegacyShop() {
  var p = sp0_();
  if (!p.getProperty('centerId')) throw new Error('請先執行 setupCenter()');
  if (p.getProperty('legacyShopId')) { Logger.log('已經轉換過了：' + p.getProperty('legacyShopId')); return p.getProperty('legacyShopId'); }
  _saas = null; resetCtx_();
  var ss = SpreadsheetApp.getActiveSpreadsheet(), id = nextShopId_(), cfg = legacyCfg_();
  var me = ''; try { me = Session.getEffectiveUser().getEmail(); } catch (e) {}
  var email = (typeof MENU_EMAIL !== 'undefined' && MENU_EMAIL) || me;
  var salt = rand_(16), pw = rand_(10) + 'a1';
  var folder = rootFolder_().createFolder('店家_' + id + '_' + cfg.name);
  var oneYear = addDaysStr_(todayStr_(), 365);
  cAppend_('shops', { '店家編號': id, '公司名稱': cfg.name, '統編': '00000000', '負責人': '', '登入Email': email, '方案': 'pro', '狀態': ST_LABEL.active, '到期日': oneYear,
    '試算表ID': ss.getId(), '資料夾ID': folder.getId(), '密碼鹽': salt, '密碼雜湊': pwHash_(pw, salt), '通行證版本': 1, '建立時間': nowD_(), '最後使用': '',
    '名稱鎖定至': addDaysStr_(todayStr_(), 180), '備註': '原單店系統轉入（請到後台補上統編、負責人、Email）', 'Email已驗證': true });
  /* 把舊的 Script Properties 搬進這家店的「系統設定」 */
  CTX = { shopId: id, ssId: ss.getId(), role: 'system', shop: shopById_(id), lic: {} };
  _saas = true; _spMap = null;
  var dst = shopProps_(), moved = 0;
  LEGACY_PROPS.forEach(function (k) { var v = p.getProperty(k); if (v != null) { dst.setProperty(k, v); moved++; } });
  var all = p.getProperties ? p.getProperties() : {};
  Object.keys(all).forEach(function (k) { if (k.indexOf('seq_') === 0) { dst.setProperty(k, all[k]); moved++; } });
  dst.setProperty('cfg', JSON.stringify({ name: cfg.name, tagline: cfg.tagline, address: cfg.address, phone: cfg.phone, hours: cfg.hours, closedText: cfg.closedText, lineId: cfg.lineId, lineUrl: cfg.lineUrl,
    orderUrl: cfg.orderUrl, mapUrl: cfg.mapUrl, fbUrl: cfg.fbUrl, openDays: cfg.openDays, channels: cfg.channels, minDays: cfg.minDays, notifyEmail: cfg.notifyEmail, menuEmail: cfg.menuEmail, heroTag: cfg.heroTag,
    nameA: '弘林', nameB: '早午餐' }));
  dst.setProperty('onboarded', '1');
  p.setProperty('legacyShopId', id); p.setProperty('legacyKeyOn', '1');
  Logger.log('已轉入：' + id + '（搬了 ' + moved + ' 筆設定）。舊鑰匙網址暫時仍可使用。\n請到管理後台補上統編、負責人與 Email，並用「重設密碼」寄出登入密碼；確認新登入沒問題後執行 disableLegacyKey()。');
  return id;
}
function disableLegacyKey() { sp0_().setProperty('legacyKeyOn', '0'); Logger.log('舊鑰匙網址已關閉'); }

/* ---------- ④ 測試用店家（免 Email 驗證碼）----------
   在 Apps Script 編輯器執行 createTestShop()：建立狀態「使用中」的測試店家，並開啟免驗證碼。
   用統編＋密碼登入後，驗證碼欄位隨便填就會通過。正式上線前請：執行 disableTestMode()，並刪掉這個函式裡的測試密碼。 */
var TEST_ACCOUNT = { taxId: '90039370', password: 'Test90039370', name: '測試店家' };
function createTestShop() { return seedTestShop(TEST_ACCOUNT.taxId, TEST_ACCOUNT.password, TEST_ACCOUNT.name); }
function seedTestShop(taxId, password, name) {
  var p = sp0_();
  if (!p.getProperty('centerId')) throw new Error('請先執行 setupCenter()');
  _saas = null; resetCtx_();
  var s = shopByTaxId_(taxId), me = '';
  try { me = Session.getEffectiveUser().getEmail(); } catch (e) {}
  var salt = rand_(16);
  if (s) {
    s.salt = salt; s.hash = pwHash_(password, salt); s.status = 'active'; s.plan = 'pro'; s.verified = true; s.expires = addDaysStr_(todayStr_(), 365); s.tv += 1;
    saveShop_(s, ['salt', 'hash', 'status', 'plan', 'verified', 'expires', 'tv']);
  } else {
    var id = nextShopId_();
    cAppend_('shops', { '店家編號': id, '公司名稱': name || '測試店家', '統編': taxId, '負責人': '測試', '登入Email': me || 'test@example.com', '方案': 'pro', '狀態': ST_LABEL.active,
      '到期日': addDaysStr_(todayStr_(), 365), '試算表ID': '', '資料夾ID': '', '密碼鹽': salt, '密碼雜湊': pwHash_(password, salt), '通行證版本': 1, '建立時間': nowD_(), '最後使用': '',
      '名稱鎖定至': addDaysStr_(todayStr_(), 180), '備註': '測試帳號（免驗證碼）', 'Email已驗證': true });
    s = shopById_(id);
  }
  s = provisionShop_(s);
  var cur = String(p.getProperty('testAccounts') || '').split(/[,\s]+/).filter(String);
  if (cur.indexOf(String(taxId)) < 0) cur.push(String(taxId));
  p.setProperty('testAccounts', cur.join(','));
  Logger.log('測試店家已建立：' + s.id + '（統編 ' + taxId + '，免驗證碼）\n登入網址：' + webUrl_());
  return s.id;
}
/* 在 Apps Script 編輯器執行：把弘林的菜單品項匯入測試店家（統編 90039370；已有品項時只補新增與更新價格） */
function importHonglingToTestShop() {
  var s = shopByTaxId_(TEST_ACCOUNT.taxId);
  if (!s) throw new Error('還沒有測試店家，請先執行 createTestShop()');
  var r = withShop_(s, function () { return menuApplyDraft_(honglingDraft_(), { update: true, label: '載入弘林範例菜單' }); });
  Logger.log('弘林菜單已匯入測試店家 ' + s.id + '：新增 ' + r.added + '、更新 ' + r.updated);
  return r;
}
function disableTestMode() { sp0_().deleteProperty('testAccounts'); Logger.log('測試帳號免驗證碼已關閉'); }

/* ---------- ⑤ 弘林早午餐專用帳號（正式帳號，不是測試帳號：登入要 Email 驗證碼）----------
   在 Apps Script 編輯器執行 createHonglingShop()，會依序：
   1. 建立店家（統編、負責人、登入 Email 用下面 HONGLING_ACCOUNT；狀態「使用中」、專業版、到期日一年後）
   2. 建立店家資料夾與「菜單資料_弘林早午餐」試算表，唯讀分享給登入 Email
   3. 寫入店家資料（店名、地址、電話、營業時間、LINE、配色…，沿用原本單店的設定），略過設定精靈
   4. 匯入弘林的全部菜單品項（分類、規格欄、價格、推薦星號）
   5. 寄「開通信」給登入 Email：店主自己用驗證碼設定密碼（程式裡不放密碼，客服也看不到）
   重複執行不會建第二家店：已存在就補建試算表、補店家資料，菜單只補缺少的品項（已有品項的價格不動）。
   統編 00000000 若已經被 adoptLegacyShop() 用掉（原本的單店弘林），就沿用那家店，只補負責人與登入 Email。 */
var HONGLING_ACCOUNT = { taxId: '00000000', owner: '弘林早午餐', email: '' };   /* 統編用 00000000；登入 Email 留空＝用 MENU_EMAIL（原本收菜單 PDF 的信箱） */
function createHonglingShop() { return seedHonglingShop(HONGLING_ACCOUNT); }
function seedHonglingShop(acct) {
  acct = acct || {};
  var p = sp0_();
  if (!p.getProperty('centerId')) throw new Error('請先執行 setupCenter()');
  var taxId = String(acct.taxId || '').replace(/\D/g, ''), owner = String(acct.owner || '').trim();
  var email = String(acct.email || (typeof MENU_EMAIL !== 'undefined' ? MENU_EMAIL : '') || '').trim().toLowerCase();
  if (taxId.length !== 8) throw new Error('請先在 HONGLING_ACCOUNT 填入 8 碼統一編號');
  if (!emailOk_(email)) throw new Error('請先在 HONGLING_ACCOUNT 填入正確的登入 Email');
  if (!owner) throw new Error('請先在 HONGLING_ACCOUNT 填入負責人');
  if (!taxIdOk_(taxId) && acct.skipTaxCheck !== true) throw new Error('統編檢查碼不正確，請再確認一次（確定正確的話，在 HONGLING_ACCOUNT 加上 skipTaxCheck: true）');
  _saas = null; resetCtx_();
  var cfg = legacyCfg_(), s = shopByTaxId_(taxId), fresh = !s;
  /* 已經用 adoptLegacyShop() 轉入過的弘林（同一個統編）：試算表就是原本那份、菜單與店家資料都已經在裡面，只補負責人與 Email，不重匯菜單（免得蓋掉現在的價格） */
  var legacy = !!(s && p.getProperty('legacyShopId') === s.id);
  if (fresh) {
    var id = nextShopId_();
    cAppend_('shops', { '店家編號': id, '公司名稱': cfg.name, '統編': taxId, '負責人': owner, '登入Email': email, '方案': 'pro', '狀態': ST_LABEL.active,
      '到期日': addDaysStr_(todayStr_(), 365), '試算表ID': '', '資料夾ID': '', '密碼鹽': '', '密碼雜湊': '', '通行證版本': 1, '建立時間': nowD_(), '最後使用': '',
      '名稱鎖定至': addDaysStr_(todayStr_(), 180), '備註': '弘林早午餐專用帳號', 'Email已驗證': true });
    s = shopById_(id);
    cLog_(id, 'system', '新增店家', '成功', '弘林早午餐專用帳號');
  } else if (s.email !== email || s.owner !== owner) {
    s.email = email; s.owner = owner; saveShop_(s, ['email', 'owner']);
  }
  s = provisionShop_(s);
  var r = legacy ? { added: 0, updated: 0 } : withShop_(s, function () {
    var dst = props_(), cur = {};
    try { cur = JSON.parse(dst.getProperty('cfg') || '{}') || {}; } catch (e) {}
    /* 店家已經在「店家工具」改過的欄位保留；沒填的用原本單店的資料補上 */
    var keep = ['name', 'nameA', 'nameB', 'tagline', 'address', 'phone', 'hours', 'closedText', 'lineId', 'lineUrl', 'orderUrl', 'mapUrl', 'fbUrl',
      'openDays', 'channels', 'minDays', 'heroTag', 'heroSub', 'primary', 'accent'];
    keep.forEach(function (k) { if ((cur[k] === undefined || cur[k] === '') && cfg[k] !== undefined) cur[k] = cfg[k]; });
    if (!cur.notifyEmail) cur.notifyEmail = email;
    if (!cur.menuEmail) cur.menuEmail = email;
    dst.setProperty('cfg', JSON.stringify(cur));
    dst.setProperty('onboarded', '1');
    return menuApplyDraft_(honglingDraft_(), { update: false, label: '匯入弘林早午餐菜單' });   /* 已有的品項不動（店家可能改過價格），只補缺的 */
  });
  var mailed = false;
  if (!s.hash) { try { actMail_(s, false); mailed = true; cLog_(s.id, 'system', '寄開通信', '成功', maskMail_(email)); } catch (e) { cLog_(s.id, 'system', '寄開通信', '失敗', String(e.message || e)); } }
  Logger.log((fresh ? '弘林早午餐專用帳號已建立：' : legacy ? '沿用原本轉入的弘林（菜單與店家資料不重匯）：' : '弘林早午餐帳號已更新：') + s.id + '（統編 ' + taxId + '）\n' +
    '菜單資料試算表：https://docs.google.com/spreadsheets/d/' + s.ssId + '\n' +
    '菜單品項：新增 ' + r.added + '、更新 ' + r.updated + '\n' +
    (mailed ? '開通信已寄到 ' + email + '：請店主按信裡的按鈕設定密碼。' : (s.hash ? '這個帳號已經有密碼，沒有寄開通信；要設定自己的密碼，請在登入頁按「首次開通／忘記密碼」，輸入統編 ' + taxId + '。' : '開通信寄送失敗，請到管理後台按「重寄開通信」。')) + '\n' +
    '登入網址：' + webUrl_());
  return { id: s.id, ssId: s.ssId, added: r.added, updated: r.updated, mailed: mailed, legacy: legacy };
}
