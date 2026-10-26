import { api } from "../api.js";
import { esc, icon, toast, carreraOptions, bindCentro, pwField, wirePw, pwProblem } from "../ui.js";
import { state } from "../main.js";

const LEAVES = `<svg class="leaves" viewBox="0 0 400 400" aria-hidden="true">
  <g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
    <path d="M60 360C60 220 140 120 300 100c0 150-80 250-240 260z"/><path d="M60 360 220 200"/>
    <path d="M250 380c-10-90 20-170 120-210 10 100-30 180-120 210z"/><path d="M250 380 340 240"/>
  </g></svg>`;

const HERO = `
  <div class="hero">
    ${LEAVES}
    <img src="/img/logo.svg" alt="ECO-GALLO UAA">
    <h1>Lo que ya usaste, le sirve a otro gallo.</h1>
    <p>Compra, vende, intercambia o regala libros, batas y material de laboratorio entre la comunidad de la UAA.</p>
    <ul class="perks">
      <li>${icon("leaf")} Menos residuos, menos gasto</li>
      <li>${icon("shield")} Solo comunidad UAA verificada</li>
      <li>${icon("lock")} Pago retenido hasta que recibes</li>
    </ul>
  </div>`;

const shellLogin = (root, inner) => {
  root.innerHTML = `<div class="login">${HERO}<div class="panel"><div id="box">${inner || ""}</div></div></div>`;
  return () => root.querySelector("#box");
};
const errBox = (m) => (m ? `<div class="error" role="alert">${esc(m)}</div>` : "");

