/**
 * 登入與帳號（Auth.gs）：統編＋密碼＋Email 驗證碼、夥伴邀請、註冊、管理後台。
 * 這裡的函式都是「公開入口」（google.script.run／doPost 呼叫），沒有店家情境，所以：
 *  - 不信任任何傳進來的店家編號，一律用通行證或統編＋密碼查出是哪家店
 *  - 失敗次數、寄信額度都在這裡擋
 * 回傳一律是物件：{ ok:true, … } 或 { ok:false, code, msg }（要讓店家看到的錯誤用 msg）
 */

var OTP_TTL = 300;          /* 驗證碼 5 分鐘有效 */
var FAIL_MAX = 5;           /* 連續錯 5 次 */
var LOCK_TTL = 900;         /* 鎖 15 分鐘 */
var PILOT_DAYS = 30;        /* 試營運：後台開通，全功能、輸出不加浮水印 */
var PLANS = {               /* 方案（月費含稅，元）；年繳 10 個月價（送 2 個月） */
  trial: { name: '試用', month: 0, trialDays: 14 },
  basic: { name: '基本版', month: 399 },
  pro: { name: '專業版', month: 599 }
};

function productName_() { return sp0_().getProperty('productName') || '星樂創意 StarFunDea'; }
function fail_(code, msg, extra) { var o = { ok: false, code: code, msg: msg }; if (extra) Object.keys(extra).forEach(function (k) { o[k] = extra[k]; }); return o; }
function maskMail_(m) {
  m = String(m || ''); var i = m.indexOf('@'); if (i < 1) return '';
  return m.slice(0, Math.min(2, i)) + '***' + m.slice(i);
}
function emailOk_(m) { return /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/.test(String(m || '')); }
function adminEmails_() { return String(sp0_().getProperty('adminEmails') || '').toLowerCase().split(/[,;\s]+/).filter(String); }

/* ---------- 測試帳號：免 Email 驗證碼 ----------
   Script Properties 的 testAccounts（逗號分隔的統編）裡的店家，密碼正確就直接通過驗證碼這一關（驗證碼欄位任意填）。
   只給測試用；正式上線前執行 disableTestMode() 關掉。密碼仍然要正確、鎖定機制照常。 */
function testAcct_(id) { return String(sp0_().getProperty('testAccounts') || '').split(/[,\s]+/).indexOf(String(id)) >= 0; }

/* ---------- 失敗次數與鎖定 ---------- */
function lockedOut_(k) { return !!CacheService.getScriptCache().get('lock:' + k); }
function failBump_(k) {
  var c = CacheService.getScriptCache(), n = Number(c.get('fail:' + k) || 0) + 1;
  c.put('fail:' + k, String(n), LOCK_TTL);
  if (n >= FAIL_MAX) { c.put('lock:' + k, '1', LOCK_TTL); c.remove('fail:' + k); }
  return n;
}
function failClear_(k) { var c = CacheService.getScriptCache(); c.remove('fail:' + k); c.remove('lock:' + k); }
var LOCK_MSG = '嘗試次數太多，已暫時鎖定。請 15 分鐘後再試。';

/* ---------- 驗證碼 ---------- */
/* 寄信：一律經過 Mail.gs 的 mailSend_（品牌 HTML＋純文字）；o＝版型，x＝{brand:'shop', btn, attachments…} */
function mail_(to, subject, body, o, x) {
  if (typeof mailSend_ === 'function') return mailSend_(to, subject, body, o, x);
  MailApp.sendEmail({ to: to, subject: subject, body: body, name: productName_() });
}
/* ---------- 登入連結（店主登入、註冊驗證、設定密碼）----------
   信裡不放驗證碼，只放一顆按鈕：?ml=連結編號。按下後連結頁在背景用這組驗證碼完成驗證（使用者看不到驗證碼），
   原本按「寄出」的那個頁面也會自動往下一步（用 poll 編號輪詢，只有那個頁面知道 poll 編號）。
   連結 10 分鐘內有效、只能用一次；再寄一次，舊連結就失效。管理後台仍用驗證碼。 */
var LINK_TTL = 600;
var LINK_KINDS = { login: { btn: '確認登入', head: '確認登入', pre: '按下按鈕就會登入' }, reg: { btn: '完成 Email 驗證', head: '完成 Email 驗證', pre: '按下按鈕完成註冊' },
  reset: { btn: '設定密碼', head: '設定你的登入密碼', pre: '按下按鈕設定密碼' } };
