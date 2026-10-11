/**
 * 訂閱收款（Billing.gs）：方案價格、付款紀錄、金流供應商介面、付款成功自動延長到期日、每日提醒。
 *
 * 金流（綠界或其他）還沒決定，所以做成「供應商介面」：
 *   BILL_PROVIDERS[名稱] = {
 *     label,
 *     create(shop, pay)  → { url?, text? }     建立付款，回傳要給客人的付款網址或說明
 *     verify(params)     → { ok, payId, amount, extId, paid }   驗證金流通知（簽章），paid=true 才算付款成功
 *   }
 * 之後接新的金流只要新增一個供應商、在 Script Properties 把 billProvider 改成它。
 * 目前內建：manual（轉帳，由管理員按「已收款」）、test（測試用，簽章由 testPaySecret 決定）。
 * 重要：付款是否成功只信 verify() 驗過簽章的通知，絕不信瀏覽器傳來的「付款成功」。
 */

var BILL_PROVIDERS = {
  manual: {
    label: '轉帳（人工對帳）',
    create: function (shop, pay) {
      var info = sp0_().getProperty('bankInfo') || '請聯絡客服取得匯款帳號';
      return { text: '請匯款 ' + pay.amount + ' 元，匯款備註填「' + shop.taxId + '」。\n' + info + '\n收到款項後客服會為你開通。' };
    },
    verify: function () { return { ok: false }; }       /* 人工對帳沒有自動通知 */
  },
  test: {
    label: '測試金流',
    create: function (shop, pay) { return { url: webUrl_() + '?p=paytest&pay=' + pay.id, text: '（測試金流）付款編號 ' + pay.id }; },
    verify: function (p) {
      var secret = sp0_().getProperty('testPaySecret');
      if (!secret || !p) return { ok: false };
      var sig = hmacHex_([p.payId, p.amount, p.status].join('|'), secret);
      if (sig !== String(p.sig || '')) return { ok: false };
      return { ok: true, payId: String(p.payId), amount: Number(p.amount), extId: String(p.extId || ''), paid: p.status === 'paid' };
    }
  }
};
function provider_(name) {
  var n = name || sp0_().getProperty('billProvider') || 'manual';
  if (!BILL_PROVIDERS[n]) throw new Error('沒有這個金流供應商：' + n);
  return { name: n, p: BILL_PROVIDERS[n] };
}

function priceOf_(plan, cycle) {
  var pl = PLANS[plan]; if (!pl) throw new Error('沒有這個方案');
  return cycle === 'year' ? pl.month * 10 : pl.month;      /* 年繳 10 個月價（送 2 個月） */
}
function cycleDays_(cycle) { return cycle === 'year' ? 365 : 30; }

/* 建立一筆待付款 */
function billingStart_(shop, plan, cycle) {
  plan = PLANS[plan] && plan !== 'trial' ? plan : 'pro'; cycle = cycle === 'year' ? 'year' : 'month';
  var pr = provider_(), id = 'PAY' + Utilities.formatDate(nowD_(), 'Asia/Taipei', 'yyMMdd') + rand_(5).toUpperCase();
  var pay = { id: id, amount: priceOf_(plan, cycle) };
  cAppend_('pays', { '付款編號': id, '店家編號': shop.id, '方案': plan, '週期': cycle, '金額': pay.amount, '供應商': pr.name, '外部單號': '', '狀態': '待付款', '建立時間': nowD_() });
  var r = pr.p.create(shop, pay) || {};
  cLog_(shop.id, shop.taxId, '建立付款', pr.name, id + '｜' + plan + '/' + cycle + '｜' + pay.amount);
  return { payId: id, amount: pay.amount, plan: plan, cycle: cycle, provider: pr.name, url: r.url || '', text: r.text || '' };
}

