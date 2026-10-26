import { api } from "../api.js";
import { esc, icon, money, timeAgo, ask, toast, STATUS } from "../ui.js";

export async function render(root, ctx) {
  return ctx.args[0] ? detail(root, ctx) : list(root, ctx);
}

async function list(root, { state }) {
  const [{ orders }, w] = await Promise.all([api.get("/api/orders"), api.get("/api/wallet")]);
  let tab = "buyer";
  const draw = () => {
    const rows = orders.filter((o) => o.role === tab);
    root.querySelector("#rows").innerHTML = rows.length
      ? rows.map((o) => `<a class="item" href="#/order/${o.id}">
          ${o.image ? `<img class="thumb" src="${esc(o.image)}" alt="">` : '<span class="thumb"></span>'}
          <div class="grow"><div class="t">${esc(o.post_title)}</div>
            <div class="muted small">${tab === "buyer" ? "Vendedor: " + esc(o.seller.name) : "Comprador: " + esc(o.buyer.name)} · ${timeAgo(o.updated_at)}</div>
            <span class="state ${STATUS[o.status][1]} small" style="padding:2px 10px;font-size:.8rem">${esc(STATUS[o.status][0])}</span></div>
          <b>${money(o.amount_cents)}</b></a>`).join("")
      : `<div class="empty">${icon("bag")}<h2>${tab === "buyer" ? "Todavía no has comprado nada" : "Todavía no tienes ventas"}</h2><p>${tab === "buyer" ? "Cuando pagues un artículo, el dinero quedará retenido aquí hasta que lo recibas." : "Cuando alguien pague uno de tus artículos, lo verás aquí."}</p></div>`;
    root.querySelectorAll("[data-t]").forEach((b) => b.setAttribute("aria-selected", b.dataset.t === tab));
  };
  root.innerHTML = `
    <h1>Compras y ventas</h1>
    <div class="kpis" style="margin:16px 0 20px">
      <div class="kpi"><div class="n">${money(w.available_cents)}</div><div class="muted small">Cobrado (liberado)</div></div>
      <div class="kpi"><div class="n">${money(w.pending_cents)}</div><div class="muted small">Por liberar de tus ventas</div></div>
      <div class="kpi"><div class="n">${money(w.buyer_held_cents)}</div><div class="muted small">Pagado y retenido por ti</div></div>
    </div>
    <div class="tabs" role="tablist"><button role="tab" data-t="buyer">Mis compras</button><button role="tab" data-t="seller">Mis ventas</button></div>
    <div class="list" id="rows"></div>`;
  root.querySelectorAll("[data-t]").forEach((b) => (b.onclick = () => { tab = b.dataset.t; draw(); }));
  draw();
}

const STEPS = [
  ["paid", "Pagado y retenido", "El dinero está en custodia de ECO-GALLO. El vendedor todavía no lo recibe."],
  ["delivered", "Entrega", "Se coordinan y entregan el artículo en un punto seguro del campus."],
  ["confirmed", "Recepción confirmada", "El comprador confirma que lo recibió y en buen estado."],
  ["released", "Pago liberado al vendedor", "Solo ahora el dinero pasa al vendedor."],
];

function track(o) {
  const st = o.status;
  let idx = { HELD: 1, DELIVERED: 2, DISPUTED: 2, RELEASED: 4, REFUNDED: 1 }[st];
  if (st === "RELEASED") idx = 4;
  return STEPS.map(([k, t, d], i) => {
    let cls = i < idx ? "done" : i === idx ? "now" : "idle";
    let ic = i < idx ? "check" : i === 0 ? "lock" : i === 1 ? "box" : i === 2 ? "check" : "shield";
    let title = t, desc = d;
    if (st === "DISPUTED" && i === 2) { cls = "bad"; ic = "alert"; title = "En disputa"; desc = "El dinero sigue retenido mientras la administración revisa el caso."; }
    if (st === "REFUNDED") { if (i === 0) { cls = "done"; } if (i === 1) { cls = "bad"; ic = "undo"; title = "Pago devuelto al comprador"; desc = "La orden se cerró con reembolso; el artículo vuelve a estar disponible."; } if (i > 1) return ""; }
    return `<li class="${cls}"><span class="dot">${icon(ic)}</span><div><b>${esc(title)}</b><span class="muted small">${esc(desc)}</span></div></li>`;
  }).join("");
}

const WHERE = {
  HELD: "En custodia de ECO-GALLO", DELIVERED: "En custodia de ECO-GALLO", DISPUTED: "En custodia (en revisión)",
  RELEASED: "Con el vendedor", REFUNDED: "De vuelta con el comprador",
};