function otpSend_(kind, email, purpose, poll) {
  var left = typeof MailApp.getRemainingDailyQuota === 'function' ? MailApp.getRemainingDailyQuota() : 100;
  if (left < 3) throw new Error('今天的寄信額度用完了，請明天再試，或聯絡客服。');
  var code = randDigits_(6), cache = CacheService.getScriptCache(), lk = LINK_KINDS[String(kind).split(':')[0]];
  if (lk) {
    var old = cache.get('mlk:' + kind); if (old) cache.remove('ml:' + old);                 /* 再寄一次：舊連結作廢 */
    var mid = rand_(32), url = webUrl_() + '?ml=' + mid;
    cache.put('otp:' + kind, JSON.stringify({ h: sha256_(code + '|' + kind + '|' + secret_()) }), LINK_TTL);
    cache.put('ml:' + mid, JSON.stringify({ k: kind, c: code, p: poll || '' }), LINK_TTL);
    cache.put('mlk:' + kind, mid, LINK_TTL);
    mail_(email, '【' + productName_() + '】' + lk.head,
      purpose + '\n\n請在 10 分鐘內打開下面的連結（只能用一次）：\n' + url + '\n\n如果不是你本人操作，請忽略這封信（也建議盡快更改密碼）。',
      typeof mailHtml_ === 'function' ? { eyebrow: 'VERIFICATION', title: lk.head, preheader: lk.pre + '，10 分鐘內有效',
        blocks: [mkP_(mkEsc_(purpose)), mkBtn_(lk.btn, url, MK.amber, MK.navy), mkNote_('連結 10 分鐘內有效，只能用一次。如果不是你本人操作，請忽略這封信，並盡快更改密碼。')],
        why: '你收到這封信，是因為有人用這個信箱在 SFD 系統登入、註冊或設定密碼。' } : null);
    return true;
  }
  cache.put('otp:' + kind, JSON.stringify({ h: sha256_(code + '|' + kind + '|' + secret_()) }), OTP_TTL);
  var head = { login: '你的登入驗證碼', reg: '完成 Email 驗證', reset: '設定密碼的驗證碼', admin: '管理後台驗證碼' }[String(kind).split(':')[0]] || '你的驗證碼';
  mail_(email, '【' + productName_() + '】驗證碼 ' + code,
    purpose + '\n\n驗證碼：' + code + '\n\n5 分鐘內有效。如果不是你本人操作，請忽略這封信（也建議盡快更改密碼）。',
    typeof mailHtml_ === 'function' ? { eyebrow: 'VERIFICATION', title: head, preheader: '驗證碼 ' + code + '，5 分鐘內有效',
      blocks: [mkP_(mkEsc_(purpose)), mkCode_(code, '5 分鐘內有效，只能用一次'), mkNote_('如果不是你本人操作，請忽略這封信，並盡快更改密碼。')],
      why: '你收到這封信，是因為有人用這個信箱在 SFD 系統登入、註冊或設定密碼。' } : null);
  return true;
}
/* 驗證碼正確回傳 true 並作廢；錯誤累計次數，達上限鎖定 */
function otpCheck_(kind, lockKey, code) {
  var c = CacheService.getScriptCache(), raw = c.get('otp:' + kind);
  if (!raw) return false;
  var o = JSON.parse(raw);
  if (sha256_(String(code || '').replace(/\D/g, '') + '|' + kind + '|' + secret_()) !== o.h) { failBump_(lockKey); return false; }
  c.remove('otp:' + kind); failClear_(lockKey);
  return true;
}

/* ================= 店主登入：統編＋密碼 → Email 驗證碼 → 通行證 ================= */
function authStart(taxId, password) {
  resetCtx_();
  if (!saas_()) return fail_('off', '線上服務尚未啟用');
  var id = String(taxId || '').replace(/\D/g, '');
  if (lockedOut_('t' + id)) return fail_('locked', LOCK_MSG);
  var shop = id ? shopByTaxId_(id) : null;
  if (!shop || !pwOk_(password, shop)) {
    var n = failBump_('t' + id); cLog_(shop && shop.id, id, '登入', '密碼錯誤', '第 ' + n + ' 次');
    return fail_('bad', '統編或密碼不正確');
  }
  var lic = licOf_(shop);
  if (shop.status === 'pending') return fail_('unpaid', shop.verified ? '尚未完成訂閱付款，付款後才會寄出驗證碼。' : '這個統編還沒完成 Email 驗證，請先完成註冊。', { verified: shop.verified });
  if (lic.mode === 'blocked') return fail_('blocked', lic.msg);
  if (testAcct_(id)) { CacheService.getScriptCache().put('pwok:' + id, '1', OTP_TTL); cLog_(shop.id, id, '登入', '測試帳號免驗證碼', ''); return { ok: true, mail: '（測試帳號：免驗證碼，任意填）', name: shop.name, bypass: true }; }
  var poll = rand_(32);
  try { otpSend_('login:' + id, shop.email, '你正在登入「' + shop.name + '」的菜單系統（確認訂閱狀態：' + lic.label + (shop.expires ? '，到期日 ' + shop.expires : '') + '）。', poll); }
  catch (e) { return fail_('mail', e.message); }
  cLog_(shop.id, id, '登入', '已寄登入連結', '');
  return { ok: true, mail: maskMail_(shop.email), name: shop.name, poll: poll };
}

function authVerify(taxId, code, device) {
  resetCtx_();
  var id = String(taxId || '').replace(/\D/g, '');
  if (lockedOut_('t' + id)) return fail_('locked', LOCK_MSG);
  var shop = id ? shopByTaxId_(id) : null;
  if (!shop) return fail_('badcode', '驗證碼不正確或已過期');
  var bypass = testAcct_(id) && !!CacheService.getScriptCache().get('pwok:' + id);      /* 測試帳號：要先通過 authStart 的密碼檢查 */
  if (!bypass && !otpCheck_('login:' + id, 't' + id, code)) return fail_('badcode', '驗證碼不正確或已過期');
  return ownerLogin_(shop, device, '');
}
/* 驗證都通過後：發店主通行證給這台裝置 */
function ownerLogin_(shop, device, note) {
  var lic = licOf_(shop);
  if (lic.mode === 'blocked') return fail_('blocked', lic.msg);
  shop = ensureProvisioned_(shop);
  var tok = tokenMake_({ s: shop.id, r: 'owner', u: 'owner', v: shop.tv, d: sha256_(String(device || '')).slice(0, 8) }, OWNER_DAYS);
  cLog_(shop.id, shop.taxId, '登入', '成功', note || '');
  return sessionInfo_(shop, tok, 'owner');
}

