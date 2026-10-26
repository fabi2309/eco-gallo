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

export const state = { user: null, meta: null, unreadMsgs: 0, unreadNotes: 0, verification: null };
const app = document.getElementById("app");

const routes = [
  [/^#\/?$/, home], [/^#\/post\/(\d+)$/, post], [/^#\/new$/, form], [/^#\/edit\/(\d+)$/, form],
  [/^#\/mine$/, me, "mine"], [/^#\/orders$/, orders], [/^#\/order\/(\d+)$/, orders],
  [/^#\/messages$/, chat], [/^#\/chat\/(\d+)\/(\d+)$/, chat], [/^#\/profile$/, me, "profile"],
  [/^#\/impact$/, me, "impact"], [/^#\/admin$/, admin], [/^#\/wishlist$/, wish],
];

const NAV = [
  ["#/", "Inicio", "home"], ["#/mine", "Mis publicaciones", "list"], ["#/orders", "Compras y ventas", "bag"],
  ["#/messages", "Mensajes", "chat"], ["#/profile", "Perfil", "user"],
];

export async function refreshUser() {
  const r = await api.get("/api/me");
  state.user = r.user;
  state.unreadMsgs = r.unread_messages || 0;
  state.unreadNotes = r.unread_notifications || 0;
  state.verification = r.verification || null;
  return r;
}

function shell(path) {
  const cur = (href) => (path === href || (href !== "#/" && path.startsWith(href)) ? ' aria-current="page"' : "");
  const badge = (n) => (n ? `<span class="badge">${n}</span>` : "");
  const nb = { "#/messages": badge(state.unreadMsgs) };
  app.innerHTML = `
  <header class="topbar"><div class="in">
    <a class="brand" href="#/"><img src="/img/logo.svg" alt=""><span>ECO-GALLO <small>UAA</small></span></a>
    <nav class="topnav" aria-label="Principal">
      ${NAV.map(([h, t]) => `<a href="${h}"${cur(h)}>${t}${nb[h] || ""}</a>`).join("")}
      ${state.user.role === "admin" ? `<a href="#/admin"${cur("#/admin")}>Administración</a>` : ""}
    </nav>
    <span class="spacer"></span>
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
  document.querySelectorAll('a[href="#/messages"]').forEach((a) => put(a, state.unreadMsgs));
}
setInterval(async () => {
  if (!state.user || document.hidden || !document.getElementById("bell")) return;
  const before = state.unreadNotes;
  try { await refreshUser(); } catch { return; }
  if (!state.user) return;
  paintBadges();
  if (state.unreadNotes > before) toast("Tienes un aviso nuevo 🔔");
}, 30000);

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
  if (state.unreadNotes) { await api.post("/api/notifications/read"); state.unreadNotes = 0; e.currentTarget.querySelector(".badge")?.remove(); }
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
    if (!state.user) return login.render(app, { onDone: goHome });
    if (r.needs_profile) return login.renderProfile(app, { onDone: () => route() });
    if (r.needs_verification) return login.renderPending(app, { state, onLogout: logout, refresh: () => route() });
  } catch (e) {
    app.innerHTML = `<main><div class="empty"><h2>No pudimos conectar</h2><p>${esc(e.message)}</p><button class="btn" onclick="location.reload()">Reintentar</button></div></main>`;
    return;
  }
  if (hash === "#/login") { location.hash = "#/"; return; }
  shell(hash);
  const view = document.getElementById("view");
  const hit = routes.find(([re]) => re.test(hash));
  if (!hit) { location.hash = "#/"; return; }
  const [re, mod, extra] = hit;
  const args = hash.match(re).slice(1);
  try {
    await mod.render(view, { args, extra, state, go: (h) => (location.hash = h), refresh: () => route(), isCurrent: () => my === seq });
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
