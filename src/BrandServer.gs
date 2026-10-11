/**
 * 多門市／品牌（Brand.gs）第一階段：分店清單批量建立、品牌主進入分店、把菜單套用到多家分店。
 *
 * 結構：總店＝一般店家（有統編、密碼、可登入）；分店＝授權中心裡「品牌編號」指向總店、「角色」＝分店的店家。
 *  - 分店跟總店同統編，不能用統編登入；品牌主（總店店長）在「分店管理」頁按「開啟」，拿到以總店身分進入該分店的通行證
 *  - 分店的授權（到期日、狀態）跟著總店；單獨停用某家分店仍然有效
 *  - 每家分店有自己的試算表與資料夾，資料互相獨立；建立時繼承總店的外觀（顏色、Logo、標語）與菜單
 */
var BRANCH_DAYS = 7;       /* 品牌主進入分店的通行證有效天數 */
function branchMax_() { return Number(sp0_().getProperty('branchMax') || 30); }

function branchList_(hq) {
  return allShops_().filter(function (s) { return s.role === '分店' && s.brandId === hq.id; });
}
function brandGuard_(token, write) {
  var c = authGuard_(token, write !== false);
  if (c.role !== 'owner' || c.shop.brandId) throw new Error('只有總店店長可以管理分店');
  return c;
}
/* 暫時切換到另一家店的情境做事（寫入分店的設定、試算表） */
function withShop_(shop, fn) {
  var save = CTX, sm = _spMap;
  CTX = { shopId: shop.id, ssId: shop.ssId, role: 'owner', uid: 'brand', shop: shop, lic: licOf_(shop) };
  _spMap = null;
  try { return fn(); } finally { CTX = save; _spMap = sm; }
}

/* ---------- 分店清單的欄位檢查與整理 ---------- */
var DAY_MAP = { '日': 0, '天': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 0, '0': 0 };
var DAY_ORDER = [1, 2, 3, 4, 5, 6, 0];
function daysParse_(s) {
  s = String(s || '').replace(/[週周星期禮拜、，,\s]/g, '');
  if (!s) return null;
  var out = [], m, re = /([日天一二三四五六0-7])[至到~\-－]([日天一二三四五六0-7])/g;
  while ((m = re.exec(s))) {
    var a = DAY_ORDER.indexOf(DAY_MAP[m[1]]), b = DAY_ORDER.indexOf(DAY_MAP[m[2]]);
    for (var i = a; ; i = (i + 1) % 7) { if (out.indexOf(DAY_ORDER[i]) < 0) out.push(DAY_ORDER[i]); if (i === b) break; }
  }
  s = s.replace(re, '');
  for (var j = 0; j < s.length; j++) { if (DAY_MAP[s[j]] === undefined) throw new Error('營業日看不懂：「' + s[j] + '」（可寫：一二三四五、週一至週五、1-5）'); var d = DAY_MAP[s[j]]; if (out.indexOf(d) < 0) out.push(d); }
  return out.length ? DAY_ORDER.filter(function (d) { return out.indexOf(d) >= 0; }) : null;
}
function landParse_(s) {
  var d = String(s || '').replace(/\D/g, '');
  if (!d) return null;
  var areas = AREA_CODES.slice().sort(function (a, b) { return b.length - a.length; });
  for (var i = 0; i < areas.length; i++) if (d.indexOf(areas[i]) === 0) { var rest = d.slice(areas[i].length); landFmt_(areas[i], rest); return { area: areas[i], num: rest }; }
  throw new Error('市話要含區碼（例：02-2222-3333）');
}
/* row = { name, city, dist, road, land, mobile, days, hours, closed, lineId, email, note }（全是文字） */
function branchRowParse_(row, hq) {
  var errs = [], out = {};
  function T(f, max) { return cfgClean_(row[f], max); }
  out.name = T('name', 30);
  if (!out.name) errs.push('沒有分店名稱');
  out.city = T('city', 6).replace('臺', '台'); out.dist = T('dist', 8); out.road = T('road', 60);
  if ((out.city || out.dist) && !(out.city && out.dist)) errs.push('縣市和區要一起填');
  try { var l = landParse_(row.land); out.phoneLandArea = l ? l.area : ''; out.phoneLandNum = l ? l.num : ''; } catch (e) { errs.push(e.message); }
  try { out.phoneMobile = String(row.mobile || '').replace(/\D/g, ''); mobileFmt_(out.phoneMobile); } catch (e) { errs.push(e.message); }
  try { out.openDays = daysParse_(row.days); } catch (e) { errs.push(e.message); }
  out.hours = T('hours', 60); out.closedText = T('closed', 40);
  var lid = lineIdNorm_(row.lineId); if (lid === null) errs.push('LINE ID 格式不正確'); out.lineId = lid || '';
  out.email = String(row.email || '').trim().toLowerCase(); if (out.email && !emailOk_(out.email)) errs.push('店長 Email 格式不正確');
  out.note = T('note', 100);
  var base = String(shopCfgOf_(hq).name || hq.name);
  out.fullName = out.name.indexOf(base) >= 0 ? out.name : base + ' ' + out.name;
  return { ok: !errs.length, errors: errs, data: out };
}
/* 讀總店的店家設定（不管現在在哪個情境） */
function shopCfgOf_(shop) { return withShop_(shop, function () { return shopCfg_(); }); }

