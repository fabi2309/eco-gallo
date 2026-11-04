import { api } from "../api.js";
import { esc, icon, money, avatar, badges, toast, TIPO } from "../ui.js";
import { card } from "./home.js";

const STEPS = ["Fotos e información", "Detalles y precio", "Vista previa"];

export async function render(root, { args, state, go }) {
  const meta = state.meta;
  const editing = args[0] ? (await api.get(`/api/posts/${args[0]}`)).post : null;
  // Estado del asistente: vive en memoria mientras dura la pantalla.
  const st = editing
    ? { title: editing.title, description: editing.description, category: editing.category, condition: editing.condition,
        centro: editing.centro, tipo: editing.tipo, price: editing.price_cents ? String(editing.price_cents / 100) : "", files: [] }
    : { title: "", description: "", category: meta.categories[0], condition: meta.conditions.includes("Usado") ? "Usado" : meta.conditions[0],
        centro: "General", tipo: "venta", price: "", files: [] };
  let step = 0;
  const urls = new Map();   // File -> URL de vista previa
  const urlOf = (f) => { if (!urls.has(f)) urls.set(f, URL.createObjectURL(f)); return urls.get(f); };
  const cleanup = () => { urls.forEach((u) => URL.revokeObjectURL(u)); urls.clear(); };

  const opts = (list, sel, f = (x) => x) => list.map((v) => `<option value="${esc(v)}" ${v === sel ? "selected" : ""}>${esc(f(v))}</option>`).join("");
  const images = () => (st.files.length ? st.files.map(urlOf) : editing ? editing.images : []);

  root.innerHTML = `
  <div class="wizard">
    <h1>${editing ? "Editar publicación" : "Nueva publicación"}</h1>
    <ol class="steps" id="steps" aria-label="Progreso"></ol>
    <form id="f" class="stack" novalidate></form>
  </div>`;
  const form = root.querySelector("#f");
  const stepsEl = root.querySelector("#steps");

  const drawSteps = () => {
    stepsEl.innerHTML = STEPS.map((t, i) => `<li class="${i < step ? "done" : i === step ? "now" : ""}" ${i === step ? 'aria-current="step"' : ""}><span>${t}</span></li>`).join("");
  };
  const err = (m) => (form.querySelector("#err").innerHTML = m ? `<div class="error" role="alert">${esc(m)}</div>` : "");
  const nav = (last) => `<div id="err"></div><div class="nav">
    ${step > 0 ? '<button type="button" class="btn ghost" id="back">Atrás</button>' : `<a class="btn ghost" href="${editing ? `#/post/${editing.id}` : "#/"}">Cancelar</a>`}
    <button class="btn ${last ? "accent" : ""}" id="next">${last ? (editing ? "Guardar cambios" : "Publicar ahora") : "Siguiente"}</button></div>`;

  // ---------------------------------------------------------------- paso 1
  function step1() {
    form.innerHTML = `
      <div class="field">Fotos <span class="hint">hasta ${meta.max_images} · JPG, PNG o WebP · 5 MB c/u. La primera será la portada.</span>
        <label class="dropzone" id="drop" for="files">${icon("camera")}<b>Toca para elegir fotos</b><span class="muted small">o arrástralas aquí</span>
          <input type="file" id="files" accept="image/jpeg,image/png,image/webp" multiple hidden></label></div>
      <div class="photos" id="photos"></div>
      ${editing && !st.files.length ? `<p class="muted small">Estas son las fotos actuales. Si subes nuevas, reemplazan a las actuales.</p>` : ""}
      <label class="field">Título <span class="hint count" id="tc"></span>
        <input class="input" name="title" maxlength="100" value="${esc(st.title)}" placeholder="Libro de Cálculo Vectorial" autocomplete="off"></label>
      <label class="field">Descripción <span class="hint count" id="dc"></span>
        <textarea class="input" name="description" maxlength="1500" rows="5" placeholder="Cuenta su condición y por qué lo sueltas">${esc(st.description)}</textarea></label>
      ${nav(false)}`;
    const photos = form.querySelector("#photos");
    const drawPhotos = () => {
      const list = st.files.length ? st.files.map((f) => ({ src: urlOf(f), f })) : (editing ? editing.images.map((src) => ({ src })) : []);
      photos.innerHTML = list.map((x, i) => `<div class="ph1"><img src="${esc(x.src)}" alt="Foto ${i + 1}">${i === 0 ? '<span class="cover">Portada</span>' : ""}
        ${x.f ? `<button type="button" data-rm="${i}" aria-label="Quitar foto ${i + 1}">${icon("x")}</button>` : ""}</div>`).join("");
      photos.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { st.files.splice(+b.dataset.rm, 1); drawPhotos(); }));
    };
    const add = (fileList) => {
      for (const f of fileList) {
        if (st.files.length >= meta.max_images) { err(`Máximo ${meta.max_images} fotos.`); break; }
        if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { err("Solo se permiten imágenes JPG, PNG o WebP."); continue; }
        if (f.size > 5 * 1024 * 1024) { err(`«${f.name}» pesa más de 5 MB.`); continue; }
        st.files.push(f);
      }
      drawPhotos();
    };
    form.querySelector("#files").onchange = (e) => { err(""); add([...e.target.files]); e.target.value = ""; };
    const drop = form.querySelector("#drop");
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => { err(""); add([...e.dataTransfer.files]); });
    const t = form.querySelector("[name=title]"), d = form.querySelector("[name=description]");
    const count = () => { form.querySelector("#tc").textContent = `${t.value.length}/100`; form.querySelector("#dc").textContent = `${d.value.length}/1500`; };
    t.oninput = d.oninput = count; count(); drawPhotos();
    form.querySelector("#next").onclick = (e) => {
      e.preventDefault();
      st.title = t.value.trim(); st.description = d.value.trim();
      if (st.title.length < 3) return err("Escribe un título de al menos 3 caracteres.");
      if (st.description.length < 10) return err("La descripción debe tener al menos 10 caracteres.");
      go2(1);
    };
  }

  // ---------------------------------------------------------------- paso 2
  function step2() {
    form.innerHTML = `
      <div class="filters" style="grid-template-columns:1fr 1fr">
        <label class="field">Categoría<select class="input" name="category">${opts(meta.categories, st.category)}</select></label>
        <label class="field">Estado del artículo<select class="input" name="condition">${opts(meta.conditions, st.condition)}</select></label>
        <label class="field">Centro académico<select class="input" name="centro">${opts(meta.centros, st.centro)}</select></label>
        <label class="field">Tipo de operación<select class="input" name="tipo" id="tipo">${opts(meta.tipos, st.tipo, (t) => TIPO[t])}</select></label>
      </div>
      <label class="field" id="priceBox">Precio (MXN)<input class="input" name="price" inputmode="decimal" placeholder="250" value="${esc(st.price)}" autocomplete="off">
        <span class="hint">Las ventas usan pago protegido: el dinero se retiene hasta que el comprador confirma la recepción. Máximo ${money(meta.max_price_cents)}.</span></label>
      <div class="notice" id="freeNote">${icon("leaf")} Las donaciones y los trueques no llevan precio: se acuerdan por mensaje.</div>
      ${nav(false)}`;
    const tipo = form.querySelector("#tipo");
    const sync = () => {
      const venta = tipo.value === "venta";
      form.querySelector("#priceBox").classList.toggle("hidden", !venta);
      form.querySelector("#freeNote").classList.toggle("hidden", venta);
    };
    tipo.onchange = sync; sync();
    form.querySelector("#next").onclick = (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(form));
      Object.assign(st, { category: fd.category, condition: fd.condition, centro: fd.centro, tipo: fd.tipo, price: (fd.price || "").trim() });
      if (st.tipo === "venta") {
        const v = st.price.replace(",", ".");
        if (!/^\d+(\.\d{1,2})?$/.test(v) || +v <= 0) return err("Escribe un precio válido, por ejemplo 250 o 99.50.");
        if (Math.round(+v * 100) > meta.max_price_cents) return err(`El precio máximo es ${money(meta.max_price_cents)}.`);
      } else st.price = "";
      go2(2);
    };
  }

  // ---------------------------------------------------------------- paso 3
  function step3() {
    const u = state.user;
    const imgs = images();
    const cents = st.tipo === "venta" ? Math.round(+st.price.replace(",", ".") * 100) : 0;
    const fake = { id: 0, title: st.title, tipo: st.tipo, price_cents: cents, condition: st.condition, status: "active",
      images: imgs, author: { name: u.name } };
    form.innerHTML = `
      <div class="notice">${icon("search")} Así verán tu publicación. Revisa que todo esté bien antes de publicar.</div>
      <div class="previewbox">
        <div class="lbl">En el catálogo</div>
        <div class="previewcard">${card(fake)}</div>
        <div class="lbl">Al abrirla</div>
        <div class="detail" style="grid-template-columns:1fr">
          <div class="gallery"><div class="main" style="cursor:default">${imgs.length ? `<img src="${esc(imgs[0])}" alt="">` : `<div class="card"><div class="ph"><div class="noimg">${icon("image")}</div></div></div>`}</div>
            ${imgs.length > 1 ? `<div class="thumbs">${imgs.map((s) => `<button type="button" tabindex="-1"><img src="${esc(s)}" alt=""></button>`).join("")}</div>` : ""}</div>
          <div class="info">
            <div class="row wrap"><span class="fact">${esc(TIPO[st.tipo])}</span><span class="fact">${esc(st.condition)}</span><span class="fact">${esc(st.category)}</span></div>
            <h1>${esc(st.title)}</h1>
            <div class="big">${st.tipo === "venta" ? money(cents) : st.tipo === "donacion" ? "Gratis" : "Se intercambia"}</div>
            <p style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(st.description)}</p>
            <div class="muted small">${esc(st.centro)} · publicado ahora</div>
            <div class="seller">${avatar(u)}<div class="grow"><b>${esc(u.name)}</b>${badges(u) ? `<div class="insignias-row">${badges(u)}</div>` : ""}<div class="muted small">${esc(u.carrera || u.centro || "")}</div></div></div>
          </div>
        </div>
        <div class="row wrap"><button type="button" class="btn ghost sm" data-edit="0">Editar fotos y texto</button><button type="button" class="btn ghost sm" data-edit="1">Editar detalles y precio</button></div>
      </div>
      ${nav(true)}`;
    form.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => go2(+b.dataset.edit)));
    form.querySelector("#next").onclick = submit;
  }

  async function submit(e) {
    e.preventDefault();
    const btn = form.querySelector("#next"); btn.disabled = true; btn.textContent = "Guardando…";
    const fd = new FormData();
    ["title", "description", "category", "condition", "centro", "tipo"].forEach((k) => fd.append(k, st[k]));
    fd.append("price", st.tipo === "venta" ? st.price.replace(",", ".") : "");
    st.files.forEach((f) => fd.append("images", f, f.name));
    try {
      if (editing) { await api.form("PUT", `/api/posts/${editing.id}`, fd); toast("Cambios guardados"); cleanup(); go(`#/post/${editing.id}`); }
      else { const r = await api.form("POST", "/api/posts", fd); toast("Enviada a revisión: se mostrará cuando un administrador la apruebe"); cleanup(); go(`#/post/${r.id}`); }
    } catch (er) {
      err(er.message); btn.disabled = false; btn.textContent = editing ? "Guardar cambios" : "Publicar ahora";
    }
  }

  function go2(n) {
    step = n; drawSteps();
    [step1, step2, step3][n]();
    form.querySelector("#back")?.addEventListener("click", () => go2(step - 1));
    window.scrollTo({ top: 0 });
    form.querySelector("input:not([type=file]), select, textarea")?.focus({ preventScroll: true });
  }
  form.onsubmit = (e) => { e.preventDefault(); form.querySelector("#next")?.click(); };
  go2(0);
}