export function render(root, { onDone }) {
  let email = "", cooldown = 0, timer = null;
  const box = shellLogin(root);
  const meta = () => state.meta;

  // ------------------------------------------------------------ correo + contraseña
  function stepPassword(msg = "") {
    clearInterval(timer);
    box().innerHTML = `
      <h2>Inicia sesión</h2>
      <form id="f" class="stack" novalidate>
        <label class="field">Correo
          <input class="input" name="email" type="email" inputmode="email" autocomplete="username" placeholder="al350114@edu.uaa.mx" value="${esc(email)}" required autofocus>
        </label>
        ${pwField("password", "Contraseña", { autocomplete: "current-password" })}
        ${errBox(msg)}
        <button class="btn block">Entrar</button>
        <button type="button" class="linkbtn" id="usecode">¿Olvidaste tu contraseña o aún no tienes una? Entra con un código</button>
      </form>
      <div class="or"><span>¿Primera vez en ECO-GALLO?</span></div>
      <div class="stack">
        <button class="btn ghost block" id="newstudent">${icon("user")} Crear cuenta con mi correo @edu.uaa.mx</button>
        <button class="btn ghost block" id="newalumni">${icon("shield")} Soy egresado de la UAA</button>
      </div>`;
    wirePw(box());
    box().querySelector("#f").onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      email = fd.email.trim().toLowerCase();
      if (!email || !fd.password) return stepPassword("Escribe tu correo y tu contraseña.");
      const btn = e.submitter; btn.disabled = true; btn.textContent = "Entrando…";
      try { const res = await api.post("/api/auth/login", { email, password: fd.password }); state.user = res.user; onDone(); }
      catch (err) {
        if (err.data?.needs_email_verification) return sendCode(err.message);
        stepPassword(err.message);
      }
    };
    box().querySelector("#usecode").onclick = () => { email = box().querySelector("[name=email]").value.trim().toLowerCase(); stepEmail(); };
    box().querySelector("#newstudent").onclick = () => stepEmail("", true);
    box().querySelector("#newalumni").onclick = () => stepAlumni();
  }

  // ------------------------------------------------------------ código por correo
  function stepEmail(msg = "", creating = false) {
    box().innerHTML = `
      <h2>${creating ? "Crea tu cuenta" : "Entra con un código"}</h2>
      <form id="f" class="stack" novalidate>
        <label class="field">${creating ? "Tu correo institucional (@edu.uaa.mx)" : "Correo"}
          <input class="input" id="email" type="email" inputmode="email" autocomplete="email" placeholder="al350114@edu.uaa.mx" value="${esc(email)}" required autofocus>
        </label>
        ${errBox(msg)}
        <button class="btn block">Enviarme un código</button>
        <p class="muted small">${creating
          ? "Te mandamos un código de 6 dígitos para confirmar que el correo es tuyo. Después podrás crear una contraseña para no pedir códigos cada vez."
          : "Sirve con tu correo @edu.uaa.mx o con el correo con el que te registraste como egresado."}</p>
        <button type="button" class="linkbtn" id="back">← Volver a iniciar sesión con contraseña</button>
      </form>`;
    box().querySelector("#back").onclick = () => stepPassword();
    box().querySelector("#f").onsubmit = async (e) => {
      e.preventDefault();
      email = box().querySelector("#email").value.trim().toLowerCase();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return stepEmail("Escribe un correo válido.", creating);
      if (creating && !/^[a-z0-9][a-z0-9._%+-]*@edu\.uaa\.mx$/.test(email)) return stepEmail("Para crear la cuenta de estudiante usa tu correo @edu.uaa.mx. Si ya egresaste, usa «Soy egresado».", creating);
      const btn = e.submitter; btn.disabled = true; btn.textContent = "Enviando…";
      await sendCode("", creating);
    };
  }

  async function sendCode(msg = "", creating = false) {
    try { const r = await api.post("/api/auth/request-code", { email }); stepCode(r, msg); }
    catch (err) { if (err.status === 429 && err.data.retry_after) stepCode({ cooldown: err.data.retry_after, ttl: 600 }); else stepEmail(err.message, creating); }
  }

  function stepCode(r, msg = "") {
    cooldown = r.cooldown || 45;
    clearInterval(timer);
    box().innerHTML = `
      <h2>Revisa tu correo</h2>
      <p class="muted">Enviamos un código a <b>${esc(email)}</b>. Vence en ${Math.round((r.ttl || 600) / 60)} minutos.</p>
      ${r.dev_code ? `<div class="devcode">Modo de pruebas (sin SMTP): tu código es <b>${esc(r.dev_code)}</b></div>` : ""}
      <form id="f" class="stack" novalidate>
        <div class="codebox" id="cells" aria-label="Código de 6 dígitos">
          ${[0, 1, 2, 3, 4, 5].map((i) => `<input inputmode="numeric" autocomplete="${i ? "off" : "one-time-code"}" maxlength="1" aria-label="Dígito ${i + 1}">`).join("")}
        </div>
        ${errBox(msg)}
        <button class="btn block" id="go" disabled>Entrar</button>
      </form>
      <div class="row wrap"><button class="btn ghost sm" id="resend" disabled></button><button class="btn ghost sm" id="back">Cambiar correo</button></div>`;
    const cells = [...box().querySelectorAll("#cells input")];
    const go = box().querySelector("#go");
    const value = () => cells.map((c) => c.value).join("");
    const sync = () => (go.disabled = value().length !== 6);
    cells[0].focus();
    cells.forEach((c, i) => {
      c.addEventListener("input", () => {
        c.value = c.value.replace(/\D/g, "").slice(-1);
        if (c.value && cells[i + 1]) cells[i + 1].focus();
        sync();
        if (value().length === 6) box().querySelector("#f").requestSubmit();
      });
      c.addEventListener("keydown", (e) => { if (e.key === "Backspace" && !c.value && cells[i - 1]) cells[i - 1].focus(); });
      c.addEventListener("paste", (e) => {
        const d = (e.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 6);
        if (!d) return;
        e.preventDefault(); d.split("").forEach((ch, k) => (cells[k].value = ch)); cells[Math.min(d.length, 5)].focus(); sync();
        if (d.length === 6) box().querySelector("#f").requestSubmit();
      });
    });
    box().querySelector("#f").onsubmit = async (e) => {
      e.preventDefault();
      if (value().length !== 6) return;
      go.disabled = true; go.textContent = "Verificando…";
      try {
        const res = await api.post("/api/auth/verify", { email, code: value() });
        clearInterval(timer);
        state.user = res.user;
        if (res.needs_profile) renderProfile(root, { onDone }); else onDone();
      } catch (err) { stepCode({ ...r, cooldown }, err.message); }
    };
    const resend = box().querySelector("#resend");
    const tick = () => {
      resend.disabled = cooldown > 0;
      resend.textContent = cooldown > 0 ? `Reenviar en ${cooldown} s` : "Reenviar código";
      if (cooldown > 0) cooldown--; else clearInterval(timer);
    };
    tick(); timer = setInterval(tick, 1000);
    resend.onclick = async () => {
      resend.disabled = true;
      try { stepCode(await api.post("/api/auth/request-code", { email })); } catch (err) { stepCode({ ...r, cooldown: err.data?.retry_after || 30 }, err.message); }
    };
    box().querySelector("#back").onclick = () => { clearInterval(timer); stepPassword(); };
  }

  // ------------------------------------------------------------ registro de egresados
  function stepAlumni(msg = "", keep = {}) {
    const m = meta();
    box().innerHTML = `
      <h2>Registro de egresados</h2>
      <p class="muted">Como ya no usas tu correo institucional, confirmamos que estudiaste en la UAA con tu <b>kárdex</b> o tu <b>título</b>. Un administrador lo revisa antes de darte acceso.</p>
      <form id="f" class="stack" novalidate>
        <label class="field">Nombre completo<input class="input" name="name" required minlength="3" maxlength="80" autocomplete="name" value="${esc(keep.name || "")}"></label>
        <label class="field">Correo (puede ser personal)<input class="input" name="email" type="email" autocomplete="email" required value="${esc(keep.email || "")}"></label>
        <label class="field">Carrera que estudiaste<select class="input" name="carrera" required>${carreraOptions(m, keep.carrera || "")}</select>
          <span class="hint">Centro: <b id="centro"></b></span></label>
        <div class="field">Documento que subes
          <div class="seg" role="radiogroup" aria-label="Tipo de documento">
            ${Object.entries(m.doc_types).map(([k, v], i) => `<label><input type="radio" name="doc_type" value="${esc(k)}" ${(keep.doc_type ? keep.doc_type === k : i === 0) ? "checked" : ""}><span>${esc(v)}</span></label>`).join("")}
          </div>
        </div>
        <label class="field">Captura o PDF <span class="hint">(JPG, PNG, WebP o PDF · máx. 6 MB)</span>
          <input class="input file" type="file" name="document" accept="image/jpeg,image/png,image/webp,application/pdf" required></label>
        ${pwField("password", "Crea una contraseña", { hint: `(mín. ${m.password_min}, con letras y un número)` })}
        ${pwField("password2", "Repite la contraseña")}
        ${errBox(msg)}
        <button class="btn block">Enviar para revisión</button>
        <p class="muted small">${icon("lock")} Tu documento solo lo ve el equipo de administración y se borra en cuanto se resuelve la solicitud.</p>
        <button type="button" class="linkbtn" id="back">← Volver</button>
      </form>`;
    wirePw(box());
    const f = box().querySelector("#f");
    bindCentro(f.carrera, box().querySelector("#centro"), m);
    box().querySelector("#back").onclick = () => stepPassword();
    f.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(f);
      const keepNow = Object.fromEntries([...fd].filter(([k, v]) => typeof v === "string" && !k.startsWith("password")));
      const back = (t) => stepAlumni(t, keepNow);
      if (!fd.get("carrera")) return back("Elige tu carrera de la lista.");
      const file = fd.get("document");
      if (!file || !file.size) return back("Sube una captura o PDF de tu kárdex o título.");
      if (file.size > 6 * 1024 * 1024) return back("El documento debe pesar menos de 6 MB.");
      const pw = fd.get("password"); const bad = pwProblem(pw, m.password_min);
      if (bad) return back(bad);
      if (pw !== fd.get("password2")) return back("Las contraseñas no coinciden.");
      fd.delete("password2");
      email = String(fd.get("email")).trim().toLowerCase();
      const btn = e.submitter; btn.disabled = true; btn.textContent = "Enviando…";
      try { const r = await api.form("POST", "/api/auth/egresado", fd); stepCode(r); toast("Documento enviado. Falta confirmar tu correo."); }
      catch (err) { back(err.message); }
    };
  }

  stepPassword();
}