/* ---------- 對外 API ---------- */
function brandOverview(token) {
  var c = brandGuard_(token, false), hq = c.shop, base = webUrl_();
  var list = branchList_(hq).map(function (b) {
    var cfg = shopCfgOf_(b), lic = licOf_(b);
    var tk = tokenMake_({ s: b.id, r: 'owner', u: 'brand', b: hq.id, v: hq.tv }, BRANCH_DAYS);
    return { id: b.id, name: cfg.name || b.name, address: cfg.address || '', phone: cfg.phone || '', status: lic.label, mode: lic.mode, lastUsed: b.lastUsed, note: b.note,
      menuUrl: base + '?t=' + tk, toolsUrl: base + '?p=tools&t=' + tk, customerUrl: base + '?s=' + b.id, follow: followOf_(b), pricing: pricingSummary_(b) };
  });
  var cats = withShop_(hq, function () { return menuDraftOf_().sections.map(function (x) { return x.title; }); });
  return { ok: true, brand: { id: hq.id, name: shopCfgOf_(hq).name || hq.name, lic: licOf_(hq).label }, branches: list, max: branchMax_(), menuUrl: base + '?t=' + token, cats: cats };
}

/* 檢查整份分店清單（不寫入）：回傳每一列整理後的結果或錯誤 */
function brandBranchCheck(token, rows) {
  var c = brandGuard_(token, false), hq = c.shop;
  if (!Array.isArray(rows) || !rows.length) return fail_('bad', '清單裡沒有分店');
  if (rows.length > 60) return fail_('bad', '一次最多 60 家');
  var have = branchList_(hq), names = {}; have.forEach(function (b) { names[shopCfgOf_(b).name] = 1; });
  var seen = {};
  var out = rows.map(function (r) {
    var p = branchRowParse_(r || {}, hq);
    if (p.data.name && seen[p.data.fullName]) { p.ok = false; p.errors.push('清單裡分店名稱重複'); }
    if (p.data.name && names[p.data.fullName]) { p.ok = false; p.errors.push('這家分店已經存在'); }
    seen[p.data.fullName] = 1;
    return p;
  });
  var room = branchMax_() - have.length;
  return { ok: true, rows: out, room: room, tooMany: out.filter(function (x) { return x.ok; }).length > room };
}

