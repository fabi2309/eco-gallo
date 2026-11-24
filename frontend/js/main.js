import { api, ApiError } from "./api.js";
import { esc, icon, toast, timeAgo, toggleTheme } from "./ui.js";
import * as login from "./views/login.js";
import * as home from "./views/home.js";
import * as post from "./views/post.js";
import * as form from "./views/postform.js";
import * as orders from "./views/orders.js";
import * as chat from "./views/chat.js";
import * as me from "./views/profile.js";
import * as admin from "./views/admin.js";
import * as wish from "./views/wishlist.js";
import * as legal from "./views/legal.js";
import * as cart from "./views/cart.js";

export const state = { user: null, meta: null, unreadMsgs: 0, unreadNotes: 0, verification: null, cartCount: 0 };
const app = document.getElementById("app");

const routes = [
  [/^#\/?$/, home], [/^#\/post\/(\d+)$/, post], [/^#\/new$/, form], [/^#\/edit\/(\d+)$/, form],
  [/^#\/mine$/, me, "mine"], [/^#\/orders$/, orders], [/^#\/order\/(\d+)$/, orders],
  [/^#\/messages$/, chat], [/^#\/chat\/(\d+)\/(\d+)$/, chat], [/^#\/profile$/, me, "profile"],
  [/^#\/payment-(?:success|cancel)\/(\d+)$/, orders],
  [/^#\/impact$/, me, "impact"], [/^#\/admin$/, admin], [/^#\/wishlist$/, wish],
  [/^#\/cart$/, cart], [/^#\/privacidad$/, legal, "privacidad"], [/^#\/terminos$/, legal, "terminos"],
];
// Páginas que se pueden leer sin iniciar sesión (aviso de privacidad y términos).
const PUBLIC = { "#/privacidad": "privacidad", "#/terminos": "terminos" };

const NAV = [
  ["#/", "Inicio", "home"], ["#/mine", "Mis publicaciones", "list"], ["#/orders", "Compras y ventas", "bag"],
  ["#/messages", "Mensajes", "chat"], ["#/profile", "Perfil", "user"],
];

export async function refreshUser() {
  const r = await api.get("/api/me");
  state.user = r.user;
  state.passwordResetAllowed = !!r.password_reset_allowed;
  state.unreadMsgs = r.unread_messages || 0;
  state.unreadNotes = r.unread_notifications || 0;
  state.cartCount = r.cart_count || 0;
  state.verification = r.verification || null;
  return r;
}

function shell(path) {
  const cur = (href) => (path === href || (href !== "#/" && path.startsWith(href)) ? ' aria-current="page"' : "");
  const badge = (n) => (n ? `<span class="badge">${n}</span>` : "");
  const nb = { "#/messages": badge(state.unreadMsgs) };
  app.innerHTML = `
  ${state.meta.payment_mode === "test" ? `<div class="payment-banner" role="status">${state.meta.payment_provider === "mercadopago" ? "Mercado Pago" : "Stripe"} en modo de pruebas: usa únicamente tarjetas de prueba. No se mueve dinero real.</div>` : ""}
  <header class="topbar"><div class="in">
    <a class="brand" href="#/"><img src="/img/logo.svg" alt=""><span>ECO-GALLO <small>UAA</small></span></a>
    <nav class="topnav" aria-label="Principal">
      ${NAV.map(([h, t]) => `<a href="${h}"${cur(h)}>${t}${nb[h] || ""}</a>`).join("")}
      ${state.user.role === "admin" ? `<a href="#/admin"${cur("#/admin")}>Administración</a>` : ""}
    </nav>
    <span class="spacer"></span>
    <a class="bell" id="cartlink" href="#/cart" aria-label="Carrito" title="Carrito">${icon("bag")}${badge(state.cartCount)}</a>
    <a class="bell" id="wishlink" href="#/wishlist" aria-label="Lista de deseos" title="Lista de deseos">${icon("heart")}</a>
    <button class="bell" id="theme" aria-label="Cambiar entre modo claro y oscuro" title="Modo claro / oscuro">${icon(document.documentElement.dataset.theme === "dark" ? "sun" : "moon")}</button>
    <button class="bell" id="bell" aria-label="Notificaciones">${icon("bell")}${badge(state.unreadNotes)}</button>
    <button class="logout" id="logout" title="Cerrar sesión">${icon("logout")}<span>Cerrar sesión</span></button>
  </div></header>
  <main id="view" tabindex="-1"><div class="loading">Cargando…</div></main>
  <nav class="tabbar" aria-label="Principal">
    ${NAV.map(([h, t, i]) => `<a href="${h}"${cur(h)}>${icon(i)}<span>${t.split(" ")[0]}</span>${nb[h] || ""}</a>`).join("")}
  </nav>`;
  document.getElementById("bell").onclick = toggleNotes;
  document.getElementById("logout").onclick = logout;
  const th = document.getElementById("theme");
  th.onclick = () => { const dark = toggleTheme(); th.innerHTML = icon(dark ? "sun" : "moon"); };
}

// Revisa cada 30 s si hay mensajes o avisos nuevos (p. ej. algo de tu lista de deseos) sin recargar la vista.
function paintBadges() {
  const put = (host, n, cls = "badge") => { host?.querySelector("." + cls)?.remove(); if (n) host?.insertAdjacentHTML("beforeend", `<span class="${cls}">${n}</span>`); };
  put(document.getElementById("bell"), state.unreadNotes);
  put(document.getElementById("cartlink"), state.cartCount);
  document.querySelectorAll('a[href="#/messages"]').forEach((a) => put(a, state.unreadMsgs));
}
// Avisos casi en tiempo real: consulta ligera cada 5 s (contadores) y aviso del navegador si la pestaña está oculta.
let lastSeen = { msg: null, note: null };
async function pulse() {
  if (!state.user || !document.getElementById("bell")) return;
  let r;
  try { r = await api.get("/api/pulse"); } catch { return; }
  const first = lastSeen.msg === null;
  const newNote = !first && r.last_notification_id > lastSeen.note && r.unread_notifications > 0;
  const newMsg = !first && r.last_message_id > lastSeen.msg && r.unread_messages > 0;
  lastSeen = { msg: r.last_message_id, note: r.last_notification_id };
  state.unreadNotes = r.unread_notifications; state.unreadMsgs = r.unread_messages; state.cartCount = r.cart_count;
  paintBadges();
  const inThatChat = r.latest_message && location.hash === `#/chat/${r.latest_message.post_id}/${r.latest_message.sender_id}`;
  if (newMsg && !inThatChat) {
    const m = r.latest_message;
    if (!systemNotify(`Mensaje de ${m.name}`, m.preview, `#/chat/${m.post_id}/${m.sender_id}`)) toast(`💬 ${m.name}: ${m.preview}`);
  }
  if (newNote) {
    const n = r.latest_notification;
    if (!systemNotify("ECO-GALLO", n.text, n.link || "#/")) toast("Tienes un aviso nuevo 🔔");
  }
}
// Notificación del sistema operativo solo si el usuario la permitió y no está mirando la página.
function systemNotify(title, body, link) {
  if (!("Notification" in window) || Notification.permission !== "granted" || !document.hidden) return false;
  try {
    const n = new Notification(title, { body, icon: "/img/logo.svg", tag: link });
    n.onclick = () => { window.focus(); location.hash = link; n.close(); };
    return true;
  } catch { return false; }
}
setInterval(pulse, 5000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) pulse(); });

async function toggleNotes(e) {
  const old = document.querySelector(".notes");
  if (old) return old.remove();
  const { notifications } = await api.get("/api/notifications");
  const box = document.createElement("div");
  box.className = "notes";
  box.innerHTML = notifications.length
    ? notifications.map((n) => `<a href="${esc(n.link || "#/")}" class="${n.read_at ? "" : "unread"}">${esc(n.text)}<br><span class="muted small">${timeAgo(n.created_at)}</span></a>`).join("")
    : '<p class="muted" style="padding:16px">Aún no tienes notificaciones.</p>';
  box.addEventListener("click", () => box.remove());
  document.querySelector(".topbar").append(box);
  if (state.unreadNotes) { const bell = e.currentTarget; await api.post("/api/notifications/read"); state.unreadNotes = 0; bell.querySelector(".badge")?.remove(); }
}

// Si ya estamos en "#/", cambiar el hash no dispara hashchange: hay que volver a pintar a mano.
const goHome = () => { if ((location.hash || "#/") === "#/") route(); else location.hash = "#/"; };

let seq = 0;
async function route() {
  const my = ++seq;
  const hash = location.hash || "#/";
  try {
    const r = await refreshUser();
    if (!state.meta) state.meta = await api.get("/api/meta");
    // El aviso y los términos se pueden leer siempre: sin sesión o a mitad del registro.
    if (PUBLIC[hash] && (!state.user || r.needs_profile || r.needs_terms || r.needs_verification)) {
      return legal.render(app, { extra: PUBLIC[hash], state });
    }
    if (!state.user) {
      const err = hash.match(/^#\/oauth-error\/([\w-]+)$/), totp = hash.match(/^#\/oauth-totp\/([\w-]+)$/);
      if (err || totp) history.replaceState(null, "", "#/");   // el token no se queda en el historial
      return login.render(app, { onDone: goHome, oauth: err ? { error: err[1] } : totp ? { totp: totp[1] } : null });
    }
    if (r.needs_profile) return login.renderProfile(app, { onDone: () => route() });
    if (r.needs_terms && !PUBLIC[hash]) return legal.renderAccept(app, { state, api, onDone: () => route(), onLogout: logout });
    if (r.needs_verification) return login.renderPending(app, { state, onLogout: logout, refresh: () => route() });
  } catch (e) {
    app.innerHTML = `<main><div class="empty"><h2>No pudimos conectar</h2><p>${esc(e.message)}</p><button class="btn" id="retry-connection">Reintentar</button></div></main>`;
    app.querySelector("#retry-connection")?.addEventListener("click", () => route());
    return;
  }
  if (hash === "#/login" || hash.startsWith("#/oauth-")) { location.hash = "#/"; return; }
  shell(hash);
  const view = document.getElementById("view");
  const hit = routes.find(([re]) => re.test(hash));
  if (!hit) { location.hash = "#/"; return; }
  const [re, mod, extra] = hit;
  const args = hash.match(re).slice(1);
  try {
    await mod.render(view, { args, extra, state, inShell: true, go: (h) => (location.hash = h), refresh: () => route(), isCurrent: () => my === seq });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return route();
    view.innerHTML = `<div class="empty"><h2>No se pudo cargar</h2><p>${esc(e.message)}</p><a class="btn ghost" href="#/">Volver al inicio</a></div>`;
  }
  window.scrollTo(0, 0);
}

export async function logout() {
  await api.post("/api/auth/logout");
  state.user = null;
  location.hash = "#/";
  toast("Sesión cerrada");
  route();
}

window.addEventListener("hashchange", route);
route();

// Enlaces de aviso/términos dentro de formularios: se abren encima sin perder lo escrito.
document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-legal]");
  if (!a || !state.meta) return;
  e.preventDefault();
  legal.openLegal(a.dataset.legal, state.meta);
});

// App instalable (PWA): el service worker guarda solo la interfaz, nunca datos de la API.
export let installPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installPrompt = e; document.dispatchEvent(new Event("eg:installable")); });
window.addEventListener("appinstalled", () => { installPrompt = null; toast("ECO-GALLO quedó instalada en tu dispositivo"); });
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => { /* sin PWA: la web sigue funcionando */ }));
}
window.addEventListener("offline", () => toast("Sin conexión. Algunas acciones no estarán disponibles.", true));
window.addEventListener("online", () => toast("Conexión restablecida"));
