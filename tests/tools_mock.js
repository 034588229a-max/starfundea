/* Google Apps Script 模擬：涵蓋 Code.gs 與 Tools.gs 用到的服務
   - 試算表：日期字串（2026-10-05）、時間字串（08:00）寫入時會變成 Date，跟真的 Google 試算表一樣
   - google.script.run：非同步、資料經過 JSON 來回；回傳值裡有 Date 會直接失敗（真的 Apps Script 也不能傳 Date）
   - HtmlService：模板 <?!= x ?> 代入，並模擬「<script> 內 // 到行尾被砍掉」 */
(function (G) {
  var store = { props: {}, files: {}, folders: {}, mails: [], seq: 0, cache: {} };
  G.__store = store;
  function id() { return 'id' + (++store.seq); }
  function pad(n) { return ('0' + n).slice(-2); }
  G.PropertiesService = { getScriptProperties: function () { return {
    getProperty: function (k) { return k in store.props ? store.props[k] : null; },
    setProperty: function (k, v) { store.props[k] = String(v); }
  }; } };
  G.CacheService = { getScriptCache: function () { return {
    get: function (k) { return k in store.cache ? store.cache[k] : null; },
    put: function (k, v) { store.cache[k] = v; },
    remove: function (k) { delete store.cache[k]; }
  }; } };
  G.Session = {
    getScriptTimeZone: function () { return 'Asia/Taipei'; },
    getEffectiveUser: function () { return { getEmail: function () { return 'owner@example.com'; } }; }
  };
  G.Logger = { log: function () {} };
  G.ScriptApp = { getService: function () { return { getUrl: function () { return ''; } }; } };
  G.LockService = { getScriptLock: function () { return { waitLock: function () {}, releaseLock: function () {} }; } };
  function b64ToBytes(b) { var s = atob(b), a = []; for (var i = 0; i < s.length; i++) { var c = s.charCodeAt(i); a.push(c > 127 ? c - 256 : c); } return a; }
  function bytesToB64(a) { var s = ''; for (var i = 0; i < a.length; i++) s += String.fromCharCode(a[i] & 255); return btoa(s); }
  function Blob(bytes, type, name) { this.b = bytes; this.t = type; this.n = name; }
  Blob.prototype.getBytes = function () { return this.b; };
  Blob.prototype.getContentType = function () { return this.t; };
  G.Utilities = {
    base64Decode: b64ToBytes, base64Encode: bytesToB64,
    newBlob: function (b, t, n) { if (typeof b === 'string') { var u = unescape(encodeURIComponent(b)), a = []; for (var i = 0; i < u.length; i++) a.push(u.charCodeAt(i)); b = a; } return new Blob(b, t, n); },
    /* 只支援 Asia/Taipei（UTC+8，沒有夏令時間） */
    formatDate: function (d, tz, f) {
      var x = new Date(d.getTime() + 8 * 3600000);
      var map = { yyyy: x.getUTCFullYear(), yy: String(x.getUTCFullYear()).slice(2), MM: pad(x.getUTCMonth() + 1), dd: pad(x.getUTCDate()),
        HH: pad(x.getUTCHours()), mm: pad(x.getUTCMinutes()), ss: pad(x.getUTCSeconds()), u: (x.getUTCDay() + 6) % 7 + 1 };
      return f.replace(/yyyy|yy|MM|dd|HH|mm|ss|u/g, function (t) { return String(map[t]); });
    }
  };
  function File(blob, folder) {
    this.id = id(); this.blob = blob; this.folder = folder; this.trashed = false; this.shared = false;
    store.files[this.id] = this;
  }
  File.prototype.getId = function () { return this.id; };
  File.prototype.getName = function () { return this.blob.n; };
  File.prototype.getBlob = function () { return this.blob; };
  File.prototype.getThumbnail = function () { return null; };
  File.prototype.getUrl = function () { return 'https:' + '/' + '/drive.google.com/file/d/' + this.id + '/view'; };
  File.prototype.setSharing = function () { this.shared = true; };
  File.prototype.setTrashed = function (t) { this.trashed = t; };
  File.prototype.getParents = function () { var f = [this.folder], i = 0; return { hasNext: function () { return i < f.length; }, next: function () { return f[i++]; } }; };
  function Folder(name) { this.id = id(); this.name = name; store.folders[this.id] = this; }
  Folder.prototype.getId = function () { return this.id; };
  Folder.prototype.getName = function () { return this.name; };
  Folder.prototype.createFile = function (blob) { return new File(blob, this); };
  function iter(l) { var i = 0; return { hasNext: function () { return i < l.length; }, next: function () { return l[i++]; } }; }
  G.DriveApp = {
    Access: { ANYONE_WITH_LINK: 1 }, Permission: { VIEW: 1 },
    createFolder: function (n) { return new Folder(n); },
    getFolderById: function (i) { if (!store.folders[i]) throw new Error('no folder'); return store.folders[i]; },
    getFoldersByName: function (n) { return iter(Object.keys(store.folders).map(function (k) { return store.folders[k]; }).filter(function (f) { return f.name === n; })); },
    getFileById: function (i) { if (!store.files[i]) throw new Error('no file'); return store.files[i]; },
    searchFiles: function () { return iter([]); }
  };
  /* 試算表自動轉型：日期、時間字串 → Date（以台北時間解讀） */
  function conv(v) {
    if (typeof v !== 'string') return v;
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return new Date(v + 'T00:00:00+08:00');
    if (/^\d{2}:\d{2}$/.test(v)) return new Date('1899-12-30T' + v + ':00+08:00');
    return v;
  }
  function Sheet(name) { this.name = name; this.data = []; }
  var chain = function () { return this; };
  Sheet.prototype.getName = function () { return this.name; };
  Sheet.prototype.getLastRow = function () { return this.data.length; };
  Sheet.prototype.appendRow = function (r) { this.data.push(r.map(conv)); };
  Sheet.prototype.deleteRow = function (r) { this.data.splice(r - 1, 1); };
  Sheet.prototype.insertRowsAfter = function (r, n) { var a = []; for (var i = 0; i < n; i++) a.push([]); Array.prototype.splice.apply(this.data, [r, 0].concat(a)); };
  ['setFrozenRows', 'setColumnWidth', 'setColumnWidths'].forEach(function (m) { Sheet.prototype[m] = function () {}; });
  Sheet.prototype.getRange = function (r, c, nr, nc) {
    var sh = this; nr = nr || 1; nc = nc || 1;
    function ensure() { while (sh.data.length < r + nr - 1) sh.data.push([]); }
    var rg = {
      getValues: function () { var o = []; for (var i = 0; i < nr; i++) { var row = []; for (var j = 0; j < nc; j++) { var v = (sh.data[r - 1 + i] || [])[c - 1 + j]; row.push(v === undefined ? '' : v); } o.push(row); } return o; },
      getValue: function () { return this.getValues()[0][0]; },
      setValues: function (v) { ensure(); for (var i = 0; i < nr; i++) for (var j = 0; j < nc; j++) sh.data[r - 1 + i][c - 1 + j] = conv(v[i][j]); return this; },
      setValue: function (v) { ensure(); sh.data[r - 1][c - 1] = conv(v); return this; },
      insertCheckboxes: function () { ensure(); for (var i = 0; i < nr; i++) { var x = sh.data[r - 1 + i][c - 1]; sh.data[r - 1 + i][c - 1] = x === true; } return this; }
    };
    ['setFontWeight', 'setBackground', 'setFontColor', 'setDataValidation', 'setFontSize', 'setHorizontalAlignment'].forEach(function (m) { rg[m] = chain; });
    return rg;
  };
  var ss = { sheets: {}, getUrl: function () { return 'https:' + '/' + '/docs.google.com/spreadsheets/d/test'; }, getName: function () { return '測試試算表'; },
    getSheetByName: function (n) { return this.sheets[n] || null; }, insertSheet: function (n) { return (this.sheets[n] = new Sheet(n)); } };
  G.__ss = ss;
  var dv = { requireValueInList: function () { return dv; }, requireCheckbox: function () { return dv; }, build: function () { return {}; } };
  G.SpreadsheetApp = { openById: function () { return ss; }, getActiveSpreadsheet: function () { return ss; }, newDataValidation: function () { return dv; },
    getUi: function () { throw new Error('沒有試算表介面'); } };
  G.MailApp = { sendEmail: function (o, subj, body) {
    if (typeof o === 'string') store.mails.push({ to: o, subject: subj, n: 0 });
    else store.mails.push({ to: o.to, subject: o.subject, n: (o.attachments || []).length });
  } };
  /* HtmlService：模板代入＋模擬 Apps Script 砍掉 <script> 內 // 之後的文字 */
  function gasStrip(html) {
    return html.replace(/<script>([\s\S]*?)<\/script>/g, function (m, body) {
      return '<script>' + body.split('\n').map(function (ln) { var i = ln.indexOf('/' + '/'); return i < 0 ? ln : ln.slice(0, i); }).join('\n') + '</script>';
    });
  }
  function Output(html) { this.html = html; this.title = ''; }
  Output.prototype.getContent = function () { return this.html; };
  Output.prototype.setTitle = function (t) { this.title = t; return this; };
  Output.prototype.addMetaTag = function () { return this; };
  Output.prototype.setXFrameOptionsMode = function () { return this; };
  Output.prototype.setWidth = Output.prototype.setHeight = function () { return this; };
  G.HtmlService = {
    XFrameOptionsMode: { ALLOWALL: 1 },
    createHtmlOutput: function (h) { return new Output(h); },
    createTemplateFromFile: function (name) {
      var src = (G.__FILES || {})[name];
      if (src == null) throw new Error('No HTML file named ' + name + ' was found.');
      var t = { evaluate: function () {
        var out = src.replace(/<\?!=\s*(\w+)\s*\?>/g, function (m, k) { return String(t[k]); });
        return new Output(gasStrip(out));
      } };
      return t;
    }
  };
  /* 只跑 Tools.gs 時才需要的原系統常數（跑真的 Code.gs 時由 Code.gs 提供） */
  if (!G.__REAL_CODE) {
    G.STAFF_KEY = 'test-key';
    G.WEB_APP_URL = 'https:' + '/' + '/script.google.com/macros/s/AKfycbz/exec';
    G.LINKS = { line: 'https:' + '/' + '/lin.ee/VpY3C6z' };
  }
  function noDate(v, path) {
    if (v instanceof Date) throw new Error('回傳值不能有 Date（' + path + '）');
    if (v && typeof v === 'object') Object.keys(v).forEach(function (k) { noDate(v[k], path + '.' + k); });
  }
  G.__calls = [];
  function runner(ok, bad) {
    return new Proxy({}, { get: function (t, name) {
      if (name === 'withSuccessHandler') return function (f) { return runner(f, bad); };
      if (name === 'withFailureHandler') return function (f) { return runner(ok, f); };
      return function () {
        var args = JSON.parse(JSON.stringify(Array.prototype.slice.call(arguments)));
        G.__calls.push(name);
        setTimeout(function () {
          try {
            if (typeof G[name] !== 'function') throw new Error('伺服器沒有 ' + name);
            var r = G[name].apply(null, args); noDate(r, name);
            r = r === undefined ? undefined : JSON.parse(JSON.stringify(r)); if (ok) ok(r);
          } catch (e) { if (bad) bad(e); }
        }, 5);
      };
    } });
  }
  G.google = { script: { run: runner(null, null) } };
})(window);
