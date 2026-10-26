// Utilidades de interfaz (sin frameworks). Todo texto dinámico pasa por esc().
export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const money = (cents) =>
  new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: cents % 100 ? 2 : 0 }).format(cents / 100);

export function timeAgo(ts) {
  const s = Math.max(1, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return "ahora";
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  if (s < 86400 * 30) return `hace ${Math.floor(s / 86400)} d`;
  return new Date(ts * 1000).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" });
}
export const clock = (ts) => new Date(ts * 1000).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });
export const initials = (n) => esc((n || "?").trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase());

const P = {
  home: '<path d="M3 11 12 3l9 8"/><path d="M5 10v10h14V10"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  bag: '<path d="M6 7h12l1 13H5L6 7z"/><path d="M9 7a3 3 0 0 1 6 0"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.600 7.100L3 20l1-5.200A8 8 0 1 1 21 12z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2z"/><path d="M10 21h4"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.500 8 8 9 4.500-1 8-4 8-9V6l-8-3z"/><path d="m9 12 2 2 4-4"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  box: '<path d="M3 8l9-5 9 5v8l-9 5-9-5V8z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  alert: '<path d="M12 4 2 20h20L12 4z"/><path d="M12 10v4M12 17h.01"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
  leaf: '<path d="M5 19c0-9 5-14 15-14 0 10-5 15-14 15"/><path d="M5 19 14 10"/>',
  send: '<path d="m4 12 16-8-6 16-3-7-7-1z"/>',
  chart: '<path d="M4 20V4M4 20h16M8 16v-5M13 16V8M18 16v-3"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
  logout: '<path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4"/><path d="M16 8l4 4-4 4M20 12H9"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z"/><path d="M4 19a2 2 0 0 1 2-2h13"/>',
  note: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>',
  flask: '<path d="M9 3h6M10 3v6L5 19a1.500 1.500 0 0 0 1.400 2h11.200A1.500 1.500 0 0 0 19 19l-5-10V3"/><path d="M8 15h8"/>',
  laptop: '<rect x="4" y="5" width="16" height="11" rx="1.500"/><path d="M2 20h20"/>',
  ruler: '<path d="M3 17 17 3l4 4L7 21z"/><path d="m7 13 2 2M10 10l2 2M13 7l2 2"/>',
  shirt: '<path d="M8 3 3 6l2.500 4L8 9v12h8V9l2.500 1L21 6l-5-3a4 4 0 0 1-8 0z"/>',
  ball: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/>',
  chip: '<rect x="7" y="7" width="10" height="10" rx="1.500"/><path d="M9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4"/>',
  grid: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.500-3.500"/>',
  moon: '<path d="M20 14.500A8 8 0 0 1 9.500 4 8 8 0 1 0 20 14.500z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.500 1.500M17.500 17.500 19 19M19 5l-1.500 1.500M6.500 17.500 5 19"/>',
  heart: '<path d="M12 20s-8-4.800-8-10.500A4.500 4.500 0 0 1 12 7a4.500 4.500 0 0 1 8 2.500C20 15.200 12 20 12 20z"/>',
  pause: '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',
  play: '<path d="M7 4.500v15l12-7.500z"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13" r="3.500"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
};
export const icon = (n) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg>`;

export function toast(msg, isErr = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isErr ? " err" : "");
  el.textContent = msg;
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), 3600);
}

/** Modal con formulario opcional. Devuelve una promesa con el texto (o true) o null si se cancela. */
export function ask({ title, text = "", field = null, confirm = "Aceptar", danger = false }) {
  return new Promise((resolve) => {
    const ov = document.createElement("div");
    ov.className = "overlay";
    ov.innerHTML = `<form class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <h2>${esc(title)}</h2>${text ? `<p class="muted">${esc(text)}</p>` : ""}
      ${field ? `<textarea class="input" name="v" maxlength="500" placeholder="${esc(field)}" required minlength="10"></textarea>` : ""}
      <div class="row"><button type="button" class="btn ghost grow" data-x>Cancelar</button>
      <button class="btn grow ${danger ? "danger" : ""}">${esc(confirm)}</button></div></form>`;
    const done = (v) => { ov.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => e.key === "Escape" && done(null);
    ov.addEventListener("click", (e) => e.target === ov && done(null));
    ov.querySelector("[data-x]").onclick = () => done(null);
    ov.querySelector("form").onsubmit = (e) => { e.preventDefault(); done(field ? ov.querySelector("textarea").value.trim() : true); };
    document.addEventListener("keydown", onKey);
    document.body.append(ov);
    (ov.querySelector("textarea") || ov.querySelector(".btn:not(.ghost)")).focus();
  });
}

export const TIPO = { venta: "Venta", trueque: "Trueque", donacion: "Donación" };
export const STATUS = {
  HELD: ["Pago retenido", ""], DELIVERED: ["Entregado · esperando confirmación", ""],
  RELEASED: ["Pago liberado", "ok"], DISPUTED: ["En disputa", "bad"], REFUNDED: ["Reembolsado", "bad"],
};

// ---------- Carrera (lista agrupada por centro; el centro sale de la carrera) ----------
export function carreraOptions(meta, selected = "") {
  return `<option value="" disabled ${selected ? "" : "selected"}>Elige tu carrera…</option>` +
    Object.entries(meta.carreras).map(([centro, lista]) =>
      `<optgroup label="${esc(centro)}">${lista.map((c) => `<option value="${esc(c)}" ${c === selected ? "selected" : ""}>${esc(c)}</option>`).join("")}</optgroup>`).join("");
}
export function centroDeCarrera(meta, carrera) {
  return Object.keys(meta.carreras).find((c) => meta.carreras[c].includes(carrera)) || "";
}
/** Muestra en `out` el centro que corresponde a la carrera elegida en `select`. */
export function bindCentro(select, out, meta) {
  const sync = () => { const c = centroDeCarrera(meta, select.value); out.textContent = c ? c : "Se asigna según tu carrera"; };
  select.addEventListener("change", sync); sync();
}

// ---------- Contraseña con botón mostrar/ocultar ----------
export function pwField(name, label, { autocomplete = "new-password", hint = "" } = {}) {
  return `<label class="field">${esc(label)}${hint ? ` <span class="hint">${esc(hint)}</span>` : ""}
    <span class="pw"><input class="input" type="password" name="${name}" autocomplete="${autocomplete}" maxlength="128">
    <button type="button" class="pwtoggle" aria-label="Mostrar u ocultar contraseña">Ver</button></span></label>`;
}
export function wirePw(root) {
  root.querySelectorAll(".pwtoggle").forEach((b) => (b.onclick = () => {
    const i = b.previousElementSibling; const show = i.type === "password";
    i.type = show ? "text" : "password"; b.textContent = show ? "Ocultar" : "Ver";
  }));
}
export function pwProblem(pw, min = 8) {
  if (pw.length < min) return `La contraseña debe tener al menos ${min} caracteres.`;
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Usa letras y al menos un número.";
  return "";
}

export const CAT_ICON = { todos: "grid", Libros: "book", Apuntes: "note", Laboratorio: "flask", "Tecnología": "laptop",
  Arquitectura: "ruler", Uniformes: "shirt", Deportes: "ball", "Electrónica": "chip", Otros: "box" };

/** Número que sube de 0 a `to` (respeta "reducir movimiento"). */
export function countUp(el, to, { decimals = 0, ms = 900 } = {}) {
  const fmt = (n) => n.toLocaleString("es-MX", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || !to) { el.textContent = fmt(to); return; }
  const t0 = performance.now();
  const step = (t) => {
    const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(to * e);
    if (k < 1 && el.isConnected) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/** Foto de perfil si la hay; si no, iniciales. */
export const avatar = (u, extra = "") => (u && u.avatar
  ? `<img class="avatar ${extra}" src="${esc(u.avatar)}" alt="" loading="lazy">`
  : `<span class="avatar ${extra}">${initials(u && u.name)}</span>`);

// ---------- Preferencias locales (pueden fallar en modo privado: siempre con try/catch) ----------
export const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
};
export function toggleTheme() {
  const dark = document.documentElement.dataset.theme !== "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  try { localStorage.setItem("eg_theme", dark ? "dark" : "light"); } catch { /* ignorar */ }
  return dark;
}
