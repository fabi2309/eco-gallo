// Carrito (US-04): varios artículos en un solo pago. Cada uno conserva su propia orden protegida.
import { api } from "../api.js";
import { esc, icon, money, toast, choosePayment } from "../ui.js";
import { prepareCardPayment } from "../payflow.js";

export async function render(root, { state, go, refresh }) {
  const c = await api.get("/api/cart");
  state.cartCount = c.count;
  const ok = c.items.filter((i) => i.available), gone = c.items.filter((i) => !i.available);
  const row = (i) => `<div class="item${i.available ? "" : " gone"}">
      ${i.image ? `<img class="thumb" src="${esc(i.image)}" alt="">` : '<span class="thumb"></span>'}
      <div class="grow"><a class="t" href="#/post/${i.post_id}">${esc(i.title)}</a>
        <div class="muted small">Vende ${esc(i.seller_name)}${i.available ? "" : " · ya no está disponible"}</div></div>
      <b>${money(i.price_cents)}</b>
      <button class="btn ghost sm" data-rm="${i.post_id}" aria-label="Quitar ${esc(i.title)} del carrito">${icon("trash")}</button></div>`;
  root.innerHTML = `
  <div style="max-width:760px;margin:0 auto" class="stack">
    <h1>Carrito</h1>
    ${c.items.length ? `
      <div class="list">${ok.map(row).join("")}</div>
      ${gone.length ? `<h3 class="muted small">Ya no disponibles</h3><div class="list">${gone.map(row).join("")}</div>` : ""}
      <div class="panelbox stack">
        <div class="row"><span class="grow">Total (${ok.length} artículo${ok.length === 1 ? "" : "s"})</span><b style="font-size:1.3rem">${money(c.total_cents)}</b></div>
        <p class="muted small">${icon("shield")} Elige Mercado Pago o efectivo. Cada artículo queda como una compra por separado con su vendedor.</p>
        <button class="btn block" id="pay" ${ok.length ? "" : "disabled"}>${icon("bag")} Comprar ${money(c.total_cents)}</button>
      </div>`
    : `<div class="empty">${icon("bag")}<h2>Tu carrito está vacío</h2><p>Agrega artículos en venta para pagarlos juntos.</p><a class="btn" href="#/">Ver artículos</a></div>`}
  </div>`;
  root.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = async () => {
    try { await api.del(`/api/cart/${b.dataset.rm}`); refresh(); } catch (e) { toast(e.message, true); }
  }));
  root.querySelector("#pay")?.addEventListener("click", async (e) => {
    const method = await choosePayment({ meta: state.meta, total: c.total_cents, many: ok.length > 1,
      acceptsCard: ok.every((i) => i.accepts_card) });
    if (!method) return;
    let card = null;
    if (method === "en_linea") {
      const prep = await prepareCardPayment(state, c.total_cents);
      if (!prep) return;
      card = prep.card;
    }
    e.target.disabled = true;
    try {
      const r = await api.post("/api/cart/checkout", { method, ...(card ? { card } : {}) });
      if (r.checkout_url) { window.location.assign(r.checkout_url); return; }
      toast(method === "efectivo" ? "Artículos apartados. Coordina cada entrega y paga al recibir." : "Pago retenido. Coordina cada entrega por mensaje.");
      go("#/orders");
    } catch (err) { toast(err.message, true); refresh(); }
  });
}
