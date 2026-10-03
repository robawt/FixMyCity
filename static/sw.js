const CACHE = 'fixmycity-shell-v3';
const SHELL = ['/', '/admin', '/static/style.css', '/static/logo.png', '/static/manifest.webmanifest'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/uploads/')) return;

  // Navigations use network-first so new builds (especially QR fixes) are
  // picked up immediately; the cached shell remains the low-network fallback.
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request, {cache: 'no-store'}).then(response => {
      const copy = response.clone();
      caches.open(CACHE).then(c => c.put(event.request, copy));
      return response;
    }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/'))));
    return;
  }

  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE).then(c => c.put(event.request, copy));
    return response;
  }).catch(() => caches.match('/'))));
});