/* ---------- 按下信裡的連結 ----------
   mlUse：連結頁一打開就呼叫（使用者不用輸入任何東西）。登入／註冊驗證直接完成；設定密碼要先讓使用者填新密碼（mlResetDone）。
   完成後在 mlp:<poll> 留一筆紀錄，原本寄信的那個頁面用 mlPoll 拿到後也會自動進下一步。 */
function mlRec_(id) {
  id = String(id || '').replace(/[^0-9a-f]/gi, '');
  var raw = id ? CacheService.getScriptCache().get('ml:' + id) : null;
  if (!raw) return null;
  var o = JSON.parse(raw), p = String(o.k).split(':');
  return { id: id, kind: p[0], taxId: p[1], code: o.c, poll: o.p, k: o.k };
}
var ML_GONE = '這個連結已經用過或已過期（10 分鐘內有效）。請回到登入頁重新寄一次。';
function mlDone_(m, r) {
  var c = CacheService.getScriptCache();
  c.remove('ml:' + m.id); if (c.get('mlk:' + m.k) === m.id) c.remove('mlk:' + m.k);
  if (r.ok && m.poll) c.put('mlp:' + m.poll, JSON.stringify({ k: m.kind, t: m.taxId, r: m.kind === 'reg' ? { status: r.status, label: r.label, expires: r.expires, pay: r.pay || null } : null }), LINK_TTL);
}
function mlUse(id, device) {
  resetCtx_();
  if (!saas_()) return fail_('off', '線上服務尚未啟用');
  var m = mlRec_(id); if (!m) return fail_('gone', ML_GONE);
  var shop = shopByTaxId_(m.taxId);
  if (m.kind === 'reset') return { ok: true, kind: 'reset', need: 'pw', name: shop ? shop.name : '', first: !!(shop && !shop.hash) };
  var r = m.kind === 'login' ? authVerify(m.taxId, m.code, device) : m.kind === 'reg' ? regVerify(m.taxId, m.code) : fail_('gone', ML_GONE);
  mlDone_(m, r);
  r.kind = m.kind; if (m.kind === 'reg') r.taxId = m.taxId;
  return r;
}
function mlResetDone(id, newPw, device) {
  var m = mlRec_(id); if (!m || m.kind !== 'reset') return fail_('gone', ML_GONE);
  var r = actDone(m.taxId, m.code, newPw, device);
  if (r.ok) mlDone_(m, r);
  else if (r.code === 'badcode') { CacheService.getScriptCache().remove('ml:' + m.id); r.msg = ML_GONE; }   /* 驗證碼已失效（例如又寄了一次）：這個連結也作廢 */
  r.kind = 'reset'; return r;
}
/* 原本的頁面每幾秒問一次：信裡的連結按了沒？按了就換這台裝置登入（只有拿到 poll 編號的頁面能問，poll 編號只回給輸入密碼的那個頁面） */
function mlPoll(poll, device) {
  resetCtx_();
  poll = String(poll || '').replace(/[^0-9a-f]/gi, '');
  var c = CacheService.getScriptCache(), raw = poll ? c.get('mlp:' + poll) : null;
  if (!raw) return { ok: true, wait: true };
  c.remove('mlp:' + poll);
  var o = JSON.parse(raw), shop = shopByTaxId_(o.t);
  if (!shop) return fail_('gone', ML_GONE);
  if (o.k === 'reg') { var x = o.r || {}; x.ok = true; x.kind = 'reg'; x.taxId = o.t; return x; }
  if (o.k === 'reset' && shop.status === 'pending') return { ok: true, kind: 'reset', set: true, msg: '密碼已設定。完成付款開通後，就能用統編＋密碼登入。' };
  var r = ownerLogin_(shop, device, '從信件連結登入（原頁面）'); r.kind = o.k; return r;
}

function sessionInfo_(shop, tok, role) {
  var u = webUrl_(), lic = licOf_(shop);
  return {
    ok: true, token: tok, role: role, shop: { id: shop.id, name: shop.name }, lic: { label: lic.label, expires: lic.expires, mode: lic.mode, msg: lic.msg, daysLeft: lic.daysLeft },
    urls: { menu: u + '?t=' + tok, tools: u + '?p=tools&t=' + tok, account: u + '?p=account&t=' + tok, staff: role === 'owner' ? u + '?p=staff&t=' + tok : '', home: u + '?p=home&t=' + tok, ledger: u + '?p=ledger&t=' + tok, customer: u + '?s=' + shop.id },
    sheetUrl: shop.ssId ? 'https:' + '/' + '/docs.google.com/spreadsheets/d/' + shop.ssId : ''
  };
}

/* 登入頁自動續登：通行證還有效就直接回網址 */
function authCheck(token) {
  try {
    resetCtx_();
    var p = tokenRead_(token);
    if (p.r === 'admin') return { ok: true, role: 'admin', url: webUrl_() + '?p=admin&a=' + token };
    var c = authGuard_(token, false);
    return sessionInfo_(c.shop, token, c.role);
  } catch (e) { return fail_('expired', e.message); }
}