/* 付款成功：延長到期日、開通、寄收據、（之後）開發票。同一筆只會處理一次 */
function applyPayment_(shop, payRow, extId) {
  if (String(payRow['狀態']) === '已付款') return false;
  var today = todayStr_(), plan = String(payRow['方案']), cycle = String(payRow['週期']);
  var from = shop.expires && shop.expires >= today ? shop.expires : today, to = addDaysStr_(from, cycleDays_(cycle));
  cUpdate_('pays', payRow._r, { '狀態': '已付款', '付款時間': nowD_(), '期間起': from, '期間迄': to, '外部單號': extId || payRow['外部單號'] || '' });
  shop.plan = plan; shop.expires = to;
  if (shop.status !== 'suspended') shop.status = 'active';
  saveShop_(shop, ['plan', 'expires', 'status']);
  var inv = invoiceHook_(shop, payRow);
  if (inv) cUpdate_('pays', payRow._r, { '發票號碼': inv });
  try { mail_(shop.email, '【' + productName_() + '】收到款項，訂閱已開通', '「' + shop.name + '」已收到 ' + payRow['金額'] + ' 元（' + (PLANS[plan] || {}).name + '，' + (cycle === 'year' ? '年繳' : '月繳') + '）。\n訂閱期間：' + from + ' ～ ' + to + (inv ? '\n發票號碼：' + inv : '\n電子發票會另外寄出。') + '\n\n現在可以用統編＋密碼登入使用。',
    typeof mailHtml_ === 'function' ? { eyebrow: 'PAYMENT RECEIVED', title: '收到款項，訂閱已開通', preheader: 'NT$' + Number(payRow['金額']).toLocaleString('en-US') + ' 已入帳，訂閱到 ' + to,
      blocks: [mkP_('謝謝你。「' + mkEsc_(shop.name) + '」的訂閱已開通，資料和設定都直接沿用。'),
        mkRows_([['金額', 'NT$' + Number(payRow['金額']).toLocaleString('en-US') + '（含稅）', 1], ['方案', ((PLANS[plan] || {}).name || plan) + '・' + (cycle === 'year' ? '年繳' : '月繳')], ['訂閱期間', from + ' ～ ' + to, 1], ['付款編號', String(payRow['付款編號']), 1]].concat(inv ? [['發票號碼', inv, 1]] : [])),
        mkP_('<span style="font-size:14px;color:' + MK.mute + '">' + (inv ? '這封信可以當作付款紀錄。' : '電子發票會另外寄出。') + '</span>'),
        mkBtn_('登入 SFD 系統', webUrl_(), MK.amber, MK.navy)],
      why: '這是你在星樂創意的付款紀錄，請保留這封信。' } : null); } catch (e) {}
  cLog_(shop.id, 'billing', '付款成功', String(payRow['供應商']), String(payRow['付款編號']) + '｜至 ' + to);
  return true;
}
/* 電子發票：之後接上加值中心時實作；目前不開票，付款紀錄的發票號碼留空，由管理員處理 */
function invoiceHook_(shop, payRow) { return ''; }

/* 金流通知入口（doPost 的 payNotify 呼叫）。驗簽失敗一律不處理 */
function payNotify(providerName, params) {
  resetCtx_();
  var pr = provider_(providerName), v = pr.p.verify(params || {});
  if (!v.ok) { cLog_('', pr.name, '付款通知', '驗證失敗', ''); return { ok: false, msg: 'bad signature' }; }
  var row = cRows_('pays').filter(function (r) { return String(r['付款編號']) === v.payId; })[0];
  if (!row) return { ok: false, msg: 'unknown order' };
  if (Number(row['金額']) !== v.amount) { cLog_(String(row['店家編號']), pr.name, '付款通知', '金額不符', v.payId); return { ok: false, msg: 'amount mismatch' }; }
  var shop = shopById_(String(row['店家編號']));
  if (!shop) return { ok: false, msg: 'no shop' };
  if (!v.paid) { cUpdate_('pays', row._r, { '狀態': '失敗', '外部單號': v.extId }); cLog_(shop.id, pr.name, '付款失敗', v.payId, ''); return { ok: true, paid: false }; }
  var done = applyPayment_(shop, row, v.extId);
  return { ok: true, paid: true, already: !done };
}

/* ---------- 店主：自己續訂 ---------- */
function ownPayStart(token, plan, cycle) {
  var c = authGuard_(token, false);
  if (c.role !== 'owner') return fail_('perm', '只有店長可以訂閱');
  var out = billingStart_(c.shop, plan, cycle);
  out.ok = true; return out;
}

