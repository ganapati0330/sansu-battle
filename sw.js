/* =========================================================
   さんすうバトル！ フテ猫 vs クロネコさん
   Service Worker

   ★ index.html を更新したら、下の VERSION の数字を
     必ず 1つ増やしてください。
     増やさないと、利用者の画面が古いままになります。
   ========================================================= */
const VERSION = 26;
const CACHE = 'sansu-battle-v' + VERSION;

/* 事前に保存しておくファイル。
   存在しないファイルがあっても失敗しないよう、1つずつ入れる。 */
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './apple-touch-icon.png',
  './ogp.png'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await Promise.all(ASSETS.map(async url => {
      try {
        await cache.add(new Request(url, { cache: 'reload' }));
      } catch (e) {
        /* そのファイルが無くても、他の保存は続ける */
      }
    }));
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

/* index.html は「まずネットワーク」。
   更新をすぐ受け取れるようにするため。つながらなければ保存版を使う。
   それ以外は「まず保存版」。表示を速くするため。 */
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  const isPage = req.mode === 'navigate' ||
                 (req.headers.get('accept') || '').includes('text/html');

  if (isPage) {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const cache = await caches.open(CACHE);
        cache.put(req, fresh.clone());
        return fresh;
      } catch (e) {
        const hit = await caches.match(req) || await caches.match('./index.html');
        if (hit) return hit;
        throw e;
      }
    })());
    return;
  }

  event.respondWith((async () => {
    const hit = await caches.match(req);
    if (hit) return hit;
    try {
      const fresh = await fetch(req);
      const cache = await caches.open(CACHE);
      cache.put(req, fresh.clone());
      return fresh;
    } catch (e) {
      throw e;
    }
  })());
});

/* 「こうしん」ボタンから呼ばれる */
self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});