/* ================= 夥伴邀請 ================= */
function ownInvite(token, name) {
  var c = authGuard_(token, true);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以邀請夥伴');
  name = String(name || '').replace(/[<>]/g, '').trim().slice(0, 20);
  if (!name) return fail_('bad', '請填夥伴的名字或暱稱');
  var n = cRows_('partners').filter(function (r) { return String(r['店家編號']) === c.shopId && r['狀態'] !== '停用'; }).length;
  if (n >= 30) return fail_('limit', '夥伴帳號已達上限（30 個），請先停用不用的帳號');
  var code = rand_(12).toUpperCase().replace(/[^A-Z0-9]/g, 'X'), exp = addDaysStr_(todayStr_(), 7);
  var id = 'P' + Date.now().toString(36).toUpperCase() + rand_(2).toUpperCase();
  cAppend_('partners', { '夥伴編號': id, '店家編號': c.shopId, '名稱': name, '角色': 'staff', '邀請碼雜湊': sha256_(code + secret_()), '邀請到期': exp, '綁定裝置': '', '狀態': '邀請中', '建立時間': nowD_(), '最後使用': '' });
  cLog_(c.shopId, 'owner', '邀請夥伴', '成功', name);
  return { ok: true, id: id, code: code, link: webUrl_() + '?invite=' + code, expires: exp };
}

