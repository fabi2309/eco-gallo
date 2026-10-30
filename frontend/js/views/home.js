import { api } from "../api.js";
import { esc, icon, money, TIPO, CAT_ICON, countUp, store, toast } from "../ui.js";

export function card(p) {
  const img = p.images[0];
  const price = p.tipo === "venta" ? money(p.price_cents) : TIPO[p.tipo];
  return `<a class="card" href="#/post/${p.id}">
    <div class="ph">${img ? `<img src="${esc(img)}" alt="" loading="lazy">` : `<div class="noimg">${icon("image")}</div>`}
      <span class="tag ${esc(p.tipo)}">${esc(TIPO[p.tipo])}</span>${p.status === "reserved" ? '<span class="tag reserved">Reservado</span>' : ""}${p.status === "paused" ? '<span class="tag reserved">Pausada</span>' : ""}</div>
    <div class="body"><div class="title">${esc(p.title)}</div><div class="price">${esc(price)}</div>
    <div class="muted small">${esc(p.condition)} · ${esc(p.author.name || "Usuario")}</div>
    ${p.stats ? `<div class="row small muted" style="margin-top:6px;gap:10px;border-top:1px solid var(--border);padding-top:4px"><span title="Vistas">${icon("eye")} ${p.stats.views || 0}</span><span title="Contactos">${icon("chat")} ${p.stats.contacts || 0}</span><span title="Interesados">${icon("heart")} ${p.stats.interested || 0}</span></div>` : ""}
    </div></a>`;
}

const TIPS = [
  "Un libro reutilizado evita cerca de 2.5 kg de CO₂e frente a comprarlo nuevo.",
  "¿Terminaste el semestre? Tu bata y tus apuntes pueden ahorrarle dinero a alguien de nuevo ingreso.",
  "Dona lo que ya no uses: la donación también cuenta en el impacto de la comunidad.",
  "Cuando compres o vendas, acuerda el encuentro en un punto seguro del campus.",
];

function hero(state) {
  const first = (state.user.name || "").trim().split(/\s+/)[0] || "gallo";
  return `<section class="homehero">
    <svg class="leaves" viewBox="0 0 400 400" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
      <path d="M60 360C60 220 140 120 300 100c0 150-80 250-240 260z"/><path d="M60 360 220 200"/><path d="M250 380c-10-90 20-170 120-210 10 100-30 180-120 210z"/></g></svg>
    <div class="copy">
      <span class="eyebrow">${icon("leaf")} Economía circular UAA</span>
      <h1>Hola, ${esc(first)}. Dale una segunda vida a tu material.</h1>
      <p>Lo que a ti ya no te sirve, a otro universitario le ahorra dinero y a la UAA le ahorra residuos.</p>
      <div class="row wrap"><a class="btn accent" href="#/new">${icon("plus")} Publicar algo</a><a class="btn ghostlight" href="#/impact">${icon("chart")} Ver impacto</a></div>
    </div>
    <div class="stats" id="stats" aria-label="Impacto de la comunidad">
      <div><b data-n="reused_items">0</b><span>artículos reutilizados</span></div>
      <div><b data-n="co2_kg" data-d="1">0</b><span>kg de CO₂e evitados</span></div>
      <div><b data-n="active_posts">0</b><span>publicaciones activas</span></div>
    </div>
    <p class="tip" id="tip">${icon("leaf")}<span>${esc(TIPS[Math.floor(Date.now() / 60000) % TIPS.length])}</span></p>
  </section>`;
}