// ------------------------------------------------------------ primer perfil (estudiantes)
export function renderProfile(root, { onDone }) {
  const m = state.meta;
  const box = shellLogin(root, `
    <h2>Un último paso: ¿quién eres?</h2>
    <p class="muted">Así te verán quienes compren o intercambien contigo.</p>
    <form id="f" class="stack" novalidate>
      <label class="field">Nombre completo<input class="input" name="name" required minlength="3" maxlength="80" autocomplete="name" autofocus></label>
      <label class="field">Carrera<select class="input" name="carrera" required>${carreraOptions(m)}</select>
        <span class="hint">Centro: <b id="centro"></b></span></label>
      <div class="pwbox stack">
        <div><b>Crea una contraseña</b> <span class="hint">(opcional)</span>
          <p class="muted small">Con contraseña entras directo, sin esperar un código en tu correo.</p></div>
        ${pwField("password", "Contraseña", { hint: `(mín. ${m.password_min}, letras y un número)` })}
        ${pwField("password2", "Repite la contraseña")}
      </div>
      <div id="err"></div>
      <button class="btn block">Empezar</button>
    </form>`);
  wirePw(box());
  const f = root.querySelector("#f");
  bindCentro(f.carrera, root.querySelector("#centro"), m);
  const show = (t) => (root.querySelector("#err").innerHTML = errBox(t));
  f.onsubmit = async (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(f));
    if (!fd.carrera) return show("Elige tu carrera de la lista.");
    if (fd.password || fd.password2) {
      const bad = pwProblem(fd.password, m.password_min);
      if (bad) return show(bad);
      if (fd.password !== fd.password2) return show("Las contraseñas no coinciden.");
    }
    try {
      const r = await api.put("/api/me", { name: fd.name, carrera: fd.carrera });
      state.user = r.user;
      if (fd.password) {
        try { await api.put("/api/auth/password", { new_password: fd.password }); state.user.has_password = true; toast("Contraseña creada. La próxima vez entra sin código."); }
        catch (err) { toast("Tu perfil se guardó, pero la contraseña no: " + err.message, true); }
      }
      onDone();
    } catch (err) { show(err.message); }
  };
}

