// Service worker de ECO-GALLO (app instalable, RNF-07). Nunca guarda respuestas de /api ni /uploads privados:
// solo la «cáscara» de la aplicación (HTML, CSS, JS e iconos), para abrir rápido y mostrar un aviso sin conexión.
const VERSION = "eg-shell-v2";
const SHELL = [
  "/", "/index.html", "/css/app.css", "/manifest.json", "/img/logo.svg", "/img/icon-192.png",
  "/js/main.js", "/js/api.js", "/js/ui.js", "/js/theme.js", "/js/charts.js", "/js/pagination.js", "/js/zoom.js",
  "/js/views/home.js", "/js/views/post.js", "/js/views/postform.js", "/js/views/orders.js", "/js/views/chat.js",
  "/js/views/profile.js", "/js/views/admin.js", "/js/views/wishlist.js", "/js/views/login.js", "/js/views/legal.js",
  "/js/views/cart.js", "/js/payflow.js",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/uploads/")) return;   // siempre a la red
  // Red primero (para recibir siempre la versión nueva); si no hay conexión, la copia guardada.
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok && SHELL.includes(url.pathname)) {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(e.request, copy));
      }
      return res;
    }).catch(() => caches.match(e.request).then((hit) => hit || (e.request.mode === "navigate" ? caches.match("/index.html") : Response.error())))
  );
});
