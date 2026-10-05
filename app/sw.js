/* Offline cache. Cache-first: the app opens with no signal.
   Bump CACHE whenever any file changes, or phones keep the old copy. */
const CACHE = 'rx-v15';
const ASSETS = [
  './', 'index.html', 'app.css', 'sheet.css', 'app.js', 'manifest.webmanifest',
  'assets/icon-192.png', 'assets/icon-512.png',
  'fonts/Montserrat-400.woff2', 'fonts/Montserrat-600.woff2', 'fonts/Montserrat-700.woff2',
  'fonts/NotoNastaliqUrdu-Regular.woff2',
  'vendor/html2canvas.min.js', 'vendor/jspdf.umd.min.js',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(hit => hit || fetch(e.request)));
});
