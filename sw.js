/* Offline support.
 *
 * The app shell is cached on install, so after the first visit the hymnal
 * opens with no signal at all. Tunes are large and rarely all wanted, so they
 * are cached only once someone has actually played them.
 *
 * When you change index.html, bump VERSION. Phones pick up the new version
 * the next time they are opened with a connection.
 */
const VERSION = "v6";
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
  "icons/logo.png",
  "extra-hymns.json",
  "changes.json",
  "notes/notes.json",
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

// The page asks which version this is, to tell people what changed.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "version" && event.ports[0]) {
    event.ports[0].postMessage({ version: VERSION });
  }
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Tunes: serve from cache if we have it, otherwise fetch and keep a copy.
  // (A hymn's music takes the last path below: kept once opened, and
  // refreshed when corrected.)
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

  // Added hymns and the list of changes: network first, so a new hymn or a
  // new note shows up as soon as it is uploaded, with the cached copy kept
  // for when there is no signal.
  if (url.pathname.endsWith("extra-hymns.json") || url.pathname.endsWith("changes.json") ||
      url.pathname.endsWith("notes/notes.json")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
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