/* 建立一家分店（一次一家，前端逐家呼叫，避免超過 Apps Script 6 分鐘上限） */
function brandBranchCreate(token, row, opts) {
  var c = brandGuard_(token, true), hq = c.shop; opts = opts || {};
  if (licOf_(hq).mode !== 'full') return fail_('lic', '總店目前不是可使用狀態，不能新增分店');
  if (branchList_(hq).length >= branchMax_()) return fail_('limit', '分店數量已達上限（' + branchMax_() + ' 家）');
  var p = branchRowParse_(row || {}, hq);
  if (!p.ok) return fail_('bad', p.errors.join('；'));
  var d = p.data, hqCfg = shopCfgOf_(hq);
  if (branchList_(hq).some(function (b) { return shopCfgOf_(b).name === d.fullName; })) return fail_('exists', '這家分店已經存在');
  var id = nextShopId_();
  cAppend_('shops', { '店家編號': id, '公司名稱': hq.name, '統編': hq.taxId, '負責人': hq.owner, '登入Email': hq.email, '方案': hq.plan, '狀態': ST_LABEL[hq.status], '到期日': hq.expires,
    '試算表ID': '', '資料夾ID': '', '密碼鹽': '', '密碼雜湊': '', '通行證版本': 1, '建立時間': nowD_(), '最後使用': '', '名稱鎖定至': '', '備註': d.note + (d.email ? '｜店長：' + d.email : ''),
    'Email已驗證': true, '品牌編號': hq.id, '角色': '分店' });
  var shop = provisionShop_(shopById_(id));
  /* 在分店的情境裡寫入：外觀、店家資料、Logo、菜單 */
  var menu = opts.copyMenu !== false ? withShop_(hq, menuDraftOf_) : null;
  withShop_(shop, function () {
    var cfg = Object.assign({}, hqCfg, { name: d.fullName, addrCity: d.city, addrDist: d.dist, addrRoad: d.road, address: d.city + d.dist + d.road,
      phoneLandArea: d.phoneLandArea, phoneLandNum: d.phoneLandNum, phoneMobile: d.phoneMobile,
      phone: [d.phoneLandNum ? landFmt_(d.phoneLandArea, d.phoneLandNum) : '', d.phoneMobile ? mobileFmt_(d.phoneMobile) : ''].filter(String).join('／'),
      openDays: d.openDays || hqCfg.openDays, hours: d.hours || hqCfg.hours, closedText: d.closedText || hqCfg.closedText,
      lineId: d.lineId || hqCfg.lineId, lineUrl: d.lineId ? lineUrlOf_(d.lineId) : hqCfg.lineUrl, notifyEmail: d.email || hqCfg.notifyEmail });
    delete cfg.nameA; delete cfg.nameB; delete cfg.heroSub; delete cfg.brandLegacy;
    props_().setProperty('cfg', JSON.stringify(cfg));
    props_().setProperty('onboarded', '1');
  });
  /* Logo：複製檔案到分店資料夾 */
  var logo = withShop_(hq, function () { return uploadedLogo_(); });
  if (logo) withShop_(shop, function () {
    var meta = Object.assign({}, logo, { srcId: logo.fileId }), folder = tFolder_();
    ['fileId', 'webId'].forEach(function (k) { if (logo[k]) { try { meta[k] = DriveApp.getFileById(logo[k]).makeCopy('logo_' + k + '_' + Date.now(), folder).getId(); } catch (e) { delete meta[k]; } } });
    props_().setProperty('t_logo', JSON.stringify(meta));
  });
  if (menu && menu.sections.length) {
    withShop_(shop, function () { menuApplyDraft_(pricedDraft_(menu, pricingNow_()), { label: '從總店複製菜單' }); });
    /* 分類顏色（分類名稱對得上才帶） */
    withShop_(shop, function () {
      var secs = sectionsOf_() || [], by = {}; menu.sections.forEach(function (s) { if (s.color) by[s.title] = s.color; });
      props_().setProperty('sections', JSON.stringify(secs.map(function (s) { return by[s.t] ? Object.assign({}, s, { color: by[s.t] }) : s; })));
    });
  } else if (!menu) {
    withShop_(shop, function () { var s = withShop_(hq, sectionsOf_); if (s) props_().setProperty('sections', JSON.stringify(s)); });
  }
  /* 店長邀請：寄邀請連結（夥伴身分，可改價格、品項） */
  var invited = false;
  if (d.email) {
    var inv = invitePartner_(shop.id, '店長', d.email);
    try { mail_(d.email, '【' + productName_() + '】邀請你管理「' + d.fullName + '」', '「' + hqCfg.name + '」的總店替你建立了分店「' + d.fullName + '」。\n\n用這個連結加入（只能一個人使用，' + inv.expires + ' 前有效，第一次打開就會綁定你的手機）：\n' + inv.link + '\n\n加入後可以修改菜單價格與品項。', null, { btn: '加入分店' }); invited = true; } catch (e) {}
  }
  cLog_(hq.id, 'owner', '新增分店', '成功', id + ' ' + d.fullName);
  return { ok: true, id: id, name: d.fullName, customerUrl: webUrl_() + '?s=' + id, invited: invited };
}

/* 內部：替某家店建立夥伴邀請（不用通行證，品牌主已通過驗證） */
function invitePartner_(shopId, name, mail) {
  var code = rand_(12).toUpperCase().replace(/[^A-Z0-9]/g, 'X'), exp = addDaysStr_(todayStr_(), 7);
  var id = 'P' + Date.now().toString(36).toUpperCase() + rand_(2).toUpperCase();
  cAppend_('partners', { '夥伴編號': id, '店家編號': shopId, '名稱': name, '角色': 'staff', '邀請碼雜湊': sha256_(code + secret_()), '邀請到期': exp, '綁定裝置': '', '狀態': '邀請中', '建立時間': nowD_(), '最後使用': '' });
  return { id: id, code: code, link: webUrl_() + '?invite=' + code, expires: exp };
}

/* 把一份菜單初稿套用到某家分店（範本匯入到多店）。draft 為空就用總店目前的菜單 */
function brandApplyDraft(token, draft, branchId, opts) {
  var c = brandGuard_(token, true), hq = c.shop; opts = opts || {};
  var b = branchList_(hq).filter(function (x) { return x.id === String(branchId); })[0];
  if (!b) return fail_('none', '找不到這家分店');
  var d = draft && draft.sections && draft.sections.length ? draft : withShop_(hq, menuDraftOf_);
  var r = withShop_(b, function () { return menuApplyDraft_(pricedDraft_(d, pricingNow_()), { update: true, label: '總店套用菜單' }); });
  cLog_(hq.id, 'owner', '套用菜單到分店', '成功', b.id + '：新增 ' + r.added + '、更新 ' + r.updated);
  return { ok: true, added: r.added, updated: r.updated, skipped: r.skipped, name: shopCfgOf_(b).name };
}