// ------------------------------------------------------------ egresado esperando revisión
export function renderPending(root, { state: st, onLogout, refresh }) {
  const u = st.user, v = st.verification;
  const m = st.meta;
  const rejected = u.verif_status === "rejected";
  const box = shellLogin(root, `
    <div class="statuscard ${rejected ? "bad" : ""}">
      <div class="big">${icon(rejected ? "alert" : "shield")}</div>
      <h2>${rejected ? "No pudimos verificar tu documento" : "Estamos revisando tu documento"}</h2>
      <p class="muted">${rejected
        ? `Motivo: <b>${esc(v?.note || "el documento no era legible o no coincide con tus datos")}</b>. Sube otro y lo revisamos de nuevo.`
        : `Hola, ${esc(u.name.split(" ")[0])}. Un administrador está comprobando tu ${esc(m.doc_types[v?.doc_type] || "documento").toLowerCase()}. Normalmente tarda poco; vuelve a entrar o toca «Revisar estado».`}</p>
    </div>
    ${rejected ? `
    <form id="f" class="stack" novalidate>
      <div class="seg" role="radiogroup" aria-label="Tipo de documento">
        ${Object.entries(m.doc_types).map(([k, val], i) => `<label><input type="radio" name="doc_type" value="${esc(k)}" ${i === 0 ? "checked" : ""}><span>${esc(val)}</span></label>`).join("")}
      </div>
      <input class="input file" type="file" name="document" accept="image/jpeg,image/png,image/webp,application/pdf" required aria-label="Documento">
      <div id="err"></div>
      <button class="btn block">Enviar otro documento</button>
    </form>` : `<button class="btn block" id="refresh">Revisar estado</button>`}
    <button class="btn ghost block" id="out">Cerrar sesión</button>`);
  root.querySelector("#out").onclick = onLogout;
  const r = root.querySelector("#refresh"); if (r) r.onclick = refresh;
  const f = root.querySelector("#f");
  if (f) f.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(f);
    const file = fd.get("document");
    if (!file || !file.size) return (root.querySelector("#err").innerHTML = errBox("Elige un archivo."));
    try { await api.form("POST", "/api/auth/egresado/document", fd); toast("Documento enviado para revisión"); refresh(); }
    catch (err) { root.querySelector("#err").innerHTML = errBox(err.message); }
  };
}
