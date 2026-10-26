import { api } from "../api.js";
import { esc, icon, toast, timeAgo } from "../ui.js";

export async function render(root, { state, refresh }) {
  const meta = state.meta;
  const { items, max } = await api.get("/api/wishlist");
  root.innerHTML = `
  <div style="max-width:680px;margin:0 auto" class="stack">
    <div><h1>Lista de deseos</h1>
      <p class="muted">Dinos qué estás buscando. Cuando alguien publique algo que coincida, te llega un aviso (campana de arriba) con el enlace.</p></div>
    <form id="f" class="panelbox stack" novalidate>
      <label class="field">¿Qué buscas?<input class="input" name="term" maxlength="60" required minlength="2" placeholder="Cálculo vectorial, bata talla M, multímetro…"></label>
      <div class="filters" style="grid-template-columns:1fr 1fr">
        <label class="field">Categoría <span class="hint">(opcional)</span><select class="input" name="category"><option value="">Cualquiera</option>${meta.categories.map((c) => `<option>${esc(c)}</option>`).join("")}</select></label>
        <label class="field">Centro <span class="hint">(opcional)</span><select class="input" name="centro"><option value="">Cualquiera</option>${meta.centros.map((c) => `<option>${esc(c)}</option>`).join("")}</select></label>
      </div>
      <div id="err"></div>
      <button class="btn">${icon("heart")} Avisarme</button>
      <span class="muted small">${items.length} de ${max} deseos. Ignoramos acentos y mayúsculas al comparar.</span>
    </form>
    ${items.length ? `<div class="list">${items.map((w) => `<div class="item"><span class="avatar">${icon("heart")}</span>
      <div class="grow"><div class="t">${esc(w.term)}</div>
        <div class="muted small">${esc(w.category || "Cualquier categoría")} · ${esc(w.centro || "cualquier centro")} · desde ${timeAgo(w.created_at)}</div></div>
      <button class="btn sm ghost" data-del="${w.id}" aria-label="Quitar ${esc(w.term)}">${icon("x")}</button></div>`).join("")}</div>`
      : `<div class="empty">${icon("heart")}<h2>Todavía no tienes deseos</h2><p>Agrega lo que necesites este semestre y te avisamos.</p></div>`}
  </div>`;
  root.querySelector("#f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target));
    try { await api.post("/api/wishlist", fd); toast("Listo, te avisaremos"); refresh(); }
    catch (err) { root.querySelector("#err").innerHTML = `<div class="error" role="alert">${esc(err.message)}</div>`; }
  };
  root.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => { await api.del(`/api/wishlist/${b.dataset.del}`); refresh(); }));
}