async function detail(root, { args, state, refresh, go }) {
  const { order: o } = await api.get(`/api/orders/${args[0]}`);
  const [label, kind] = STATUS[o.status];
  const A = new Set(o.actions);
  const BTN = {
    confirm: `<button class="btn green block" data-a="confirm">${icon("check")} Sí, ya lo recibí: liberar el pago</button>`,
    deliver: `<button class="btn block" data-a="deliver">${icon("box")} Marcar como entregado</button>`,
    dispute: `<button class="btn ghost block" data-a="dispute">${icon("alert")} Hubo un problema</button>`,
    refund: `<button class="btn ghost block" data-a="refund">${icon("undo")} Devolver el pago al comprador</button>`,
    resolve_release: `<button class="btn green block" data-a="resolve-release">Liberar al vendedor</button>`,
    resolve_refund: `<button class="btn danger block" data-a="resolve-refund">Reembolsar al comprador</button>`,
  };
  const who = o.role === "buyer" ? o.seller : o.buyer;
  const help = {
    buyer: { HELD: "Coordina la entrega con el vendedor. No confirmes hasta tener el artículo en tus manos.", DELIVERED: "El vendedor dice que ya te lo entregó. Revisa que esté como lo describió y confirma, o cuéntanos si hubo un problema." },
    seller: { HELD: "El pago ya está retenido. Entrega el artículo en un punto seguro y márcalo como entregado.", DELIVERED: "Esperando a que el comprador confirme la recepción. Tu dinero se libera en cuanto lo haga." },
  }[o.role]?.[o.status] || "";

  root.innerHTML = `
  <div style="max-width:720px;margin:0 auto" class="stack">
    <a href="#/orders" class="small">← Compras y ventas</a>
    <div class="vault">
      <div class="vault-hd"><div><h1 style="font-size:1.6rem">${esc(o.post_title)}</h1>
        <div class="muted small">${o.role === "buyer" ? "Compras a" : "Vendes a"} <b>${esc(who.name)}</b> · orden #${o.id}</div></div>
        <span class="state ${kind}">${icon(kind === "ok" ? "check" : kind === "bad" ? "alert" : "lock")} ${esc(label)}</span></div>
      <div class="money"><div><div class="muted small">Monto</div><div class="amt">${money(o.amount_cents)}</div></div>
        <div style="text-align:right"><div class="muted small">Dónde está el dinero</div><b>${esc(WHERE[o.status])}</b></div></div>
      ${help ? `<div class="notice">${esc(help)}</div>` : ""}
      <ol class="track" aria-label="Avance del pago">${track(o)}</ol>
      ${o.dispute_reason ? `<div class="error">Motivo de la disputa: ${esc(o.dispute_reason)}</div>` : ""}
      <div class="stack" id="acts">${o.actions.map((a) => BTN[a]).join("")}</div>
      ${o.status === "HELD" || o.status === "DELIVERED" ? `<a class="btn ghost" href="#/chat/${o.post_id}/${who.id}">${icon("chat")} Escribir a ${esc(who.name.split(" ")[0])}</a>` : ""}
    </div>
    <div class="panelbox"><h3 style="margin-bottom:10px">Historial</h3><div class="log">
      ${o.events.map((e) => `<div><b>${esc(e.actor || "Sistema")}</b> · <span class="muted">${timeAgo(e.created_at)}</span><br>${esc(e.note || e.event)}</div>`).join("")}</div></div>
  </div>`;

  root.querySelectorAll("[data-a]").forEach((b) => (b.onclick = async () => {
    const a = b.dataset.a;
    const body = {};
    if (a === "confirm") { if (!(await ask({ title: "¿Recibiste el artículo?", text: "Al confirmar, el dinero se libera al vendedor y ya no se puede revertir.", confirm: "Confirmar y liberar" }))) return; }
    if (a === "dispute") { const r = await ask({ title: "Cuéntanos qué pasó", text: "El dinero seguirá retenido y la administración revisará el caso.", field: "No llegó, no es como se describió…", confirm: "Abrir disputa" }); if (!r) return; body.reason = r; }
    if (a === "refund") { if (!(await ask({ title: "¿Devolver el pago?", text: "El comprador recupera su dinero y tu artículo vuelve a publicarse.", confirm: "Devolver pago", danger: true }))) return; }
    if (a.startsWith("resolve")) { const n = await ask({ title: a === "resolve-release" ? "Liberar al vendedor" : "Reembolsar al comprador", text: "Escribe la razón de tu decisión.", field: "Motivo de la resolución", confirm: "Resolver" }); if (!n) return; body.note = n; }
    b.disabled = true;
    try { await api.post(`/api/orders/${o.id}/${a}`, body); toast("Listo"); refresh(); }
    catch (e) { toast(e.message, true); refresh(); }
  }));
}
