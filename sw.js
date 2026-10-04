// DHK OMR Pro - Production Offline Service Worker
const CACHE_NAME = 'dhkomr-pro-v2';

const CRITICAL_ASSETS = [
  './',
  './index.html',
  './roster.html',
  './exam.html',
  './grade.html',
  './scan-mcq.html',
  './scan-primary.html',
  './scan-school.html',
  // Core CDNs
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/lucide@latest',
  'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js',
  'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js'
];

// 1. Install & Cache Assets Resiliently
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      // Use map with individual catches so one failed CDN won't abort entire SW
      const cachePromises = CRITICAL_ASSETS.map(async (url) => {
        try {
          const response = await fetch(url, { mode: 'cors' });
          if (response.ok) {
            await cache.put(url, response);
          }
        } catch (err) {
          console.warn(`[SW] Failed to cache: ${url}`, err);
        }
      });
      await Promise.all(cachePromises);
    })
  );
  self.skipWaiting();
});

// 2. Activate & Purge Stale Caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log(`[SW] Purging old cache: ${key}`);
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// 3. Stale-While-Revalidate / Cache-First Fetch Engine
self.addEventListener('fetch', (event) => {
  // Only handle GET requests (skip chrome extensions or POST/PUT)
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      // If not in cache, fetch from network and dynamically store it
      return fetch(event.request)
        .then((networkResponse) => {
          if (!networkResponse || networkResponse.status !== 200 || networkResponse.type === 'opaque') {
            return networkResponse;
          }

          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });

          return networkResponse;
        })
        .catch(() => {
          // Fallback to home/index if page navigation fails offline
          if (event.request.mode === 'navigate') {
            return caches.match('./index.html');
          }
        });
    })
  );
});
