const CACHE_NAME = 'solo-system-v36';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(keys.map((key) => caches.delete(key)));
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Always fetch fresh from network first
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
