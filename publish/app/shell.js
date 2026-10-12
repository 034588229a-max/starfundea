/* 星樂創意 App 外殼：把 Apps Script 頁面嵌成全螢幕，像 App 一樣用。
   - 員工打卡／店家菜單：需要店家代碼（網址 ?s=S0001，或第一次開啟時輸入，之後記住）
   - 店主管理：記住登入，下次直接進菜單工具
   - 頁面裡 target=_top 的連結會透過 postMessage 交給外殼，在同一個視窗裡開，不會跳出 App
   - 程式更新：Apps Script 重新部署後，下次開啟就是最新版，外殼不用重裝 */
(function () {
  var C = window.HL_CONFIG || {}, E = window.HL_ENTRY, NEED = window.HL_ENTRY_NEED_SHOP;
  var $ = function (id) { return document.getElementById(id); };
  var P = new URLSearchParams(location.search);
  function get(k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } }
  function set(k, v) { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch (e) {} }
  var base = (C.exec || '').replace(/\?.*$/, '');

  if (P.get('reset')) { set('hl-shop', ''); set('hl-token', ''); }
  var sid = String(P.get('s') || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (sid) set('hl-shop', sid); else sid = get('hl-shop');

  function urlFor() {
    if (E === 'clock') return base + '?s=' + sid + '&p=clock';
    if (E === 'menu') return base + '?s=' + sid + '&p=menu';
    var tk = get('hl-token');
    return tk ? base + '?p=home&t=' + encodeURIComponent(tk) : base + '?go=home';
  }
  var timer = null;
  function open(url) {
    var f = $('app');
    $('sTxt').textContent = '載入中…';
    $('splash').classList.remove('hidden'); $('setup').classList.add('hidden'); $('err').classList.add('hidden');
    f.classList.remove('hidden');
    f.onload = function () { clearTimeout(timer); $('splash').classList.add('hidden'); };
    f.src = url;
    clearTimeout(timer);
    timer = setTimeout(function () {
      if (!$('splash').classList.contains('hidden')) {
        $('sTxt').textContent = navigator.onLine === false ? '沒有網路連線' : '連線比較慢，還在載入…';
        $('err').classList.remove('hidden'); $('eTxt').textContent = navigator.onLine === false ? '目前沒有網路，連線後再試一次。' : '載入比較久，可以再等一下，或按重新載入。';
      }
    }, 12000);
  }
  function start() {
    if (!base) { $('splash').classList.add('hidden'); $('err').classList.remove('hidden'); $('eTxt').textContent = '外殼還沒設定：請在 config.js 填入 Apps Script 網址。'; return; }
    if (NEED && !sid) { $('splash').classList.add('hidden'); $('setup').classList.remove('hidden'); return; }
    open(urlFor());
  }
  $('go').onclick = function () {
    var v = $('sid').value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (!/^S\d{4,}$/.test(v)) { $('sErr').textContent = '店家代碼格式不對，例如 S0001'; return; }
    set('hl-shop', v); sid = v; $('sErr').textContent = ''; start();
  };
  $('sid').onkeydown = function (e) { if (e.key === 'Enter') $('go').onclick(); };
  $('retry').onclick = function () { $('err').classList.add('hidden'); start(); };

  /* 頁面傳來的訊息：開新頁、記住登入 */
  window.addEventListener('message', function (e) {
    var d = e.data || {};
    var okOrigin = /\.googleusercontent\.com$/.test(e.origin); try { okOrigin = okOrigin || e.origin === new URL(base).origin; } catch (x) {}
    if (!okOrigin) return;
    if (typeof d.hlGo === 'string' && d.hlGo.indexOf(base) === 0) {
      var u = d.hlGo;
      var m = u.match(/[?&]t=([^&#]+)/); if (m && E === 'owner') set('hl-token', decodeURIComponent(m[1]));
      open(u);
    } else if (typeof d.hlToken === 'string' && E === 'owner') set('hl-token', d.hlToken);
  });

  if ('serviceWorker' in navigator) { navigator.serviceWorker.register('../sw.js', { scope: '../' }).catch(function () {}); }
  start();
})();