function authInvite(code, device) {
  resetCtx_();
  code = String(code || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (lockedOut_('inv')) return fail_('locked', LOCK_MSG);
  var h = sha256_(code + secret_()), today = todayStr_();
  var r = code.length >= 8 ? cRows_('partners').filter(function (x) { return x['邀請碼雜湊'] === h && x['狀態'] === '邀請中'; })[0] : null;
  if (!r || dayOf_(r['邀請到期']) < today) { failBump_('inv'); return fail_('badcode', '邀請連結無效或已過期，請請店長重新邀請'); }
  var shop = shopById_(String(r['店家編號'])), lic = shop ? licOf_(shop) : null;
  if (!shop || lic.mode === 'blocked') return fail_('blocked', lic ? lic.msg : '找不到這家店');
  cUpdate_('partners', r._r, { '狀態': '使用中', '綁定裝置': sha256_(String(device || '')).slice(0, 12), '邀請碼雜湊': '', '最後使用': nowD_() });
  var id = String(r['夥伴編號']); dropPartnerCache_(id);
  cLog_(shop.id, id, '夥伴綁定', '成功', String(r['名稱']));
  return sessionInfo_(shop, tokenMake_({ s: shop.id, r: 'staff', u: id }, STAFF_DAYS), 'staff');
}

function ownPartners(token) {
  var c = authGuard_(token, false);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以管理夥伴');
  return { ok: true, partners: cRows_('partners').filter(function (r) { return String(r['店家編號']) === c.shopId; }).map(function (r) {
    return { id: String(r['夥伴編號']), name: String(r['名稱']), status: String(r['狀態']), bound: !!r['綁定裝置'], created: stampOf_(r['建立時間']), lastUsed: stampOf_(r['最後使用']), inviteExp: dayOf_(r['邀請到期']) };
  }) };
}
function ownPartnerSet(token, id, status) {
  var c = authGuard_(token, true);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以管理夥伴');
  if (['停用', '使用中'].indexOf(status) < 0) return fail_('bad', '狀態不正確');
  var r = cRows_('partners').filter(function (x) { return String(x['夥伴編號']) === String(id) && String(x['店家編號']) === c.shopId; })[0];
  if (!r) return fail_('none', '找不到這個夥伴');
  if (status === '使用中' && !r['綁定裝置']) return fail_('bad', '這個邀請還沒被使用，不需要啟用');
  cUpdate_('partners', r._r, { '狀態': status });
  dropPartnerCache_(String(id));                       /* 立即生效：下一次寫入就會被擋 */
  cLog_(c.shopId, 'owner', status === '停用' ? '停用夥伴' : '啟用夥伴', '成功', String(r['名稱']));
  return ownPartners(token);
}
function ownRevokeAll(token) {
  var c = authGuard_(token, false);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以操作');
  var shop = c.shop; shop.tv += 1; saveShop_(shop, ['tv']);
  cLog_(c.shopId, 'owner', '全部登出', '成功', '');
  return { ok: true };
}
function ownChangePw(token, oldPw, newPw) {
  var c = authGuard_(token, false);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以改密碼');
  var shop = c.shop;
  if (!pwOk_(oldPw, shop)) return fail_('bad', '舊密碼不正確');
  var bad = pwRule_(newPw); if (bad) return fail_('bad', bad);
  shop.salt = rand_(16); shop.hash = pwHash_(newPw, shop.salt); shop.tv += 1;
  saveShop_(shop, ['salt', 'hash', 'tv']);
  cLog_(c.shopId, 'owner', '改密碼', '成功', '');
  return { ok: true, relogin: true };
}
function ownLicense(token) {
  var c = authGuard_(token, false), shop = c.shop, lic = licOf_(shop);
  return { ok: true, plan: PLANS[shop.plan] ? PLANS[shop.plan].name : shop.plan, lic: lic, name: shop.name, taxId: shop.taxId,
    pays: cRows_('pays').filter(function (r) { return String(r['店家編號']) === c.shopId; }).slice(-12).reverse().map(payView_) };
}

/* ================= 註冊 ================= */
function regCreate(f) {
  resetCtx_();
  if (!saas_()) return fail_('off', '線上服務尚未啟用');
  f = f || {};
  var company = String(f.company || '').replace(/[<>]/g, '').trim().slice(0, 40), taxId = String(f.taxId || '').replace(/\D/g, '');
  var owner = String(f.owner || '').replace(/[<>]/g, '').trim().slice(0, 20), email = String(f.email || '').trim().toLowerCase();
  if (!company) return fail_('bad', '請填公司（或商號）名稱');
  if (!taxIdOk_(taxId)) return fail_('bad', '統編不正確，請再確認 8 碼數字');
  if (!owner) return fail_('bad', '請填負責人姓名');
  if (!emailOk_(email)) return fail_('bad', 'Email 格式不正確');
  var bad = pwRule_(f.password); if (bad) return fail_('bad', bad);
  if (f.agree !== true) return fail_('bad', '請先閱讀並同意服務條款與隱私權政策');
  var plan = PLANS[f.plan] ? f.plan : 'trial';
  if (lockedOut_('reg')) return fail_('locked', LOCK_MSG);
  var c = CacheService.getScriptCache(), rk = 'regn:' + todayStr_(), rn = Number(c.get(rk) || 0);
  if (rn >= 30) return fail_('limit', '今天的註冊人數已達上限，請明天再試');
  var old = shopByTaxId_(taxId);
  if (old) return fail_('exists', old.verified ? '這個統編已經註冊過了，請直接登入；忘記密碼請聯絡客服。' : '這個統編已經註冊，但還沒完成 Email 驗證。請聯絡客服重寄驗證信。');
  var salt = rand_(16), id = nextShopId_();
  cAppend_('shops', { '店家編號': id, '公司名稱': company, '統編': taxId, '負責人': owner, '登入Email': email, '方案': plan, '狀態': ST_LABEL.pending, '到期日': '',
    '試算表ID': '', '資料夾ID': '', '密碼鹽': salt, '密碼雜湊': pwHash_(f.password, salt), '通行證版本': 1, '建立時間': nowD_(), '最後使用': '',
    '名稱鎖定至': addDaysStr_(todayStr_(), 180), '備註': '', 'Email已驗證': false });
  c.put(rk, String(rn + 1), 86400);
  var poll = rand_(32);
  try { otpSend_('reg:' + taxId, email, '歡迎註冊「' + productName_() + '」（公司：' + company + '）。請按下面的按鈕完成 Email 驗證。', poll); }
  catch (e) { return fail_('mail', e.message); }
  cLog_(id, taxId, '註冊', '已寄驗證連結', plan);
  return { ok: true, id: id, mail: maskMail_(email), poll: poll };
}

/* 註冊的 Email 驗證。試用方案驗證完就開始試用；其他方案進入付款（Billing.gs） */
function regVerify(taxId, code) {
  resetCtx_();
  var id = String(taxId || '').replace(/\D/g, '');
  if (lockedOut_('r' + id)) return fail_('locked', LOCK_MSG);
  var shop = id ? shopByTaxId_(id) : null;
  if (!shop || !otpCheck_('reg:' + id, 'r' + id, code)) return fail_('badcode', '驗證碼不正確或已過期');
  shop.verified = true;
  if (shop.status === 'pending' && shop.plan === 'trial') { shop.status = 'trial'; shop.expires = addDaysStr_(todayStr_(), PLANS.trial.trialDays); }
  saveShop_(shop, ['verified', 'status', 'expires']);
  cLog_(shop.id, id, '註冊', 'Email 已驗證', shop.status);
  var out = { ok: true, status: shop.status, label: ST_LABEL[shop.status], expires: shop.expires };
  if (shop.status === 'pending') out.pay = billingStart_(shop, shop.plan, 'month');
  return out;
}

/* 忘記密碼：寄驗證碼到註冊信箱，驗證後設新密碼 */
function pwResetStart(taxId) {
  resetCtx_();
  var id = String(taxId || '').replace(/\D/g, '');
  if (lockedOut_('p' + id)) return fail_('locked', LOCK_MSG);
  var shop = id ? shopByTaxId_(id) : null, poll = rand_(32);
  if (shop && shop.verified) {
    var why = shop.hash ? '你申請重設「' + shop.name + '」的登入密碼。請按下面的按鈕設定新密碼。' : '歡迎使用「' + shop.name + '」的 ' + productName_() + '。這是首次開通：請按下面的按鈕設定你自己的登入密碼（客服不會知道這組密碼）。';
    try { otpSend_('reset:' + id, shop.email, why, poll); } catch (e) { return fail_('mail', e.message); }
  }
  failBump_('p' + id);                                  /* 不論有沒有這個統編，回應一樣，避免被拿來探測 */
  return { ok: true, mail: shop ? maskMail_(shop.email) : '', poll: poll };
}
function pwResetDone(taxId, code, newPw) {
  resetCtx_();
  var id = String(taxId || '').replace(/\D/g, ''), shop = id ? shopByTaxId_(id) : null;
  var bad = pwRule_(newPw); if (bad) return fail_('bad', bad);
  if (!shop || !otpCheck_('reset:' + id, 'p' + id, code)) return fail_('badcode', '驗證碼不正確或已過期');
  shop.salt = rand_(16); shop.hash = pwHash_(newPw, shop.salt); shop.tv += 1;
  saveShop_(shop, ['salt', 'hash', 'tv']);
  cLog_(shop.id, id, '重設密碼', '成功', '');
  return { ok: true };
}
/* 首次開通（或忘記密碼）：驗證碼正確就設定密碼，帳號可以用就直接登入這台裝置 */
function actDone(taxId, code, newPw, device) {
  var id = String(taxId || '').replace(/\D/g, ''), first = !!(shopByTaxId_(id) && !shopByTaxId_(id).hash);
  var r = pwResetDone(taxId, code, newPw); if (!r.ok) return r;
  var shop = shopByTaxId_(id), lic = licOf_(shop);
  if (first) cLog_(shop.id, id, '首次開通', '已設定密碼', '');
  if (shop.status === 'pending') return { ok: true, set: true, msg: '密碼已設定。完成付款開通後，就能用統編＋密碼登入。' };
  if (lic.mode === 'blocked') return { ok: true, set: true, msg: lic.msg };
  shop = ensureProvisioned_(shop);
  var tok = tokenMake_({ s: shop.id, r: 'owner', u: 'owner', v: shop.tv, d: sha256_(String(device || '')).slice(0, 8) }, OWNER_DAYS);
  cLog_(shop.id, id, '登入', '成功', first ? '首次開通' : '重設密碼後');
  var out = sessionInfo_(shop, tok, 'owner'); out.set = true; return out;
}
/* 開通信：請店主自己設定密碼（我們不寄、也不保存明碼密碼） */
function actMail_(s, again) {
  var u = webUrl_() + '?p=activate', lic = licOf_(s), o = null;
  if (typeof mailHtml_ === 'function') o = { eyebrow: again ? 'PASSWORD' : 'WELCOME', title: again ? '請重新設定登入密碼' : s.name + '的帳號開好了', preheader: again ? '原本的密碼已失效，請用驗證碼設定新密碼' : '設定你自己的密碼，設好就直接登入',
    blocks: [mkP_(again ? '客服已依你的要求重設「' + mkEsc_(s.name) + '」的登入密碼，<b>原本的密碼已失效</b>，所有裝置也已登出。' : '歡迎使用 SFD 系統。「' + mkEsc_(s.name) + '」的帳號已建立' + (s.status === 'pilot' ? '，<b>試營運到 ' + mkEsc_(s.expires) + '</b>，全功能開放，輸出不加浮水印' : '') + '。'),
      mkP_('只要三步，設好就會直接登入：'),
      mkSteps_(['按下面的按鈕，打開「首次開通」', '輸入統一編號 <b style="font-family:' + MK.num + ';font-size:18px">' + mkEsc_(s.taxId) + '</b>，會再寄一封「設定密碼」的信到這個信箱', '按信裡的「設定密碼」，設定你自己的密碼（8 個字以上，要有英文和數字）'], MK.navy),
      mkBtn_(again ? '設定新密碼' : '設定密碼並登入', u, MK.amber, MK.navy),
      mkNote_('客服看不到、也不會跟你要這組密碼。之後登入：統編＋密碼，再按登入信裡的「確認登入」。' + (lic.mode === 'blocked' && s.status === 'pending' ? '<br><b>帳號在完成付款後才能登入使用。</b>' : ''))],
    why: again ? '你收到這封信，是因為你請客服重設密碼。' : '你收到這封信，是因為星樂創意替你的店開通了 SFD 系統。' };
  mail_(s.email, '【' + productName_() + '】' + (again ? '請重新設定登入密碼' : '「' + s.name + '」帳號已開通，請設定登入密碼'),
    (again ? '客服已依你的要求重設「' + s.name + '」的登入密碼，原本的密碼已失效，所有裝置也已登出。' : '「' + s.name + '」的 ' + productName_() + ' 帳號已建立' + (s.status === 'pilot' ? '，試營運到 ' + s.expires + '（全功能，輸出不加浮水印）' : '') + '。') +
    '\n\n請用手機或電腦打開下面的連結，按「首次開通」：\n' + u +
    '\n\n1. 輸入統一編號 ' + s.taxId + '\n2. 會再寄一封「設定密碼」的信到這個信箱（10 分鐘內有效）\n3. 按信裡的按鈕，設定你自己的密碼（8 個字以上，要有英文和數字）\n\n設定好就會直接登入。之後登入：統編＋密碼，再按登入信裡的「確認登入」。' +
    (lic.mode === 'blocked' && s.status === 'pending' ? '\n\n提醒：帳號在完成付款後才能登入使用。' : ''), o);
}

/* ================= 管理後台（只有我方） ================= */
function admStart(email) {
  resetCtx_();
  email = String(email || '').trim().toLowerCase();
  if (lockedOut_('a' + email)) return fail_('locked', LOCK_MSG);
  if (adminEmails_().indexOf(email) >= 0) { try { otpSend_('admin:' + email, email, '你正在登入「' + productName_() + '」管理後台。'); } catch (e) { return fail_('mail', e.message); } }
  else failBump_('a' + email);
  return { ok: true, mail: maskMail_(email) };
}
function admVerify(email, code) {
  resetCtx_();
  email = String(email || '').trim().toLowerCase();
  if (lockedOut_('a' + email)) return fail_('locked', LOCK_MSG);
  if (adminEmails_().indexOf(email) < 0 || !otpCheck_('admin:' + email, 'a' + email, code)) return fail_('badcode', '驗證碼不正確或已過期');
  cLog_('', email, '管理員登入', '成功', '');
  var tok = tokenMake_({ s: '', r: 'admin', u: email }, ADMIN_DAYS);
  return { ok: true, token: tok, url: webUrl_() + '?p=admin&a=' + tok };
}
function admGuard_(token) {
  resetCtx_();
  var p = tokenRead_(token);
  if (p.r !== 'admin' || adminEmails_().indexOf(String(p.u).toLowerCase()) < 0) throw new Error('沒有權限');
  CTX = { admin: p.u };
  return p.u;
}
function shopView_(s) {
  var lic = licOf_(s);
  return { id: s.id, name: s.name, taxId: s.taxId, owner: s.owner, email: s.email, plan: s.plan, planName: PLANS[s.plan] ? PLANS[s.plan].name : s.plan, status: s.status, statusLabel: lic.label || ST_LABEL[s.status],
    expires: s.expires, mode: lic.mode, daysLeft: lic.daysLeft, msg: lic.msg, ssId: s.ssId, created: s.created, lastUsed: s.lastUsed, nameLock: s.nameLock, note: s.note, verified: s.verified };
}
function payView_(r) {
  return { id: String(r['付款編號']), plan: String(r['方案']), cycle: String(r['週期']), amount: Number(r['金額']) || 0, provider: String(r['供應商']), status: String(r['狀態']),
    created: stampOf_(r['建立時間']), paidAt: stampOf_(r['付款時間']), from: dayOf_(r['期間起']), to: dayOf_(r['期間迄']), invoice: String(r['發票號碼'] || ''), note: String(r['備註'] || '') };
}
function admOverview(token) {
  admGuard_(token);
  var shops = allShops_().map(shopView_), c = {};
  shops.forEach(function (s) { c[s.statusLabel] = (c[s.statusLabel] || 0) + 1; });
  return { ok: true, shops: shops, counts: c, plans: PLANS, quota: typeof MailApp.getRemainingDailyQuota === 'function' ? MailApp.getRemainingDailyQuota() : null,
    center: sp0_().getProperty('centerId') };
}
function admShop(token, id) {
  admGuard_(token);
  var s = shopById_(id); if (!s) return fail_('none', '找不到這家店');
  return { ok: true, shop: shopView_(s),
    partners: cRows_('partners').filter(function (r) { return String(r['店家編號']) === s.id; }).map(function (r) { return { id: String(r['夥伴編號']), name: String(r['名稱']), status: String(r['狀態']), lastUsed: stampOf_(r['最後使用']) }; }),
    pays: cRows_('pays').filter(function (r) { return String(r['店家編號']) === s.id; }).reverse().map(payView_),
    logs: cRows_('logs').filter(function (r) { return String(r['店家編號']) === s.id; }).slice(-30).reverse().map(function (r) { return { at: stampOf_(r['時間']), who: String(r['誰']), act: String(r['動作']), res: String(r['結果']), note: String(r['備註']) }; }) };
}
/* 新增或修改店家基本資料。統編不同視為新客戶（不能改統編）；公司名稱鎖定期間內改名需要 reason（人工審核後） */
function admSaveShop(token, f) {
  var who = admGuard_(token); f = f || {};
  var name = String(f.name || '').replace(/[<>]/g, '').trim().slice(0, 40), owner = String(f.owner || '').replace(/[<>]/g, '').trim().slice(0, 20), email = String(f.email || '').trim().toLowerCase();
  if (!name || !owner || !emailOk_(email)) return fail_('bad', '公司名稱、負責人、Email 都要填（Email 格式要正確）');
  var plan = PLANS[f.plan] ? f.plan : 'pro';
  if (f.id) {
    var s = shopById_(f.id); if (!s) return fail_('none', '找不到這家店');
    if (f.taxId && String(f.taxId).replace(/\D/g, '') !== s.taxId) return fail_('bad', '統編不同視為新客戶，請另外新增店家');
    if (name !== s.name) {
      if (s.nameLock && s.nameLock > todayStr_() && !String(f.reason || '').trim()) return fail_('locked', '公司名稱 ' + s.nameLock + ' 前不能修改。若已審核負責人本人的變更登記資料，請填「審核說明」再送出。');
      cLog_(s.id, who, '改公司名稱', '成功', s.name + ' → ' + name + '｜' + String(f.reason || ''));
    }
    s.name = name; s.owner = owner; s.email = email; s.plan = plan; s.note = String(f.note || '').slice(0, 300);
    saveShop_(s, ['name', 'owner', 'email', 'plan', 'note']);
    cLog_(s.id, who, '修改店家資料', '成功', '');
    return { ok: true, shop: shopView_(s) };
  }
  var taxId = String(f.taxId || '').replace(/\D/g, '');
  if (!taxIdOk_(taxId) && f.skipTaxCheck !== true) return fail_('bad', '統編檢查碼不正確（若確定正確，勾選「略過檢查碼」）');
  if (shopByTaxId_(taxId)) return fail_('exists', '這個統編已經有店家了');
  var id = nextShopId_(), pilot = f.start === 'pilot';
  cAppend_('shops', { '店家編號': id, '公司名稱': name, '統編': taxId, '負責人': owner, '登入Email': email, '方案': plan, '狀態': pilot ? ST_LABEL.pilot : ST_LABEL.pending, '到期日': pilot ? addDaysStr_(todayStr_(), PILOT_DAYS) : '', '試算表ID': '', '資料夾ID': '',
    '密碼鹽': '', '密碼雜湊': '', '通行證版本': 1, '建立時間': nowD_(), '最後使用': '', '名稱鎖定至': addDaysStr_(todayStr_(), 180), '備註': String(f.note || '').slice(0, 300), 'Email已驗證': true });
  cLog_(id, who, '新增店家', '成功', name + (pilot ? '（試營運 ' + PILOT_DAYS + ' 天）' : ''));
  var ns = shopById_(id), mailed = false;
  if (f.sendMail !== false) { try { actMail_(ns, false); mailed = true; cLog_(id, who, '寄開通信', '成功', maskMail_(email)); } catch (e) { cLog_(id, who, '寄開通信', '失敗', String(e.message || e)); } }
  return { ok: true, shop: shopView_(ns), mailed: mailed, mail: maskMail_(email) };
}
function admSetExpiry(token, id, date) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(date || ''))) return fail_('bad', '日期格式要是 2026-12-31');
  var old = s.expires; s.expires = date;
  if (s.status === 'pending') s.status = 'active';
  saveShop_(s, ['expires', 'status']); cLog_(s.id, who, '改到期日', '成功', old + ' → ' + date);
  return { ok: true, shop: shopView_(s) };
}
function admExtend(token, id, days) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  days = Math.max(1, Math.min(3660, parseInt(days, 10) || 0));
  var base = s.expires && s.expires >= todayStr_() ? s.expires : todayStr_();
  var old = s.expires; s.expires = addDaysStr_(base, days);
  if (s.status === 'pending' || s.status === 'suspended' || s.status === 'readonly') s.status = 'active';
  saveShop_(s, ['expires', 'status']); cLog_(s.id, who, '延長', '成功', old + ' → ' + s.expires + '（+' + days + ' 天）');
  return { ok: true, shop: shopView_(s) };
}
function admSetStatus(token, id, status) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  if (['trial', 'pilot', 'active', 'suspended', 'pending'].indexOf(status) < 0) return fail_('bad', '狀態不正確');
  var old = s.status; s.status = status;
  saveShop_(s, ['status']); cLog_(s.id, who, '改狀態', '成功', ST_LABEL[old] + ' → ' + ST_LABEL[status]);
  return { ok: true, shop: shopView_(s) };
}
function admResetPw(token, id) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  s.salt = ''; s.hash = ''; s.tv += 1;                 /* 舊密碼失效、所有裝置登出；店主用驗證碼自己設新密碼 */
  saveShop_(s, ['salt', 'hash', 'tv']);
  try { actMail_(s, true); } catch (e) { return fail_('mail', '密碼已清除，但寄信失敗：' + e.message + '。請店主到登入頁按「首次開通／忘記密碼」。'); }
  cLog_(s.id, who, '要求重設密碼', '成功', '已寄重新設定說明到 ' + maskMail_(s.email));
  return { ok: true, mail: maskMail_(s.email) };
}
/* 試營運：從今天起 PILOT_DAYS 天全功能（不加浮水印）；到期後照一般規則：7 天寬限 → 90 天唯讀 → 停用 */
function admPilot(token, id) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  var to = addDaysStr_(todayStr_(), PILOT_DAYS), old = s.status + ' ' + (s.expires || '');
  s.status = 'pilot'; if (!s.expires || s.expires < to) s.expires = to;
  saveShop_(s, ['status', 'expires']); cLog_(s.id, who, '開始試營運', '成功', old + ' → 試營運至 ' + s.expires);
  return { ok: true, shop: shopView_(s) };
}
/* 重寄開通信（店主說沒收到時） */
function admActMail(token, id) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  try { actMail_(s, false); } catch (e) { return fail_('mail', e.message); }
  cLog_(s.id, who, '寄開通信', '成功', maskMail_(s.email));
  return { ok: true, mail: maskMail_(s.email) };
}
function admRevoke(token, id) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  s.tv += 1; saveShop_(s, ['tv']); cLog_(s.id, who, '強制登出', '成功', '');
  return { ok: true };
}
function admProvision(token, id) {
  var who = admGuard_(token), s = shopById_(id);
  if (!s) return fail_('none', '找不到這家店');
  s = ensureProvisioned_(s); cLog_(s.id, who, '建立店家資料', '成功', s.ssId);
  return { ok: true, shop: shopView_(s) };
}
function admPartnerSet(token, partnerId, status) {
  var who = admGuard_(token);
  var r = cRows_('partners').filter(function (x) { return String(x['夥伴編號']) === String(partnerId); })[0];
  if (!r) return fail_('none', '找不到這個夥伴');
  cUpdate_('partners', r._r, { '狀態': status === '停用' ? '停用' : '使用中' }); dropPartnerCache_(String(partnerId));
  cLog_(String(r['店家編號']), who, '管理員改夥伴狀態', status, String(r['名稱']));
  return { ok: true };
}
