import { api } from "../api.js";
import { esc, icon, toast, TIPO } from "../ui.js";

export async function render(root, { args, state, go }) {
  const meta = state.meta;
  const editing = args[0] ? (await api.get(`/api/posts/${args[0]}`)).post : null;
  const p = editing || { title: "", description: "", category: meta.categories[0], centro: "General", tipo: "venta", price_cents: 0, condition: "Usado", images: [] };
  const opts = (list, sel, f = (x) => x) => list.map((v) => `<option value="${esc(v)}" ${v === sel ? "selected" : ""}>${esc(f(v))}</option>`).join("");

  root.innerHTML = `
  <div style="max-width:640px;margin:0 auto" class="stack">
    <h1>${editing ? "Editar publicación" : "Nueva publicación"}</h1>
    <form id="f" class="stack">
      <label class="field">Fotos <span class="hint">hasta ${meta.max_images} · JPG, PNG o WebP · 5 MB c/u${editing ? " · si subes nuevas, reemplazan las actuales" : ""}</span>
        <input class="input" type="file" name="images" accept="image/jpeg,image/png,image/webp" multiple id="files"></label>
      <div class="row wrap" id="prev"></div>
      <label class="field">Título<input class="input" name="title" required minlength="3" maxlength="100" value="${esc(p.title)}" placeholder="Libro de Cálculo Vectorial"></label>
      <label class="field">Descripción <span class="hint">cuenta su condición y por qué lo sueltas</span>
        <textarea class="input" name="description" required minlength="10" maxlength="1500">${esc(p.description)}</textarea></label>
      <div class="filters" style="grid-template-columns:1fr 1fr">
        <label class="field">Categoría<select class="input" name="category">${opts(meta.categories, p.category)}</select></label>
        <label class="field">Estado<select class="input" name="condition">${opts(meta.conditions, p.condition)}</select></label>
        <label class="field">Centro académico<select class="input" name="centro">${opts(meta.centros, p.centro)}</select></label>
        <label class="field">Tipo de operación<select class="input" name="tipo" id="tipo">${opts(meta.tipos, p.tipo, (t) => TIPO[t])}</select></label>
      </div>
      <label class="field" id="priceBox">Precio (MXN)<input class="input" name="price" id="price" inputmode="decimal" placeholder="250" value="${p.price_cents ? p.price_cents / 100 : ""}">
        <span class="hint">Las ventas usan pago protegido: el dinero se retiene hasta que el comprador confirma la recepción. Máximo $${meta.max_price_cents / 100}.</span></label>
      <div id="err"></div>
      <button class="btn block" id="go">${editing ? "Guardar cambios" : "Publicar"}</button>
    </form>
  </div>`;

  const sync = () => root.querySelector("#priceBox").classList.toggle("hidden", root.querySelector("#tipo").value !== "venta");
  root.querySelector("#tipo").onchange = sync; sync();
  root.querySelector("#files").onchange = (e) => {
    const prev = root.querySelector("#prev"); prev.innerHTML = "";
    [...e.target.files].slice(0, meta.max_images).forEach((f) => {
      const img = document.createElement("img"); img.src = URL.createObjectURL(f); img.alt = ""; img.style.cssText = "width:72px;height:72px;object-fit:cover;border-radius:12px";
      prev.append(img);
    });
  };
  root.querySelector("#f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = root.querySelector("#go"); btn.disabled = true; btn.textContent = "Guardando…";
    try {
      if (editing) { await api.form("PUT", `/api/posts/${p.id}`, fd); toast("Cambios guardados"); go(`#/post/${p.id}`); }
      else { const r = await api.form("POST", "/api/posts", fd); toast("Publicado"); go(`#/post/${r.id}`); }
    } catch (err) {
      root.querySelector("#err").innerHTML = `<div class="error" role="alert">${esc(err.message)}</div>`;
      btn.disabled = false; btn.textContent = editing ? "Guardar cambios" : "Publicar";
    }
  };
}