/* 停用／恢復某家分店（不影響總店與其他分店） */
function brandBranchSet(token, branchId, status) {
  var c = brandGuard_(token, true), hq = c.shop;
  var b = branchList_(hq).filter(function (x) { return x.id === String(branchId); })[0];
  if (!b) return fail_('none', '找不到這家分店');
  if (['active', 'suspended'].indexOf(status) < 0) return fail_('bad', '狀態不正確');
  b.status = status; saveShop_(b, ['status']);
  cLog_(hq.id, 'owner', status === 'suspended' ? '停用分店' : '恢復分店', '成功', b.id);
  return brandOverview(token);
}


/* ================= 第二階段：品牌主檔共用（同步）=================
   總店改了外觀、Logo、共通資料、分類結構、菜單後，由品牌主按「同步」套用到分店（推送，不是即時繼承）。
   每家分店有「跟隨品牌」開關（外觀、Logo、共通資料、分類、菜單），沒開的項目同步時會略過。
   同步只動品牌共用的部分：分店自己的地址、電話、營業時間、LINE、店長設定都不會被改。 */
var FOLLOW_KEYS = ['theme', 'logo', 'info', 'struct', 'menu'];
var FOLLOW_NAMES = { theme: '外觀', logo: 'Logo', info: '共通資料', struct: '分類', menu: '菜單' };
function followOf_(shop) {
  return withShop_(shop, function () {
    var f = {}; try { f = JSON.parse(props_().getProperty('follow') || '{}'); } catch (e) {}
    var o = {}; FOLLOW_KEYS.forEach(function (k) { o[k] = f[k] === undefined ? true : !!f[k]; });
    return o;
  });
}
function brandFollowSet(token, branchId, follow) {
  var c = brandGuard_(token, true), b = branchList_(c.shop).filter(function (x) { return x.id === String(branchId); })[0];
  if (!b) return fail_('none', '找不到這家分店');
  var o = {}; FOLLOW_KEYS.forEach(function (k) { o[k] = !!(follow && follow[k]); });
  withShop_(b, function () { props_().setProperty('follow', JSON.stringify(o)); });
  cLog_(c.shop.id, 'owner', '設定分店跟隨品牌', '成功', b.id + ' ' + JSON.stringify(o));
  return { ok: true, follow: o };
}

