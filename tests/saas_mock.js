/* 線上服務模式用的 Apps Script 模擬（接在 tools_mock.js 後面）：
   雜湊／HMAC（同步版 SHA-256）、有到期時間的快取、多份試算表、巢狀資料夾、ContentService、觸發程式、寄信內容紀錄 */
(function (G) {
  var store = G.__store;
  var K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  function sha256(bytes) {
    var h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    var l = bytes.length, m = bytes.slice(); m.push(0x80);
    while (m.length % 64 !== 56) m.push(0);
    var bits = l * 8; for (var i = 7; i >= 0; i--) m.push(i >= 4 ? 0 : (bits >>> (i * 8)) & 255);
    function ror(x, n) { return (x >>> n) | (x << (32 - n)); }
    for (var o = 0; o < m.length; o += 64) {
      var w = [];
      for (var t = 0; t < 16; t++) w[t] = ((m[o + t * 4] << 24) | (m[o + t * 4 + 1] << 16) | (m[o + t * 4 + 2] << 8) | m[o + t * 4 + 3]) >>> 0;
      for (t = 16; t < 64; t++) { var s0 = ror(w[t - 15], 7) ^ ror(w[t - 15], 18) ^ (w[t - 15] >>> 3), s1 = ror(w[t - 2], 17) ^ ror(w[t - 2], 19) ^ (w[t - 2] >>> 10); w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0; }
      var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
      for (t = 0; t < 64; t++) {
        var S1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25), ch = (e & f) ^ (~e & g), t1 = (hh + S1 + ch + K[t] + w[t]) >>> 0;
        var S0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22), mj = (a & b) ^ (a & c) ^ (b & c), t2 = (S0 + mj) >>> 0;
        hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0; h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0; h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0; h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + hh) >>> 0;
    }
    var out = []; h.forEach(function (x) { out.push((x >>> 24) & 255, (x >>> 16) & 255, (x >>> 8) & 255, x & 255); });
    return out;
  }
  function utf8(s) { var u = unescape(encodeURIComponent(s)), a = []; for (var i = 0; i < u.length; i++) a.push(u.charCodeAt(i)); return a; }
  function bytesOf(v) { return typeof v === 'string' ? utf8(v) : v.map(function (x) { return x & 255; }); }
  function signed(a) { return a.map(function (x) { return x > 127 ? x - 256 : x; }); }
  function hmac(key, msg) {
    if (key.length > 64) key = sha256(key);
    while (key.length < 64) key.push(0);
    var ip = key.map(function (x) { return x ^ 0x36; }), op = key.map(function (x) { return x ^ 0x5c; });
    return sha256(op.concat(sha256(ip.concat(msg))));
  }
  var U = G.Utilities;
  U.DigestAlgorithm = { SHA_256: 'SHA_256' }; U.Charset = { UTF_8: 'UTF_8' };
  U.computeDigest = function (alg, v) { return signed(sha256(bytesOf(v))); };
  U.computeHmacSha256Signature = function (v, k) { return signed(hmac(bytesOf(k), bytesOf(v))); };
  U.getUuid = function () { var s = ''; for (var i = 0; i < 32; i++) s += Math.floor(Math.random() * 16).toString(16); return s.slice(0, 8) + '-' + s.slice(8, 12) + '-' + s.slice(12, 16) + '-' + s.slice(16, 20) + '-' + s.slice(20); };
  U.base64EncodeWebSafe = function (v) { return U.base64Encode(bytesOf(v)).replace(/\+/g, '-').replace(/\//g, '_'); };
  U.base64DecodeWebSafe = function (s) { return U.base64Decode(s.replace(/-/g, '+').replace(/_/g, '/')); };
  Object.getPrototypeOf(U.newBlob([], 't', 'n')).getDataAsString = function () { var s = ''; this.b.forEach(function (x) { s += String.fromCharCode(x & 255); }); try { return decodeURIComponent(escape(s)); } catch (e) { return s; } };

  /* 快取：有到期時間（用 Date.now，測試可以改它來快轉） */
  var exp = {};
  G.CacheService = { getScriptCache: function () { return {
    get: function (k) { if (k in exp && exp[k] <= Date.now()) { delete store.cache[k]; delete exp[k]; } return k in store.cache ? store.cache[k] : null; },
    put: function (k, v, ttl) { store.cache[k] = v; exp[k] = Date.now() + (ttl || 600) * 1000; },
    remove: function (k) { delete store.cache[k]; delete exp[k]; },
    removeAll: function () { store.cache = {}; exp = {}; }
  }; } };
  var props = G.PropertiesService.getScriptProperties;
  G.PropertiesService = { getScriptProperties: function () {
    var p = props();
    p.deleteProperty = function (k) { delete store.props[k]; };
    p.getProperties = function () { var o = {}; Object.keys(store.props).forEach(function (k) { o[k] = store.props[k]; }); return o; };
    return p;
  } };
  store.quota = 100; store.sent = [];
  G.MailApp = {
    sendEmail: function (o, subj, body) {
      var m = typeof o === 'string' ? { to: o, subject: subj, body: body, n: 0 } : { to: o.to, subject: o.subject, body: o.body, n: (o.attachments || []).length, html: o.htmlBody || '', name: o.name || '', imgs: Object.keys(o.inlineImages || {}) };
      store.mails.push(m); store.quota--;
    },
    getRemainingDailyQuota: function () { return store.quota; }
  };
  G.ContentService = { MimeType: { JSON: 'json' }, createTextOutput: function (s) { var o = { s: s, getContent: function () { return s; }, setMimeType: function () { return o; } }; return o; } };
  store.triggers = [];
  G.ScriptApp.getProjectTriggers = function () { return store.triggers.map(function (n) { return { getHandlerFunction: function () { return n; } }; }); };
  G.ScriptApp.newTrigger = function (n) { var o = { timeBased: function () { return o; }, everyDays: function () { return o; }, atHour: function () { return o; }, create: function () { store.triggers.push(n); return o; } }; return o; };

  /* 試算表：多份、各自有分頁；補上建立價格表會用到的指令（不做事） */
  var Sheet = Object.getPrototypeOf(G.__ss.insertSheet('__t')); delete G.__ss.sheets.__t;
  var chain = function () { return this; };
  var rangeStubs = ['setNumberFormat', 'clearDataValidations', 'setWrap', 'setFontFamily', 'setBorder', 'merge', 'setVerticalAlignment', 'setFontStyle', 'setBackgrounds'];
  var getRange0 = Sheet.getRange;
  Sheet.getRange = function (r, c, nr, nc) {
    if (typeof r === 'string') { var st = {}; ['setValue', 'setFontSize', 'setFontWeight', 'setFontColor', 'setBackground', 'setHorizontalAlignment'].concat(rangeStubs).forEach(function (m) { st[m] = function () { return st; }; }); return st; }
    var rg = getRange0.call(this, r, c, nr, nc), sh = this;
    rangeStubs.forEach(function (m) { rg[m] = function () { return rg; }; });
    ['getValues', 'setValues'].forEach(function (m) { var o = rg[m]; rg[m] = function () { return o.apply(rg, arguments); }; });
    return rg;
  };
  Sheet.clear = function () { this.data = []; return this; };
  Sheet.getMaxRows = function () { return Math.max(1000, this.data.length); };
  Sheet.getMaxColumns = function () { return 26; };
  Sheet.getProtections = function () { return []; };
  Sheet.clearConditionalFormatRules = chain; Sheet.setConditionalFormatRules = chain; Sheet.hideSheet = chain;
  Sheet.protect = function () { var p = { setDescription: function () { return p; }, setUnprotectedRanges: function () { return p; }, addEditor: function () { return p; }, removeEditors: function () { return p; }, getEditors: function () { return []; }, canDomainEdit: function () { return false; }, setDomainEdit: function () { return p; } }; return p; };
  Sheet.getRange.__saas = 1;
  Sheet.getLastRow = function () { var d = this.data, n = d.length; while (n > 0 && d[n - 1].every(function (x) { return x === '' || x === undefined; })) n--; return n; };

  var books = store.books = {}, nb = 0;
  function patchBook(b, id, name) {
    b.id = id; b.title = name;
    b.getId = function () { return id; };
    b.getName = function () { return name; };
    b.getUrl = function () { return 'https:' + '/' + '/docs.google.com/spreadsheets/d/' + id; };
    b.getSheets = function () { var s = this.sheets; return Object.keys(s).map(function (k) { return s[k]; }); };
    b.deleteSheet = function (sh) { delete this.sheets[sh.name]; };
    b.setActiveSheet = chain; b.moveActiveSheet = chain; b.toast = chain;
    var ins = b.insertSheet; b.insertSheet = function (n) { return ins.call(this, n); };
    return b;
  }
  patchBook(G.__ss, 'test', '測試試算表'); books.test = G.__ss;
  var oldSS = G.SpreadsheetApp;
  G.SpreadsheetApp = Object.assign({}, oldSS, {
    create: function (name) { var id = 'book' + (++nb); var b = { sheets: {}, getSheetByName: G.__ss.getSheetByName, insertSheet: G.__ss.insertSheet }; books[id] = patchBook(b, id, name); return b; },
    openById: function (id) { return books[id] || G.__ss; },
    newConditionalFormatRule: function () { var r = {}; ['whenFormulaSatisfied', 'setBackground', 'setFontColor', 'setRanges'].forEach(function (m) { r[m] = function () { return r; }; }); r.build = function () { return {}; }; return r; },
    newDataValidation: function () { var d = {}; ['requireValueInList', 'requireCheckbox', 'requireNumberBetween', 'setAllowInvalid', 'setHelpText'].forEach(function (m) { d[m] = function () { return d; }; }); d.build = function () { return {}; }; return d; },
    ProtectionType: { SHEET: 1, RANGE: 2 }
  });

  /* Drive：巢狀資料夾、複製、分享 */
  var Folder = G.DriveApp.createFolder('__f').constructor, File0 = null;
  var DA = G.DriveApp, mkFile = DA.createFolder('__g').createFile(G.Utilities.newBlob([], 't', 'n')); File0 = Object.getPrototypeOf(mkFile);
  store.shares = [];
  Folder.prototype.createFolder = function (n) { var f = DA.createFolder(n); f.parent = this; (this.kids = this.kids || []).push(f); return f; };
  Folder.prototype.getFoldersByName = function (n) { var l = (this.kids || []).filter(function (k) { return k.name === n; }), i = 0; return { hasNext: function () { return i < l.length; }, next: function () { return l[i++]; } }; };
  Folder.prototype.addFile = function () {};
  DA.getRootFolder = function () { return { removeFile: function () {} }; };
  File0.makeCopy = function (name, folder) { var f = folder.createFile(this.blob); return f; };
  File0.addViewer = function (e) { store.shares.push({ id: this.id, to: e, role: 'viewer' }); };
  File0.addEditor = function (e) { store.shares.push({ id: this.id, to: e, role: 'editor' }); };
  /* 試算表本身當成檔案：getFileById(ssId) 要找得到 */
  var gf = DA.getFileById;
  DA.getFileById = function (id) {
    if (books[id]) { var f = Object.create(File0); f.id = id; f.blob = { n: books[id].title }; f.folder = null; return f; }
    return gf.call(DA, id);
  };
  /* UrlFetchApp：記錄請求，回傳 store.fetchReply（{ code, body }） */
  store.fetchLog = []; store.fetchReply = { code: 200, body: {} };
  G.UrlFetchApp = { fetch: function (url, opts) {
    store.fetchLog.push({ url: url, opts: opts });
    var r = typeof store.fetchReply === 'function' ? store.fetchReply(url, opts) : store.fetchReply;
    return { getResponseCode: function () { return r.code; }, getContentText: function () { return typeof r.body === 'string' ? r.body : JSON.stringify(r.body); } };
  } };
  G.Session.getEffectiveUser = function () { return { getEmail: function () { return 'owner@example.com'; } }; };
})(window);
