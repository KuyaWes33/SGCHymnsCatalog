/* Offline support.
 *
 * The app shell is cached on install, so after the first visit the hymnal
 * opens with no signal at all. Tunes are large and rarely all wanted, so they
 * are cached only once someone has actually played them.
 *
 * The page is fetched fresh whenever there is a connection, so a change to
 * index.html is live on the next open. Bump VERSION when the shell file list
 * changes, to clear the old cache out.
 */
const VERSION = "v3";
const SHELL = `hymnal-shell-${VERSION}`;
const TUNES = "hymnal-tunes";

const SHELL_FILES = [
  ".",
  "index.html",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-maskable-512.png",
  "icons/apple-touch-icon.png",
  "icons/favicon-32.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      // addAll fails the whole install if any single file 404s, so add them
      // one by one and let a missing icon pass rather than break offline mode.
      .then((cache) => Promise.all(
        SHELL_FILES.map((url) => cache.add(url).catch(() => null))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((k) => k.startsWith("hymnal-shell-") && k !== SHELL)
          .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Tunes: serve from cache if we have it, otherwise fetch and keep a copy.
  if (/\.(mid|midi|mp3|ogg|wav)$/i.test(url.pathname)) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(TUNES).then((c) => c.put(req, copy));
        }
        return res;
      }))
    );
    return;
  }

  // The page itself: the network first, so a correction is in the hands of the
  // congregation on the visit it is published rather than the one after. The
  // cached copy is still there the moment there is no signal, which is all
  // offline mode needs it for.
  if (req.mode === "navigate" || url.pathname.endsWith("/") || /\.html$/i.test(url.pathname)) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match("index.html")))
    );
    return;
  }

  // Everything else: cache first so the app opens instantly and offline,
  // with a background refresh so corrections arrive on the next open.
  event.respondWith(
    caches.match(req).then((hit) => {
      const network = fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || network;
    })
  );
});