/* 總店目前的品牌主檔快照 */
function hqSnapshot_(hq) {
  return withShop_(hq, function () {
    var cfg = shopCfg_();
    return { cfg: cfg, sections: sectionsOf_() || [], logo: uploadedLogo_(), draft: menuDraftOf_() };
  });
}
function sameJson_(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

/* 在分店的情境裡套用（或只算差異）。回傳每個項目的結果 */
function branchSyncOne_(snap, what, opts, dry) {
  var rep = {};
  var cfg = {}; try { cfg = JSON.parse(props_().getProperty('cfg') || '{}'); } catch (e) {}
  var secs = sectionsOf_() || [];
  var f = {}; try { f = JSON.parse(props_().getProperty('follow') || '{}'); } catch (e) {}
  function follows(k) { return f[k] === undefined ? true : !!f[k]; }
  var hqc = snap.cfg;

  if (what.theme) {
    if (!follows('theme')) rep.theme = { skipped: '分店設為不跟隨' };
    else {
      var colorBy = {}; snap.sections.forEach(function (s) { if (s.color) colorBy[s.t] = s.color; });
      var secChange = secs.filter(function (s) { return (s.color || '') !== (colorBy[s.t] || ''); }).length;
      var changed = (cfg.primary || hqc.primary) !== hqc.primary || (cfg.accent || hqc.accent) !== hqc.accent || secChange > 0;
      rep.theme = { changed: changed, detail: (cfg.primary !== hqc.primary || cfg.accent !== hqc.accent ? '顏色' : '') + (secChange ? (cfg.primary !== hqc.primary ? '、' : '') + secChange + ' 個分類色條' : '') };
      if (changed && !dry) {
        cfg.primary = hqc.primary; cfg.accent = hqc.accent; props_().setProperty('cfg', JSON.stringify(cfg));
        if (secs.length) props_().setProperty('sections', JSON.stringify(secs.map(function (s) { return Object.assign({}, s, { color: colorBy[s.t] || '' }); })));
      }
    }
  }
  if (what.logo) {
    if (!follows('logo')) rep.logo = { skipped: '分店設為不跟隨' };
    else if (!snap.logo) rep.logo = { changed: false, detail: '總店還沒有 Logo' };
    else {
      var mine = uploadedLogo_(), need = !mine || mine.srcId !== snap.logo.fileId;
      rep.logo = { changed: need, detail: need ? '總店 Logo 已更新' : '' };
      if (need && !dry) {
        var meta = Object.assign({}, snap.logo, { srcId: snap.logo.fileId }), folder = tFolder_();
        ['fileId', 'webId'].forEach(function (k) { if (snap.logo[k]) { try { meta[k] = DriveApp.getFileById(snap.logo[k]).makeCopy('logo_' + k + '_' + Date.now(), folder).getId(); } catch (e) { delete meta[k]; } } });
        props_().setProperty('t_logo', JSON.stringify(meta));
        if (mine) ['fileId', 'webId'].forEach(function (k) { if (mine[k]) { try { DriveApp.getFileById(mine[k]).setTrashed(true); } catch (e) {} } });
        tClearLogoCache_();
      }
    }
  }
  if (what.info) {
    if (!follows('info')) rep.info = { skipped: '分店設為不跟隨' };
    else {
      var keys = ['tagline', 'heroTag', 'channels', 'minDays'], diff = keys.filter(function (k) { return !sameJson_(cfg[k] === undefined ? hqc[k] : cfg[k], hqc[k]); });
      rep.info = { changed: diff.length > 0, detail: diff.length ? '標語、共通設定' : '' };
      if (diff.length && !dry) { keys.forEach(function (k) { cfg[k] = hqc[k]; }); props_().setProperty('cfg', JSON.stringify(cfg)); }
    }
  }
  if (what.struct) {
    if (!follows('struct')) rep.struct = { skipped: '分店設為不跟隨' };
    else {
      var add = 0, note = 0, cols = 0, next = secs.map(function (s) { return Object.assign({}, s); }), taken = {};
      next.forEach(function (s) { taken[s.id] = 1; });
      var data0 = getData_(), newId = function () { for (var i = 0; i < 676; i++) { var id = 's' + String.fromCharCode(97 + Math.floor(i / 26)) + String.fromCharCode(97 + i % 26); if (!taken[id]) { taken[id] = 1; return id; } } throw new Error('分類太多'); };
      var order = [];
      snap.draft.sections.forEach(function (hs) {
        var m = next.filter(function (s) { return s.t === hs.title; })[0];
        var hq = snap.sections.filter(function (s) { return s.t === hs.title; })[0] || {};
        if (!m) {
          if (next.length >= 14) return;
          m = { id: newId(), t: hs.title, cols: hs.columns.slice(), note: hs.note || '', hl: 0, color: hq.color || '' }; next.push(m); add++;
        } else {
          if (hs.columns.length > m.cols.length && m.cols.every(function (c, i) { return c === hs.columns[i]; })) { m.cols = hs.columns.slice(); cols++; }
          if ((m.note || '') !== (hs.note || '')) { m.note = hs.note || ''; note++; }
        }
        order.push(m.id);
      });
      var rest = next.filter(function (s) { return order.indexOf(s.id) < 0; }).map(function (s) { return s.id; });
      var ordered = order.concat(rest).map(function (id) { return next.filter(function (s) { return s.id === id; })[0]; });
      var moved = ordered.map(function (s) { return s.id; }).join() !== secs.map(function (s) { return s.id; }).join() && add === 0 && secs.length > 0 ? 1 : 0;
      rep.struct = { changed: add + cols + note + moved > 0, detail: (add ? '新增 ' + add + ' 個分類' : '') + (cols ? (add ? '、' : '') + cols + ' 個分類增加規格欄' : '') + (note ? '、' + note + ' 個分類說明' : '') + (moved ? '、調整順序' : '') };
      if (rep.struct.changed && !dry) props_().setProperty('sections', JSON.stringify(ordered));
    }
  }
  if (what.menu) {
    if (!follows('menu')) rep.menu = { skipped: '分店設為不跟隨' };
    else {
      var r = menuApplyDraft_(pricedDraft_(snap.draft, pricingNow_()), { update: true, prune: !!opts.prune, pricesOnly: !!opts.pricesOnly, dry: dry, label: opts.pricesOnly ? '品牌價格規則' : '品牌同步菜單' });
      rep.menu = { changed: r.added + r.updated + (r.removed || 0) > 0, added: r.added, updated: r.updated, removed: r.removed || 0 };
    }
  }
  return rep;
}
function brandSyncRun_(token, branchId, what, opts, dry) {
  var c = brandGuard_(token, !dry), hq = c.shop;
  var b = branchList_(hq).filter(function (x) { return x.id === String(branchId); })[0];
  if (!b) return fail_('none', '找不到這家分店');
  var w = {}; FOLLOW_KEYS.forEach(function (k) { w[k] = !!(what && what[k]); });
  if (!FOLLOW_KEYS.some(function (k) { return w[k]; })) return fail_('bad', '請至少選一個要同步的項目');
  if (!dry && licOf_(b).mode !== 'full') return fail_('lic', '這家分店目前不是可使用狀態');
  var snap = hqSnapshot_(hq);
  var rep = withShop_(b, function () { return branchSyncOne_(snap, w, opts || {}, dry); });
  var name = shopCfgOf_(b).name;
  if (!dry) cLog_(hq.id, 'owner', '品牌同步', '成功', b.id + '：' + FOLLOW_KEYS.filter(function (k) { return w[k] && rep[k] && rep[k].changed; }).map(function (k) { return FOLLOW_NAMES[k]; }).join('、'));
  return { ok: true, id: b.id, name: name, report: rep };
}
function brandSyncCheck(token, branchId, what, opts) { return brandSyncRun_(token, branchId, what, opts, true); }
function brandSync(token, branchId, what, opts) { return brandSyncRun_(token, branchId, what, opts, false); }


/* ================= 第三階段：分店價格、跨店調價、跨店公告 ================= */

/* ---------- 價格規則 ----------
   分店價格 ＝ 個別價（有的話）或「總店價格套規則」。規則：同價／加減百分比／加減金額，再取整到 1／5／10 元。
   分店店長（或品牌主）在分店改價，會自動記成該品項的個別價，之後品牌同步不會把它蓋回去。 */
function priceRound_(n, r) { r = Number(r) || 1; return Math.max(0, Math.min(9999, Math.round(n / r) * r)); }
function pricingDefault_() { return { mode: 'same', value: 0, round: 1, auto: true, ovr: {} }; }
function pricingNow_() {
  var p = {}; try { p = JSON.parse(props_().getProperty('pricing') || '{}'); } catch (e) {}
  var d = pricingDefault_();
  return { mode: p.mode || d.mode, value: Number(p.value) || 0, round: Number(p.round) || 1, auto: p.auto !== false, ovr: p.ovr || {} };
}
function pricingOf_(shop) { return withShop_(shop, pricingNow_); }
function pricingSummary_(shop) { var p = pricingOf_(shop); return { mode: p.mode, value: p.value, round: p.round, overrides: Object.keys(p.ovr).length }; }
function priceRule_(p, pr) {
  if (p === null || p === undefined) return p;
  var v = Number(pr.value) || 0;
  if (pr.mode === 'pct') return priceRound_(p * (1 + v / 100), pr.round);
  if (pr.mode === 'amt') return priceRound_(p + v, pr.round);
  return p;
}
function specKey_(cols, i) { return cols.length === 1 && (cols[0] === '價格' || cols[0] === '加價') ? '' : cols[i]; }
/* 總店的菜單初稿 → 這家分店該有的價格 */
function pricedDraft_(draft, pr) {
  var out = JSON.parse(JSON.stringify(draft));
  out.sections.forEach(function (s) {
    s.items.forEach(function (it) {
      it.prices = it.prices.map(function (p, i) {
        if (p === null || p === undefined) return null;
        var k = s.title + '|' + it.name + '|' + specKey_(s.columns, i);
        return pr.ovr[k] !== undefined ? pr.ovr[k] : priceRule_(p, pr);
      });
    });
  });
  return out;
}
/* 分店改價 → 記成個別價（Code.gs 的 setPrices 呼叫） */
function branchOverrideNote_(list) {
  try {
    if (!saas_() || !CTX.shop || !CTX.shop.brandId) return;
    var pr = pricingNow_(); if (!pr.auto) return;
    list.forEach(function (x) { pr.ovr[x.k] = x.v; });
    props_().setProperty('pricing', JSON.stringify(pr));
  } catch (e) {}
}
function pricingClean_(r) {
  r = r || {};
  var mode = ['same', 'pct', 'amt'].indexOf(r.mode) >= 0 ? r.mode : 'same', v = Number(r.value) || 0, rd = [1, 5, 10].indexOf(Number(r.round)) >= 0 ? Number(r.round) : 1;
  if (mode === 'pct' && (v < -90 || v > 500)) throw new Error('百分比要在 -90 到 500 之間');
  if (mode === 'amt' && (v < -500 || v > 500)) throw new Error('金額要在 -500 到 500 之間');
  return { mode: mode, value: mode === 'same' ? 0 : v, round: rd };
}
function brandPricingGet(token, branchId) {
  var c = brandGuard_(token, false), b = branchList_(c.shop).filter(function (x) { return x.id === String(branchId); })[0];
  if (!b) return fail_('none', '找不到這家分店');
  var p = pricingOf_(b);
  return { ok: true, pricing: { mode: p.mode, value: p.value, round: p.round, auto: p.auto }, overrides: Object.keys(p.ovr).map(function (k) { var a = k.split('|'); return { key: k, title: a[0], name: a[1], spec: a[2], price: p.ovr[k] }; }) };
}
/* 設定規則；apply=true 時立刻把規則套到分店現有品項的價格（個別價不變） */
function brandPricingSet(token, branchId, rule, apply) {
  var c = brandGuard_(token, true), hq = c.shop, b = branchList_(hq).filter(function (x) { return x.id === String(branchId); })[0];
  if (!b) return fail_('none', '找不到這家分店');
  var clean; try { clean = pricingClean_(rule); } catch (e) { return fail_('bad', e.message); }
  withShop_(b, function () { var p = pricingNow_(); p.mode = clean.mode; p.value = clean.value; p.round = clean.round; if (rule && rule.auto !== undefined) p.auto = !!rule.auto; props_().setProperty('pricing', JSON.stringify(p)); });
  cLog_(hq.id, 'owner', '設定分店價格規則', '成功', b.id + ' ' + clean.mode + ' ' + clean.value + ' 取整' + clean.round);
  if (!apply) return { ok: true, applied: false };
  var r = brandSyncRun_(token, branchId, { menu: true }, { pricesOnly: true }, false);
  return r.ok === false ? r : { ok: true, applied: true, updated: r.report.menu.updated, skipped: r.report.menu.skipped };
}
/* 清除個別價（keys 空＝全部），可選立刻把價格恢復成「總店價 + 規則」 */
function brandOverridesClear(token, branchId, keys, apply) {
  var c = brandGuard_(token, true), hq = c.shop, b = branchList_(hq).filter(function (x) { return x.id === String(branchId); })[0];
  if (!b) return fail_('none', '找不到這家分店');
  var n = withShop_(b, function () {
    var p = pricingNow_(), before = Object.keys(p.ovr).length;
    if (!keys || !keys.length) p.ovr = {}; else keys.forEach(function (k) { delete p.ovr[k]; });
    props_().setProperty('pricing', JSON.stringify(p)); return before - Object.keys(p.ovr).length;
  });
  cLog_(hq.id, 'owner', '清除分店個別價', '成功', b.id + ' ' + n + ' 項');
  if (!apply) return { ok: true, cleared: n };
  var r = brandSyncRun_(token, branchId, { menu: true }, { pricesOnly: true }, false);
  return r.ok === false ? r : { ok: true, cleared: n, updated: r.report.menu.updated };
}

/* ---------- 跨店調價 ----------
   把「總店調價」一次連動到分店：總店價格先調，再依各分店的價格規則算出分店新價（個別價可選擇同幅度調整）。 */
function adjSpecClean_(s) {
  s = s || {};
  var mode = s.mode === 'pct' ? 'pct' : 'amt', v = Number(s.value), rd = [1, 5, 10].indexOf(Number(s.round)) >= 0 ? Number(s.round) : 1;
  if (!v || isNaN(v)) throw new Error('請填要調整的數字');
  if (mode === 'pct' && (v < -90 || v > 200)) throw new Error('百分比要在 -90 到 200 之間');
  if (mode === 'amt' && (v < -500 || v > 500)) throw new Error('金額要在 -500 到 500 之間');
  return { mode: mode, value: v, round: rd, scope: String(s.scope || ''), overrides: s.overrides === true, branches: (s.branches || []).map(String) };
}
function adjPrice_(p, s) { if (p === null || p === undefined) return p; return priceRound_(s.mode === 'pct' ? p * (1 + s.value / 100) : p + s.value, s.round); }
function brandAdjustRun_(token, spec, dry) {
  var c = brandGuard_(token, !dry), hq = c.shop, s;
  try { s = adjSpecClean_(spec); } catch (e) { return fail_('bad', e.message); }
  var hqDraft = withShop_(hq, menuDraftOf_), adj = JSON.parse(JSON.stringify(hqDraft)), changes = [];
  adj.sections.forEach(function (sec, si) {
    if (s.scope && sec.title !== s.scope) return;
    sec.items.forEach(function (it, ii) {
      it.prices = it.prices.map(function (p, i) {
        var n = adjPrice_(p, s);
        if (p !== null && n !== p) changes.push({ title: sec.title, name: it.name, spec: specKey_(sec.columns, i), label: it.name + (specKey_(sec.columns, i) ? '（' + sec.columns[i] + '）' : ''), old: p, now: n });
        return n;
      });
    });
  });
  var rep = { hq: { count: changes.length, sample: changes.slice(0, 8) }, branches: [] };
  var targets = branchList_(hq).filter(function (b) { return !s.branches.length || s.branches.indexOf(b.id) >= 0; });
  targets.forEach(function (b) {
    var fol = followOf_(b), name = shopCfgOf_(b).name;
    if (!fol.menu) { rep.branches.push({ id: b.id, name: name, skipped: '分店設為不跟隨菜單' }); return; }
    if (licOf_(b).mode !== 'full') { rep.branches.push({ id: b.id, name: name, skipped: '分店目前不是可使用狀態' }); return; }
    var pr = pricingOf_(b), ovr2 = Object.assign({}, pr.ovr);
    if (s.overrides) Object.keys(ovr2).forEach(function (k) { var a = k.split('|'); if (!s.scope || a[0] === s.scope) { var n = adjPrice_(ovr2[k], s); ovr2[k] = n; } });
    var pr2 = Object.assign({}, pr, { ovr: ovr2 });
    var r = withShop_(b, function () { return menuApplyDraft_(pricedDraft_(adj, pr2), { update: true, pricesOnly: true, dry: dry, label: '跨店調價' }); });
    if (!dry && s.overrides) withShop_(b, function () { var p = pricingNow_(); p.ovr = ovr2; props_().setProperty('pricing', JSON.stringify(p)); });
    rep.branches.push({ id: b.id, name: name, updated: r.updated });
  });
  if (!dry && changes.length) {
    withShop_(hq, function () { bulkPrices_(changes, '跨店調價'); });
    cLog_(hq.id, 'owner', '跨店調價', '成功', (s.scope || '全部') + ' ' + s.mode + ' ' + s.value + '：總店 ' + changes.length + ' 項、分店 ' + targets.length + ' 家');
  }
  return { ok: true, report: rep, dry: dry };
}
function brandAdjustCheck(token, spec) { return brandAdjustRun_(token, spec, true); }
function brandAdjust(token, spec) { return brandAdjustRun_(token, spec, false); }
/* 依「分類名稱｜品項｜規格」批量改價（在目前這家店的情境裡），並寫進修改紀錄 */
function bulkPrices_(changes, label) {
  var ss = book_(), sh = ss.getSheetByName(SHEET_NAME), n = sh.getLastRow() - HEAD;
  if (n <= 0) return 0;
  var vals = sh.getRange(HEAD + 1, 1, n, NCOL).getValues(), idx = {};
  vals.forEach(function (r, i) { if (String(r[0]).trim()) idx[[r[1], r[2], r[3]].join('|')] = i; });
  var now = new Date(), log = [], done = 0;
  changes.forEach(function (x) {
    var i = idx[x.title + '|' + x.name + '|' + x.spec]; if (i === undefined) return;
    log.push([now, '', [x.title, x.name, x.spec].filter(String).join('・'), vals[i][4], x.now, label || '批量調價']);
    vals[i][4] = x.now; done++;
  });
  if (done) {
    sh.getRange(HEAD + 1, 1, n, NCOL).setValues(vals);
    var lg = logSheet_(ss); lg.getRange(lg.getLastRow() + 1, 1, log.length, 6).setValues(log);
    var pr = props_(); pr.setProperty('updatedAt', now.toISOString()); pr.setProperty('updatedBy', label || '批量調價');
  }
  return done;
}

/* ---------- 跨店公告 ----------
   把總店「店家工具」裡做好的公告，發佈到勾選的分店（顧客頁照常顯示）。重複發佈同一則會更新分店那一則，不會變成兩則。 */
function brandNoticeList(token) {
  var c = brandGuard_(token, false);
  return { ok: true, notices: withShop_(c.shop, function () {
    return tListNotices_(30).map(function (n) { return { id: n.id, title: n.title, cat: tCat_(n.cat).name, start: n.start, end: n.end, show: n.show }; });
  }) };
}
function brandPushNotice(token, noticeId, branchIds) {
  var c = brandGuard_(token, true), hq = c.shop;
  var src = withShop_(hq, function () {
    var sh = tNoticeSheet_(), last = sh.getLastRow(); if (last < 2) return null;
    var vals = sh.getRange(2, 1, last - 1, T_NOTICE_HEAD.length).getValues();
    for (var i = 0; i < vals.length; i++) if (String(vals[i][0]) === String(noticeId)) return vals[i];
    return null;
  });
  if (!src) return fail_('none', '找不到這則公告');
  var content = {}; try { content = JSON.parse(src[7] || '{}'); } catch (e) {}
  content._src = hq.id + '|' + src[0];
  var targets = branchList_(hq).filter(function (b) { return (branchIds || []).indexOf(b.id) >= 0; });
  if (!targets.length) return fail_('bad', '請先勾選要發佈的分店');
  var out = targets.map(function (b) {
    if (licOf_(b).mode !== 'full') return { id: b.id, name: shopCfgOf_(b).name, skipped: '分店目前不是可使用狀態' };
    return withShop_(b, function () {
      var sh = tNoticeSheet_(), last = sh.getLastRow(), at = -1, ids = [];
      if (last > 1) {
        var vals = sh.getRange(2, 1, last - 1, T_NOTICE_HEAD.length).getValues();
        vals.forEach(function (r, i) { ids.push(String(r[0])); try { if (JSON.parse(r[7] || '{}')._src === content._src) at = i + 2; } catch (e) {} });
      }
      var now = new Date(), row = ['', now, now, src[3], src[4], src[5], src[6] === true, JSON.stringify(content).replace(/[<>]/g, ''), '', src[9]];
      var lock = LockService.getScriptLock(); lock.waitLock(10000);
      try {
        if (at > 0) { row[0] = String(sh.getRange(at, 1).getValue()); row[1] = sh.getRange(at, 2).getValue(); sh.getRange(at, 1, 1, row.length).setValues([row]); }
        else {
          var p = tProps_(), k = 'seq_N' + Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyMMdd'), seq = Number(p.getProperty(k) || 0) + 1; p.setProperty(k, String(seq));
          row[0] = 'N' + k.slice(5) + ('0' + seq).slice(-2); sh.appendRow(row);
        }
      } finally { lock.releaseLock(); }
      sh.getRange(2, 7, Math.max(1, sh.getLastRow() - 1), 1).insertCheckboxes();
      return { id: b.id, name: shopCfgOf_(b).name, updated: at > 0 };
    });
  });
  cLog_(hq.id, 'owner', '跨店發佈公告', '成功', src[0] + ' → ' + out.map(function (x) { return x.id; }).join(','));
  return { ok: true, results: out };
}
