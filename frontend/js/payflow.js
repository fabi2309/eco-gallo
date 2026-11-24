// Pagos con tarjeta: confirmar el celular por SMS, capturar la tarjeta del comprador y la cuenta del vendedor.
// El número completo de la tarjeta/cuenta y el CVV se validan AQUÍ, en el navegador, y nunca se envían
// al servidor: solo viajan la marca, los últimos 4 dígitos, el vencimiento y el titular.
import { api } from "./api.js";
import { esc, icon, money, toast } from "./ui.js";

// ------------------------------------------------------------------ utilidades de tarjeta
export const digits = (v) => String(v || "").replace(/\D/g, "");

export function luhn(num) {
  let sum = 0, dbl = false;
  for (let i = num.length - 1; i >= 0; i--) {
    let d = +num[i];
    if (dbl) { d *= 2; if (d > 9) d -= 9; }
    sum += d; dbl = !dbl;
  }
  return num.length >= 13 && sum % 10 === 0;
}

export function brandOf(num) {
  if (/^4/.test(num)) return "visa";
  if (/^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))/.test(num)) return "mastercard";
  if (/^3[47]/.test(num)) return "amex";
  if (/^(506|5062|6060|639)/.test(num)) return "carnet";
  return "tarjeta";
}
export const BRAND_NAME = { visa: "Visa", mastercard: "Mastercard", amex: "American Express", carnet: "Carnet", tarjeta: "Tarjeta" };

// CLABE: 18 dígitos; el último es verificador (pesos 3,7,1).
export function clabeOk(c) {
  if (!/^\d{18}$/.test(c)) return false;
  const w = [3, 7, 1];
  let s = 0;
  for (let i = 0; i < 17; i++) s += (+c[i] * w[i % 3]) % 10;
  return (10 - (s % 10)) % 10 === +c[17];
}

const groups = (num, brand) => (brand === "amex"
  ? [num.slice(0, 4), num.slice(4, 10), num.slice(10, 15)]
  : num.match(/.{1,4}/g) || []).filter(Boolean).join(" ");

// ------------------------------------------------------------------ ventana base
function modal(html, { label }) {
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `<div class="modal paymodal" role="dialog" aria-modal="true" aria-label="${esc(label)}">${html}</div>`;
  document.body.append(ov);
  return ov;
}

// ------------------------------------------------------------------ 1) celular confirmado por SMS
/** Devuelve true si el usuario ya tiene (o acaba de confirmar) su celular. */
export function ensurePhone(state, { reason = "Para pagar con tarjeta" } = {}) {
  if (state.user?.payments?.card_ready) return Promise.resolve(true);
  return phoneDialog(state, reason);
}

