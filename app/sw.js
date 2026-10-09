/* App 外殼的離線快取：只快取外殼自己的檔案（Apps Script 頁面一律走網路，所以更新會即時生效）。
   外殼檔案有改，把 VERSION 加一，使用者下次開啟就會換成新版。 */
var VERSION = 'hl-shell-v1';
var FILES = ['./', 'index.html', 'shell.js', 'shell.css', 'config.js',
  'clock/', 'clock/index.html', 'clock/manifest.webmanifest', 'owner/', 'owner/index.html', 'owner/manifest.webmanifest', 'menu/', 'menu/index.html', 'menu/manifest.webmanifest',
  'icons/clock-192.png', 'icons/owner-192.png', 'icons/menu-192.png', 'icons/clock-32.png', 'icons/owner-32.png', 'icons/menu-32.png'];
self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(FILES); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;
  e.respondWith(fetch(r).then(function (res) {
    var copy = res.clone(); caches.open(VERSION).then(function (c) { c.put(r, copy); }); return res;
  }).catch(function () { return caches.match(r, { ignoreSearch: true }); }));
});