export async function render(root, { state }) {
  const meta = state.meta;
  const defaults = { q: "", category: "todos", tipo: "todos", centro: "todos", sort: "nuevo", condition: "todos", min: "", max: "" };
  const f = { ...defaults, ...JSON.parse(sessionStorage.getItem("eg_filters") || "{}") };
  root.innerHTML = `
    ${hero(state)}
    <section class="searchbar">
      <input class="input" id="q" type="search" placeholder="Busca libros, apuntes, herramientas…" value="${esc(f.q)}" aria-label="Buscar">
      <div class="chips" role="group" aria-label="Categoría">
        ${["todos", ...meta.categories].map((c) => `<button class="chip" data-cat="${esc(c)}" aria-pressed="${f.category === c}">${icon(CAT_ICON[c] || "box")}${c === "todos" ? "Todo" : esc(c)}</button>`).join("")}
      </div>
      <div class="filters">
        <select class="input" id="tipo" aria-label="Tipo"><option value="todos">Todos los tipos</option>${meta.tipos.map((t) => `<option value="${t}" ${f.tipo === t ? "selected" : ""}>${TIPO[t]}</option>`).join("")}</select>
        <select class="input" id="centro" aria-label="Centro académico"><option value="todos">Todos los centros</option>${meta.centros.map((c) => `<option ${f.centro === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <select class="input" id="sort" aria-label="Orden">${[["nuevo", "Más recientes"], ["barato", "Precio: menor a mayor"], ["caro", "Precio: mayor a menor"]].map(([v, t]) => `<option value="${v}" ${f.sort === v ? "selected" : ""}>${t}</option>`).join("")}</select>
        <select class="input" id="condition" aria-label="Estado del producto"><option value="todos">Cualquier estado</option>${meta.conditions.map((c) => `<option ${f.condition === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <input class="input" id="min" type="number" min="0" step="1" inputmode="numeric" placeholder="Precio mín. $" aria-label="Precio mínimo" value="${esc(f.min)}">
        <input class="input" id="max" type="number" min="0" step="1" inputmode="numeric" placeholder="Precio máx. $" aria-label="Precio máximo" value="${esc(f.max)}">
      </div>
      <div class="row wrap" id="recent"></div>
    </section>
    <div class="sectionhd"><h2>Disponible ahora</h2><span class="muted small" id="count"></span></div>
    <section id="list" aria-live="polite"><div class="loading">Buscando…</div></section>
    <a class="btn accent fab" href="#/new">${icon("plus")} Publicar</a>`;

  let t;
  const load = async () => {
    sessionStorage.setItem("eg_filters", JSON.stringify(f));
    const qs = new URLSearchParams({ q: f.q, category: f.category, tipo: f.tipo, centro: f.centro, sort: f.sort, condition: f.condition, min_price: f.min, max_price: f.max });
    const { posts } = await api.get("/api/posts?" + qs);
    const list = root.querySelector("#list");
    if (!list) return;
    const cnt = root.querySelector("#count"); if (cnt) cnt.textContent = posts.length ? `${posts.length} publicación${posts.length === 1 ? "" : "es"}` : "";
    list.innerHTML = posts.length
      ? `<div class="grid">${posts.map(card).join("")}</div>`
      : `<div class="empty">${icon("leaf")}<h2>No encontramos nada con esos filtros</h2><p>Prueba otra palabra, o pídenos que te avisemos cuando alguien lo publique.</p>
          <div class="row wrap" style="justify-content:center">${f.q.trim().length >= 2 ? `<button class="btn" id="watch">${icon("heart")} Avisarme cuando publiquen «${esc(f.q.trim().slice(0, 30))}»</button>` : ""}<button class="btn ghost" id="clear">Limpiar filtros</button><a class="btn ghost" href="#/new">Publicar un artículo</a></div></div>`;
    list.querySelector("#clear")?.addEventListener("click", resetFilters);
    list.querySelector("#watch")?.addEventListener("click", async () => {
      try { await api.post("/api/wishlist", { term: f.q.trim(), category: f.category === "todos" ? "" : f.category, centro: f.centro === "todos" ? "" : f.centro }); toast("Listo: te avisaremos cuando alguien lo publique"); }
      catch (e) { toast(e.message, true); }
    });
  };
  // Búsquedas recientes (solo en este navegador).
  const recents = () => store.get("eg_recent", []);
  const paintRecent = () => {
    const r = recents(), box = root.querySelector("#recent");
    if (!box) return;
    box.innerHTML = r.length ? `<span class="muted small">Recientes:</span>${r.map((x, i) => `<button class="chip sm" data-rq="${i}">${icon("search")}${esc(x)}</button>`).join("")}<button class="linkbtn" id="clr">Borrar</button>` : "";
    box.querySelectorAll("[data-rq]").forEach((b) => (b.onclick = () => { f.q = r[+b.dataset.rq]; root.querySelector("#q").value = f.q; load(); }));
    box.querySelector("#clr")?.addEventListener("click", () => { store.set("eg_recent", []); paintRecent(); });
  };
  const remember = () => {
    const q = f.q.trim(); if (q.length < 2) return;
    store.set("eg_recent", [q, ...recents().filter((x) => x.toLowerCase() !== q.toLowerCase())].slice(0, 6)); paintRecent();
  };
  const resetFilters = () => { Object.assign(f, defaults); sessionStorage.setItem("eg_filters", JSON.stringify(f)); render(root, { state }); };
  paintRecent();
  root.querySelector("#q").oninput = (e) => { f.q = e.target.value; clearTimeout(t); t = setTimeout(load, 250); };
  root.querySelector("#q").addEventListener("change", remember);
  root.querySelector("#q").addEventListener("keydown", (e) => e.key === "Enter" && remember());
  for (const id of ["min", "max"]) root.querySelector("#" + id).oninput = (e) => { f[id] = e.target.value; clearTimeout(t); t = setTimeout(load, 350); };
  root.querySelectorAll("[data-cat]").forEach((b) => (b.onclick = () => {
    f.category = b.dataset.cat;
    root.querySelectorAll("[data-cat]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    load();
  }));
  for (const id of ["tipo", "centro", "sort", "condition"]) root.querySelector("#" + id).onchange = (e) => { f[id] = e.target.value; load(); };
  api.get("/api/impact").then((s) => root.querySelectorAll("#stats [data-n]").forEach((el) => countUp(el, s[el.dataset.n] || 0, { decimals: +(el.dataset.d || 0) }))).catch(() => {});
  await load();
}
