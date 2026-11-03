import { api } from "../api.js";
import { esc, icon, money, timeAgo, avatar, ask, toast, TIPO } from "../ui.js";

export async function render(root, { args, state, go, refresh }) {
  const { post: p } = await api.get(`/api/posts/${args[0]}`);
  const mine = p.author.id === state.user.id;
  const venta = p.tipo === "venta";
  let shown = 0;

  root.innerHTML = `
  <div class="detail">
    <div class="gallery">
      <div class="main">${p.images.length ? `<img id="big" src="${esc(p.images[0])}" alt="${esc(p.title)}">` : `<div class="card"><div class="ph"><div class="noimg">${icon("image")}</div></div></div>`}</div>
      ${p.images.length > 1 ? `<div class="thumbs">${p.images.map((s, i) => `<button data-i="${i}" aria-label="Foto ${i + 1}" aria-current="${i === 0}"><img src="${esc(s)}" alt=""></button>`).join("")}</div>` : ""}
    </div>
    <div class="info">
      <div class="row wrap"><span class="fact">${esc(TIPO[p.tipo])}</span><span class="fact">${esc(p.condition)}</span><span class="fact">${esc(p.category)}</span>
        ${p.status === "reserved" ? '<span class="fact">Reservado</span>' : ""}${p.status === "paused" ? '<span class="fact">Pausada</span>' : ""}${p.status === "sold" ? '<span class="fact">Ya no disponible</span>' : ""}</div>
      <h1>${esc(p.title)}</h1>
      <div class="big">${venta ? money(p.price_cents) : p.tipo === "donacion" ? "Gratis" : "Se intercambia"}</div>
      <p style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(p.description)}</p>
      <div class="muted small">${esc(p.centro)} · publicado ${timeAgo(p.created_at)}</div>
      <div class="seller">${avatar(p.author)}
        <div class="grow"><b>${esc(p.author.name)}</b><div class="muted small">${esc(p.author.carrera || p.author.centro)}</div>
        ${p.author.bio ? `<div class="small bio">${esc(p.author.bio)}</div>` : ""}</div></div>
      ${mine ? `
        <div class="panelbox stack" style="margin:14px 0 6px;padding:12px 14px;background:var(--bg-card)">
          <b class="small muted" style="letter-spacing:.03em">ESTADÍSTICAS DE TU PUBLICACIÓN</b>
          <div class="row wrap" style="gap:18px;font-size:.95rem">
            <span title="Total de visualizaciones">${icon("eye")} <b>${p.stats?.views || 0}</b> vistas</span>
            <span title="Personas que te han contactado por mensaje">${icon("chat")} <b>${p.stats?.contacts || 0}</b> contactos</span>
            <span title="Personas que guardaron o tienen en lista de deseos">${icon("heart")} <b>${p.stats?.interested || 0}</b> interesados</span>
          </div>
        </div>` : `
        <div style="margin:12px 0 4px">
          <button class="btn sm ${p.is_favorited ? "green" : "ghost"}" id="favbtn" style="width:100%">
            ${icon("heart")} <span>${p.is_favorited ? "Guardado en tus favoritos" : "Guardar (avisarme si baja de precio)"}</span>
          </button>
        </div>`}
      <div id="actions" class="stack"></div>
    </div>
  </div>`;

  root.querySelectorAll(".thumbs button").forEach((b) => (b.onclick = () => {
    shown = +b.dataset.i;
    root.querySelector("#big").src = p.images[shown];
    root.querySelectorAll(".thumbs button").forEach((x) => x.setAttribute("aria-current", x === b));
  }));

  const act = root.querySelector("#actions");
  if (mine) {
    act.innerHTML = `
      ${p.live_order ? `<a class="btn accent block" href="#/order/${p.live_order.id}">${icon("shield")} Ver el pago retenido</a>` : ""}
      ${p.status === "paused" ? `<div class="notice">${icon("pause")} Tu publicación está <b>pausada</b>: nadie la ve en el catálogo hasta que la reanudes.</div>` : ""}
      ${p.status === "active" || p.status === "paused" ? `<div class="row wrap"><a class="btn ghost grow" href="#/edit/${p.id}">Editar</a>
        <button class="btn ghost grow" id="pause">${p.status === "paused" ? `${icon("play")} Reanudar` : `${icon("pause")} Pausar`}</button>
        ${venta || p.status === "paused" ? "" : '<button class="btn green grow" id="close">Marcar como entregado</button>'}
        <button class="btn ghost grow" id="del">Eliminar</button></div>` : ""}`;
    act.querySelector("#pause")?.addEventListener("click", async () => {
      try { await api.post(`/api/posts/${p.id}/pause`, { paused: p.status !== "paused" }); toast(p.status === "paused" ? "Publicación reanudada" : "Publicación pausada"); refresh(); }
      catch (e) { toast(e.message, true); }
    });
    act.querySelector("#close")?.addEventListener("click", async () => {
      if (!(await ask({ title: "¿Ya lo entregaste?", text: "La publicación dejará de mostrarse y contará en el impacto de la comunidad.", confirm: "Sí, entregado" }))) return;
      await api.post(`/api/posts/${p.id}/close`); toast("Publicación cerrada"); refresh();
    });
    act.querySelector("#del")?.addEventListener("click", async () => {
      if (!(await ask({ title: "¿Eliminar esta publicación?", confirm: "Eliminar", danger: true }))) return;
      await api.del(`/api/posts/${p.id}`); toast("Publicación eliminada"); go("#/mine");
    });
    return;
  }

  const favbtn = root.querySelector("#favbtn");
  if (favbtn) {
    favbtn.onclick = async () => {
      try {
        const r = await api.post(`/api/posts/${p.id}/favorite`);
        toast(r.favorited ? "Guardado en tus favoritos. Te avisaremos si baja de precio." : "Eliminado de tus favoritos");
        refresh();
      } catch (e) {
        toast(e.message, true);
      }
    };
  }

  if (venta && p.status === "active") {
    act.innerHTML = `
      <div class="promise"><strong>${icon("shield")} Pago protegido</strong>
        <span>Tu dinero se queda retenido en ECO-GALLO y solo se entrega al vendedor cuando tú confirmas que recibiste el artículo.</span></div>
      <button class="btn block" id="buy">${icon("lock")} Comprar con pago protegido · ${money(p.price_cents)}</button>
      <a class="btn ghost block" href="#/chat/${p.id}/${p.author.id}">${icon("chat")} Preguntar al vendedor</a>`;
    act.querySelector("#buy").onclick = async () => {
      const ok = await ask({
        title: `Pagar ${money(p.price_cents)}`,
        text: "El pago se retiene hasta que confirmes la recepción. Si algo sale mal puedes abrir una disputa y la administración decide. (Modo demostración: no se cobra dinero real.)",
        confirm: "Pagar y retener",
      });
      if (!ok) return;
      try { const r = await api.post("/api/orders", { post_id: p.id }); toast("Pago retenido. Coordina la entrega por mensaje."); go(`#/order/${r.id}`); }
      catch (e) { toast(e.message, true); refresh(); }
    };
  } else if (p.status === "active") {
    act.innerHTML = `<a class="btn block" href="#/chat/${p.id}/${p.author.id}">${icon("chat")} Contactar para ${p.tipo === "donacion" ? "pedirlo" : "proponer un trueque"}</a>
      <p class="muted small">Las donaciones y los trueques se acuerdan por mensaje y no usan pago.</p>`;
  } else if (p.live_order) {
    act.innerHTML = `<a class="btn accent block" href="#/order/${p.live_order.id}">${icon("shield")} Ver mi compra</a>`;
  } else if (p.status === "paused") {
    act.innerHTML = `<div class="notice">El vendedor pausó esta publicación por ahora.</div>`;
  } else {
    act.innerHTML = `<div class="notice">Este artículo ya no está disponible.</div>`;
  }
  act.insertAdjacentHTML("beforeend", `<button class="btn ghost sm" id="rep" style="justify-self:start">Reportar publicación</button>`);
  act.querySelector("#rep").onclick = async () => {
    const reason = await ask({ title: "Reportar publicación", field: "¿Qué está mal con esta publicación?", confirm: "Enviar reporte" });
    if (!reason) return;
    try { const r = await api.post("/api/reports", { target_type: "post", target_id: p.id, reason }); toast(r.message); } catch (e) { toast(e.message, true); }
  };
}