export function phoneDialog(state, reason = "") {
  return new Promise((resolve) => {
    const ov = modal("", { label: "Confirmar celular" });
    const box = ov.querySelector(".modal");
    const done = (v) => { ov.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => e.key === "Escape" && done(false);
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", (e) => e.target === ov && done(false));

    const stepPhone = (prefill = "") => {
      box.innerHTML = `<h2>${icon("shield")} Confirma tu celular</h2>
        <p class="muted">${esc(reason ? reason + ", " : "")}necesitamos un celular confirmado. Si un artículo no se entrega, la otra persona y administración podrán localizarte.</p>
        <form class="stack" id="pf" novalidate>
          <label>Número de celular (10 dígitos)
            <div class="phonefield"><span>+52</span><input class="input" id="ph" inputmode="tel" autocomplete="tel-national" maxlength="14" placeholder="449 123 4567" value="${esc(prefill)}" required></div></label>
          <div id="perr" role="alert"></div>
          <div class="row"><button type="button" class="btn ghost grow" data-x>Cancelar</button><button class="btn grow" id="send">Enviar código por SMS</button></div>
        </form>`;
      box.querySelector("[data-x]").onclick = () => done(false);
      const inp = box.querySelector("#ph");
      inp.focus();
      box.querySelector("#pf").onsubmit = async (e) => {
        e.preventDefault();
        const d = digits(inp.value).replace(/^52(?=\d{10}$)/, "");
        const err = box.querySelector("#perr");
        if (!/^[1-9]\d{9}$/.test(d)) { err.innerHTML = `<div class="notice bad">Escribe tu celular a 10 dígitos, sin el 52.</div>`; return; }
        const btn = box.querySelector("#send"); btn.disabled = true;
        try {
          const r = await api.post("/api/me/phone", { phone: d });
          stepCode(r, d);
        } catch (ex) { err.innerHTML = `<div class="notice bad">${esc(ex.message)}</div>`; btn.disabled = false; }
      };
    };

    const stepCode = (r, number) => {
      box.innerHTML = `<h2>${icon("chat")} Escribe el código</h2>
        <p class="muted">Te enviamos un SMS con 6 dígitos al <b>+52 ${esc(r.phone)}</b>. Vence en 10 minutos.</p>
        ${r.dev_code ? `<div class="smsbubble" role="status"><span class="smsfrom">${icon("chat")} Mensaje · ECO-GALLO UAA</span>Tu código para confirmar tu teléfono es <b>${esc(r.dev_code)}</b>. Vence en 10 minutos.</div>` : ""}
        <form class="stack" id="cf" novalidate>
          <label>Código<input class="input codeinput" id="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required></label>
          <div id="cerr" role="alert"></div>
          <div class="row"><button type="button" class="btn ghost grow" id="back">Cambiar número</button><button class="btn grow">Confirmar</button></div>
          <button type="button" class="linkbtn" id="resend" disabled>Reenviar código (<span id="cd">${r.cooldown}</span> s)</button>
        </form>`;
      const code = box.querySelector("#code"); code.focus();
      let left = r.cooldown;
      const timer = setInterval(() => {
        left -= 1;
        const cd = box.querySelector("#cd");
        if (!cd) { clearInterval(timer); return; }
        if (left <= 0) { clearInterval(timer); const b = box.querySelector("#resend"); b.disabled = false; b.textContent = "Reenviar código"; }
        else cd.textContent = left;
      }, 1000);
      box.querySelector("#back").onclick = () => { clearInterval(timer); stepPhone(number); };
      box.querySelector("#resend").onclick = async () => {
        try { clearInterval(timer); stepCode(await api.post("/api/me/phone", { phone: number }), number); toast("Código reenviado"); }
        catch (ex) { toast(ex.message, true); }
      };
      box.querySelector("#cf").onsubmit = async (e) => {
        e.preventDefault();
        try {
          const res = await api.post("/api/me/phone/verify", { code: digits(code.value) });
          clearInterval(timer);
          if (state.user) state.user.payments = res.payments;
          toast("Celular confirmado");
          done(true);
        } catch (ex) { box.querySelector("#cerr").innerHTML = `<div class="notice bad">${esc(ex.message)}</div>`; code.select(); }
      };
    };
    stepPhone();
  });
}

// ------------------------------------------------------------------ 2) tarjeta del comprador (pago de prueba)
/** Pide la tarjeta y devuelve {brand,last4,exp_month,exp_year,holder} o null. */
export function cardDialog({ total, test = true, holder = "" }) {
  return new Promise((resolve) => {
    const ov = modal(`
      <h2>${icon("card")} Pagar ${esc(money(total))} con tarjeta</h2>
      <form class="stack" id="cardf" novalidate autocomplete="on">
        <label>Nombre del titular<input class="input" id="holder" autocomplete="cc-name" maxlength="80" value="${esc(holder)}" required></label>
        <label>Número de tarjeta
          <div class="cardnum"><input class="input" id="num" inputmode="numeric" autocomplete="cc-number" maxlength="23" placeholder="1234 5678 9012 3456" required><span id="brand" class="pill"></span></div></label>
        <div class="row">
          <label class="grow">Vencimiento<input class="input" id="exp" inputmode="numeric" autocomplete="cc-exp" maxlength="5" placeholder="MM/AA" required></label>
          <label class="grow">CVV<input class="input" id="cvv" inputmode="numeric" autocomplete="cc-csc" maxlength="4" placeholder="123" required></label>
        </div>
        <p class="muted small">${icon("lock")} El número completo y el CVV no se envían ni se guardan: ECO-GALLO solo conserva la marca y los últimos 4 dígitos. Tu dinero queda retenido hasta que confirmes que recibiste el artículo.</p>
        <div id="kerr" role="alert"></div>
        <div class="row"><button type="button" class="btn ghost grow" data-x>Cancelar</button><button class="btn grow" id="pay">${icon("lock")} Pagar ${esc(money(total))}</button></div>
      </form>`, { label: "Datos de la tarjeta" });
    const $ = (s) => ov.querySelector(s);
    const done = (v) => { ov.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => e.key === "Escape" && done(null);
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", (e) => e.target === ov && done(null));
    $("[data-x]").onclick = () => done(null);

    const paintBrand = () => {
      const n = digits($("#num").value).slice(0, 19), b = brandOf(n);
      $("#num").value = groups(n, b);
      $("#brand").textContent = n.length >= 2 ? BRAND_NAME[b] : "";
    };
    $("#num").addEventListener("input", paintBrand);
    $("#exp").addEventListener("input", (e) => {
      const d = digits(e.target.value).slice(0, 4);
      e.target.value = d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
    });
    $("#cvv").addEventListener("input", (e) => { e.target.value = digits(e.target.value).slice(0, 4); });
    $("#fill")?.addEventListener("click", () => {
      $("#num").value = "4242424242424242"; paintBrand();
      const y = (new Date().getFullYear() + 3) % 100;
      $("#exp").value = `12/${String(y).padStart(2, "0")}`; $("#cvv").value = "123";
      if (!$("#holder").value) $("#holder").value = "Titular ECO-GALLO";
    });
    (holder ? $("#num") : $("#holder")).focus();

    $("#cardf").onsubmit = (e) => {
      e.preventDefault();
      const err = (m) => { $("#kerr").innerHTML = `<div class="notice bad">${esc(m)}</div>`; };
      const name = $("#holder").value.trim();
      const num = digits($("#num").value), b = brandOf(num);
      const [mm, yy] = $("#exp").value.split("/").map((x) => parseInt(x, 10));
      const cvv = digits($("#cvv").value);
      if (name.length < 5) return err("Escribe el nombre del titular como aparece en la tarjeta.");
      if (num.length < 15 || num.length > 19) return err("El número de tarjeta debe tener 16 dígitos.");
      const now = new Date(), year = 2000 + (yy || 0);
      if (!(mm >= 1 && mm <= 12) || !yy || year < now.getFullYear() || (year === now.getFullYear() && mm < now.getMonth() + 1))
        return err("La tarjeta está vencida o la fecha no es válida (MM/AA).");
      if (cvv.length !== (b === "amex" ? 4 : 3)) return err(b === "amex" ? "El CVV de American Express tiene 4 dígitos." : "El CVV tiene 3 dígitos (atrás de la tarjeta).");
      const out = { brand: b, last4: num.slice(-4), exp_month: mm, exp_year: year, holder: name };
      $("#num").value = ""; $("#cvv").value = "";        // no dejar el número completo en la página
      done(out);
    };
  });
}

// ------------------------------------------------------------------ 3) cuenta del vendedor para recibir
export function payoutDialog(state) {
  return new Promise((resolve) => {
    const p = state.user?.payments?.payout;
    const ov = modal(`
      <h2>${icon("cash")} Cuenta para recibir tus pagos</h2>
      <p class="muted">Cuando un comprador te pague con tarjeta, el dinero se libera a esta cuenta en cuanto confirme que recibió el artículo.</p>
      <form class="stack" id="payf" novalidate>
        <div class="paychoice" role="radiogroup" aria-label="Tipo de cuenta">
          <label class="payopt"><input type="radio" name="k" value="tarjeta" ${p?.kind === "clabe" ? "" : "checked"}><span class="payic">${icon("card")}</span><span><b>Tarjeta de débito</b><span class="muted small">16 dígitos, al frente de tu tarjeta.</span></span></label>
          <label class="payopt"><input type="radio" name="k" value="clabe" ${p?.kind === "clabe" ? "checked" : ""}><span class="payic">${icon("cash")}</span><span><b>CLABE interbancaria</b><span class="muted small">18 dígitos, en tu app del banco.</span></span></label>
        </div>
        <label>Nombre del titular<input class="input" id="holder" maxlength="80" value="${esc(p?.holder || state.user?.name || "")}" required></label>
        <label><span id="numlbl">Número de tarjeta</span><input class="input" id="num" inputmode="numeric" maxlength="23" required></label>
        <p class="muted small">${icon("lock")} Solo guardamos el titular y los últimos 4 dígitos.</p>
        <div id="oerr" role="alert"></div>
        <div class="row"><button type="button" class="btn ghost grow" data-x>Cancelar</button><button class="btn grow">Guardar cuenta</button></div>
      </form>`, { label: "Cuenta para recibir pagos" });
    const $ = (s) => ov.querySelector(s);
    const done = (v) => { ov.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => e.key === "Escape" && done(false);
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", (e) => e.target === ov && done(false));
    $("[data-x]").onclick = () => done(false);
    const kind = () => ov.querySelector("input[name=k]:checked").value;
    const relabel = () => {
      $("#numlbl").textContent = kind() === "clabe" ? "CLABE (18 dígitos)" : "Número de tarjeta de débito";
      $("#num").placeholder = kind() === "clabe" ? "012 180 01234567891 2" : "1234 5678 9012 3456";
    };
    ov.querySelectorAll("input[name=k]").forEach((r) => (r.onchange = () => { $("#num").value = ""; relabel(); }));
    $("#num").addEventListener("input", (e) => {
      const d = digits(e.target.value).slice(0, kind() === "clabe" ? 18 : 19);
      e.target.value = kind() === "clabe" ? d : groups(d, brandOf(d));
    });
    relabel();
    $("#payf").onsubmit = async (e) => {
      e.preventDefault();
      const err = (m) => { $("#oerr").innerHTML = `<div class="notice bad">${esc(m)}</div>`; };
      const num = digits($("#num").value), holder = $("#holder").value.trim();
      if (holder.length < 5) return err("Escribe el nombre del titular.");
      if (kind() === "clabe" ? num.length !== 18 : num.length < 15) return err(kind() === "clabe" ? "La CLABE debe tener 18 dígitos." : "El número de tarjeta debe tener 16 dígitos.");
      try {
        const r = await api.put("/api/me/payout", { kind: kind(), last4: num.slice(-4), holder });
        $("#num").value = "";
        if (state.user) state.user.payments = r.payments;
        toast("Cuenta guardada");
        done(true);
      } catch (ex) { err(ex.message); }
    };
  });
}

/** Flujo completo de cobro: celular y cuenta. Devuelve true si quedó listo para recibir con tarjeta. */
export async function setupSelling(state) {
  if (!(await ensurePhone(state, { reason: "Para recibir pagos con tarjeta" }))) return false;
  if (state.user?.payments?.payout_ready) return true;
  return payoutDialog(state);
}

/** Antes de comprar con tarjeta: celular confirmado y, en modo de prueba, los datos de la tarjeta.
 *  Devuelve {card} (card puede ser null con Mercado Pago real) o null si la persona cancela. */
export async function prepareCardPayment(state, total) {
  if (!(await ensurePhone(state))) return null;
  const test = state.meta?.payment_provider === "simulado";
  if (!test) return { card: null };            // con Mercado Pago la tarjeta se captura en su página
  const card = await cardDialog({ total, test, holder: state.user?.name || "" });
  return card ? { card } : null;
}
