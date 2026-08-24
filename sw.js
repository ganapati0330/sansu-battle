/* さんすうバトル！ Service Worker
   ねらい：一度ひらけば、そのあとは 電波が なくても あそべるようにする。
   index.html 自体に 画像も音も 入っているので、キャッシュするのは ほぼこの1枚だけ。 */

const VERSION = 'v21';
const CACHE = 'sansu-battle-' + VERSION;

const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './maskable-192.png',
  './maskable-512.png',
  './apple-touch-icon.png',
  './ogp.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      // 1つでも失敗すると install ごと こけるので、個別に入れる
      .then(cache => Promise.all(
        ASSETS.map(url => cache.add(url).catch(() => null))
      ))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k.startsWith('sansu-battle-') && k !== CACHE)
            .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

/* キャッシュ優先。うしろで こっそり新しいものを とりにいく（stale-while-revalidate） */
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.open(CACHE).then(cache =>
      cache.match(req, { ignoreSearch: true }).then(hit => {
        const network = fetch(req)
          .then(res => {
            if (res && res.status === 200 && res.type === 'basic') {
              cache.put(req, res.clone());
            }
            return res;
          })
          .catch(() => hit || cache.match('./index.html'));
        // キャッシュがあれば すぐ返す。なければ ネットワークを待つ。
        return hit || network;
      })
    )
  );
});

/* 画面の「こうしん」ボタンから 呼ばれたときだけ 新しいSWに 切りかわる。
   （install で すぐ切りかえると、バトルの とちゅうで リロードされてしまう） */
self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});