/* ---------- 管理員：人工標記已收款（轉帳、現金） ---------- */
function admMarkPaid(token, id, f) {
  var who = admGuard_(token), s = shopById_(id); f = f || {};
  if (!s) return fail_('none', '找不到這家店');
  var plan = PLANS[f.plan] && f.plan !== 'trial' ? f.plan : (PLANS[s.plan] && s.plan !== 'trial' ? s.plan : 'pro'), cycle = f.cycle === 'year' ? 'year' : 'month';
  var amount = f.amount != null && f.amount !== '' ? Number(f.amount) : priceOf_(plan, cycle);
  var pid = 'PAY' + Utilities.formatDate(nowD_(), 'Asia/Taipei', 'yyMMdd') + rand_(5).toUpperCase();
  var r = cAppend_('pays', { '付款編號': pid, '店家編號': s.id, '方案': plan, '週期': cycle, '金額': amount, '供應商': 'manual', '外部單號': '', '狀態': '待付款', '建立時間': nowD_(), '備註': String(f.note || '').slice(0, 200) });
  var row = cRows_('pays').filter(function (x) { return x._r === r; })[0];
  applyPayment_(s, row, '');
  cLog_(s.id, who, '人工收款', '成功', pid + '｜' + amount);
  return { ok: true, shop: shopView_(shopById_(s.id)) };
}

/* ---------- 每日工作：到期提醒、依日期更新狀態標示 ---------- */
function dailyJob() {
  resetCtx_();
  if (!saas_()) return;
  var p = sp0_(), today = todayStr_(), sent = 0;
  allShops_().forEach(function (s) {
    if (s.role === '分店' || s.status === 'pending' || s.status === 'suspended' || !s.expires) return;
    var lic = licOf_(s), left = daysBetween_(today, s.expires), tag = null;
    if (left === 7 || left === 3 || left === 1) tag = 'pre' + left;
    else if (left === -1) tag = 'grace';
    else if (left === -(GRACE_DAYS + 1)) tag = 'readonly';
    else if (left === -(GRACE_DAYS + READONLY_DAYS - 7)) tag = 'final';
    var want = lic.mode === 'blocked' ? 'suspended' : lic.mode === 'readonly' ? 'readonly' : lic.grace ? 'grace' : (s.status === 'trial' || s.status === 'pilot' ? s.status : 'active');
    if (want !== s.status) { s.status = want; saveShop_(s, ['status']); }
    if (!tag) return;
    var what = s.status === 'pilot' ? '試營運' : '訂閱';
    var k = 'remind:' + s.id;
    if (p.getProperty(k) === s.expires + '|' + tag) return;
    var msg = {
      pre7: what + '將在 7 天後（' + s.expires + '）到期，請記得' + (what === '試營運' ? '訂閱，資料會直接沿用，不用重建' : '續訂') + '。', pre3: what + '將在 3 天後（' + s.expires + '）到期。', pre1: what + '明天（' + s.expires + '）到期。',
      grace: '訂閱已到期，有 ' + GRACE_DAYS + ' 天寬限期可以照常使用，請盡快續訂。', readonly: '寬限期已結束，帳號目前變成「只能查看」。續訂後立刻恢復編輯。', final: '帳號即將停用，請盡快續訂以保留資料。'
    }[tag];
    var ro = null;
    if (typeof mailHtml_ === 'function') {
      var big = /^pre/.test(tag) ? mkBig_(String(left), '天', what + '到 ' + s.expires) : '';
      ro = { eyebrow: 'REMINDER', title: { pre7: what + '還有 7 天', pre3: what + '還有 3 天', pre1: what + '明天到期', grace: '訂閱已到期，寬限期照常使用', readonly: '帳號目前只能查看', final: '帳號即將停用' }[tag], preheader: msg,
        blocks: [big, mkP_(mkEsc_('「' + s.name + '」' + msg)), mkRows_([['基本版', '399／月・3,990／年', 1], ['專業版', '599／月・5,990／年', 1]]),
          mkBtn_(what === '試營運' ? '選方案並訂閱' : '續訂', webUrl_() + '?go=account', MK.amber, MK.navy),
          mkNote_('到期後還有 ' + GRACE_DAYS + ' 天寬限可以照常使用，之後 ' + READONLY_DAYS + ' 天只能查看，資料都會保留。價格皆含稅。')],
        why: '我們會在到期前 7、3、1 天提醒你。' };
    }
    try { mail_(s.email, '【' + productName_() + '】' + s.name + '：' + what + '提醒', '「' + s.name + '」' + msg + '\n\n續訂方式：登入後到「帳號」→「續訂」，或聯絡客服。', ro); sent++; p.setProperty(k, s.expires + '|' + tag); } catch (e) {}
  });
  return sent;
}
function ensureDailyTrigger_() {
  var has = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'dailyJob'; });
  if (!has) ScriptApp.newTrigger('dailyJob').timeBased().everyDays(1).atHour(3).create();
  return !has;
}
