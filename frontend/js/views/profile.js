import { pager } from "../pagination.js";
import { api } from "../api.js";
import { esc, icon, money, avatar, badges, toast, timeAgo, TIPO, carreraOptions, bindCentro, pwField, wirePw, pwProblem } from "../ui.js";
import { state as appState } from "../main.js";
import { card } from "./home.js";
import { phoneDialog, payoutDialog } from "../payflow.js";

export async function render(root, ctx) {
  if (ctx.extra === "mine") return mine(root);
  if (ctx.extra === "impact") return impact(root);
  return profile(root, ctx);
}

async function mine(root, page = 1) {
  const { posts, pages } = await api.get(`/api/posts?mine=1&page=${page}`);
  const live = posts.filter((p) => ["pending", "active", "paused", "reserved"].includes(p.status));
  const done = posts.filter((p) => p.status === "sold");
  const st = await api.get("/api/posts/stats/mine").catch(() => null);
  const t = st?.totals;
  root.innerHTML = `
    <div class="row"><h1 class="grow">Mis publicaciones</h1><a class="btn accent" href="#/new">${icon("plus")} Publicar</a></div>
    ${t && t.posts ? `<div class="panelbox stack" style="margin-top:14px"><h3>${icon("chart")} Estadísticas de tus anuncios</h3>
      <div class="kpis">
        <div class="kpi"><div class="n">${t.views}</div><div class="muted small">Vistas</div></div>
        <div class="kpi"><div class="n">${t.contacts}</div><div class="muted small">Personas que te escribieron</div></div>
        <div class="kpi"><div class="n">${t.favorites}</div><div class="muted small">Guardados en favoritos</div></div>
        <div class="kpi"><div class="n">${t.reused}</div><div class="muted small">Entregados · ${money(t.earned_cents)}</div></div>
      </div>
      <details><summary class="small">Ver por publicación</summary>
        <div class="tablewrap"><table class="stats"><thead><tr><th>Publicación</th><th>Vistas</th><th>Contactos</th><th>Favoritos</th><th>Tasa de contacto</th></tr></thead>
        <tbody>${st.posts.map((r) => `<tr><td><a href="#/post/${r.id}">${esc(r.title)}</a></td><td>${r.views}</td><td>${r.contacts}</td><td>${r.favorites}</td><td>${Math.round(r.contact_rate * 100)}%</td></tr>`).join("")}</tbody></table></div>
      </details></div>` : ""}
    ${live.length ? `<div class="grid" style="margin-top:18px">${live.map(card).join("")}</div>`
      : `<div class="empty">${icon("list")}<h2>No tienes publicaciones activas</h2><p>Lo que ya no uses puede ayudar a otro estudiante.</p><a class="btn" href="#/new">Publicar mi primer artículo</a></div>`}
    ${done.length ? `<div class="sectionhd"><h2>Ya entregados</h2></div><div class="grid">${done.map(card).join("")}</div>` : ""}`;
  pager(root, page, pages, (next) => mine(root, next));
}

async function profile(root, { state, refresh }) {
  const ctxRefresh = refresh;
  const u = state.user;
  const w = await api.get("/api/wallet");
  const meta = state.meta;
  let connectStatus = null;

try {
  connectStatus = await api.get("/api/connect/status");
} catch {
  // Stripe todavía no está configurado o disponible.
}
  const stripePanel = `<div class="panelbox stack" id="connect-panel">
  <h3>Pagos y cuenta de vendedor</h3>
  ${connectStatus === null
  ? `<p class="muted small">Stripe no está configurado o disponible en este entorno.</p>`
  : connectStatus.simulated
    ? `<p class="muted small">Demostración o Stripe Test: no se envía dinero real y no necesitas RFC ni cuenta bancaria para esta prueba.</p><span class="pill">Modo de pruebas</span>${!connectStatus.connected ? '<button class="btn" id="connect-start">Preparar vendedor de prueba</button>' : ""}`
    : connectStatus.connected
      ? `<p class="muted small">Tu cuenta de vendedor está conectada y habilitada para recibir transferencias.</p>`
      : `<p class="muted small">Completa la verificación de Stripe para recibir pagos por tus ventas.</p>
         <button class="btn" id="connect-start">Configurar pagos con Stripe</button>`}
</div>`;
  root.innerHTML = `
  <div style="max-width:720px;margin:0 auto" class="stack">
    <div class="row"><div class="avbox">${avatar(u, "big")}<label class="avedit" title="Cambiar foto" aria-label="Cambiar foto de perfil">${icon("camera")}<input type="file" id="avfile" accept="image/jpeg,image/png,image/webp" hidden></label></div>
      <div class="grow"><h1 style="font-size:1.6rem">${esc(u.name)}</h1><div class="muted">${esc(u.email)}</div>${u.bio ? `<div class="small bio">${esc(u.bio)}</div>` : ""}
        ${u.avatar ? '<button class="linkbtn" id="avdel">Quitar foto</button>' : ""}
        ${u.kind === "egresado" && !(u.badges && u.badges.egresado) ? `<span class="pill">${icon("shield")} Egresado · en revisión</span>` : ""}
        <div class="insignias under">${badges(u)}</div></div></div>
    <div class="kpis"><div class="kpi"><div class="n">${money(w.available_cents)}</div><div class="muted small">Cobrado por ventas</div></div>
      <div class="kpi"><div class="n">${money(w.pending_cents)}</div><div class="muted small">Retenido, por liberar</div></div></div>
    ${cardPanel(u, meta)}
    ${meta.payment_provider === "stripe" ? stripePanel : ""}
    <div class="panelbox stack"><h3>Mis datos</h3>
      <form id="f" class="stack">
        <label class="field">Nombre completo<input class="input" name="name" value="${esc(u.name)}" required minlength="3" maxlength="80"></label>
        <label class="field">Carrera<select class="input" name="carrera" required>${carreraOptions(meta, u.carrera)}</select>
          <span class="hint">Centro: <b id="centro"></b></span></label>
        <label class="field">Biografía <span class="hint">(opcional · máx. 200)</span>
          <textarea class="input" name="bio" maxlength="200" rows="3" placeholder="Estudio Sistemas, vendo libros de 1er a 4to semestre…">${esc(u.bio || "")}</textarea></label>
        <button class="btn">Guardar cambios</button></form></div>
    <div class="panelbox stack"><h3>${u.has_password ? "Cambiar contraseña" : "Crear contraseña"}</h3>
      <p class="muted small">${u.has_password ? "Al cambiarla se cierran tus otras sesiones." : "Con una contraseña entras sin esperar códigos en tu correo."}</p>
      ${state.passwordResetAllowed ? '<p class="notice">Acceso reciente verificado por correo: puedes restablecer tu contraseña durante 10 minutos.</p>' : ""}
      <form id="pw" class="stack" novalidate>
        ${u.has_password && !state.passwordResetAllowed ? pwField("current_password", "Contraseña actual", { autocomplete: "current-password" }) : ""}
        ${pwField("new_password", "Nueva contraseña", { hint: `(mín. ${meta.password_min}, letras y un número)` })}
        ${pwField("new_password2", "Repite la nueva contraseña")}
        <div id="pwerr"></div>
        <button class="btn">${u.has_password ? "Cambiar contraseña" : "Guardar contraseña"}</button></form></div>
            <div class="panelbox stack" id="totp-panel">
      <h3>Autenticación en dos pasos</h3>
      <p class="muted small">
        Protege tu cuenta solicitando un código de tu aplicación
        autenticadora al iniciar sesión.
      </p>
      ${u.totp_enabled
        ? `<p class="pill ok">${icon("shield")} Autenticación activada</p>
           <form id="totp-disable" class="stack" novalidate>
             <label class="field">
               Código de tu autenticador
               <input class="input" name="code" inputmode="numeric"
                 autocomplete="one-time-code" maxlength="6" required>
             </label>
             ${u.has_password ? `
               <label class="field">
                 Contraseña actual
                 <input class="input" name="password" type="password"
                   autocomplete="current-password" required>
               </label>` : ""}
                          <button class="btn danger">Desactivar autenticación</button>
           </form>
           <div class="divider"></div>
           <h4>Recuperación de cuenta</h4>
           <p class="muted small">
             Si pierdes tus códigos de recuperación, puedes generar
             otros nuevos. Los anteriores dejarán de funcionar.
           </p>
           <form id="totp-regenerate" class="stack" novalidate>
             <label class="field">
               Código de tu autenticador
               <input class="input" name="code" inputmode="numeric"
                 autocomplete="one-time-code" maxlength="6" required>
             </label>
             ${u.has_password ? `
               <label class="field">
                 Contraseña actual
                 <input class="input" name="password" type="password"
                   autocomplete="current-password" required>
               </label>` : ""}
                          <button class="btn">Generar nuevos códigos</button>
           </form>`
        : `<p class="muted small">Actualmente está desactivada.</p>
           <button class="btn" id="totp-start">
             Activar autenticación en dos pasos
           </button>`
          }
      <div id="totp-message"></div>
    </div>
    <div class="panelbox stack"><h3>Historial de actividad</h3>
      <div class="tabs scroll" role="tablist" id="acttabs">${ACT_TABS.map(([k, l]) => `<button role="tab" data-k="${k}" aria-selected="${k === "todo"}">${l}</button>`).join("")}</div>
      <div id="actbox" aria-live="polite"></div></div>
    <div class="panelbox stack" id="notif-panel"><h3>App y avisos en este dispositivo</h3>
      <p class="muted small">Recibe un aviso del navegador cuando te escriban o haya novedades, aunque estés en otra pestaña.</p>
      <div id="notif-state"></div>
      <div id="install-box"></div></div>
    ${privacyPanel(u, state)}
    <div class="row wrap">${u.role === "admin" ? '<a class="btn" href="#/admin">Administración</a>' : ""}<a class="btn ghost" href="#/wishlist">${icon("heart")} Mi lista de deseos</a><a class="btn ghost" href="#/impact">${icon("leaf")} Impacto de la comunidad</a></div>
  </div>`;
  root.querySelector("#phone-btn")?.addEventListener("click", async () => {
    if (await phoneDialog(state)) ctxRefresh();
  });
  root.querySelector("#payout-btn")?.addEventListener("click", async () => {
    if (await payoutDialog(state)) ctxRefresh();
  });
  root.querySelector("#connect-start")?.addEventListener("click", async () => {
  const button = root.querySelector("#connect-start");
  button.disabled = true;

  try {
    const result = await api.post("/api/connect/onboarding", {});

    if (result.simulated) { ctxRefresh(); return; }
    if (!result.url) {
      throw new Error("Stripe no devolvió un enlace de registro.");
    }

    window.location.assign(result.url);
  } catch (err) {
    toast(err.message, true);
    button.disabled = false;
  }
});
  root.querySelector("#f").onsubmit = async (e) => {
    e.preventDefault();
    try { const r = await api.put("/api/me", Object.fromEntries(new FormData(e.target))); appState.user = r.user; toast("Perfil actualizado"); } catch (err) { toast(err.message, true); }
  };
  root.querySelector("#avfile").onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    if (file.size > 2 * 1024 * 1024) return toast("La foto debe pesar menos de 2 MB", true);
    const fd = new FormData(); fd.append("avatar", file);
    try { const r = await api.form("POST", "/api/me/avatar", fd); appState.user.avatar = r.avatar; toast("Foto actualizada"); ctxRefresh(); } catch (er) { toast(er.message, true); }
  };
  root.querySelector("#avdel")?.addEventListener("click", async () => { await api.del("/api/me/avatar"); toast("Foto quitada"); ctxRefresh(); });
  activity(root.querySelector("#acttabs"), root.querySelector("#actbox"));
    root.querySelector("#totp-start")?.addEventListener("click", async () => {
    const message = root.querySelector("#totp-message");

    try {
      const res = await api.post("/api/auth/totp/setup", {});

      message.innerHTML = `
        <div class="stack">
          <h4>Vincula tu aplicación autenticadora</h4>
          <p class="muted small">
            Agrega una cuenta manualmente en Google Authenticator,
            Microsoft Authenticator o una aplicación compatible.
          </p>
          <label class="field">
            Clave secreta
            <input class="input" value="${esc(res.secret)}" readonly>
          </label>
          <p class="hint">
            También puedes usar este enlace de configuración:
          </p>
          <textarea class="input" rows="3" readonly>${esc(res.provisioning_uri)}</textarea>
          <form id="totp-confirm" class="stack">
            <label class="field">
              Código de seis dígitos de tu aplicación
              <input class="input" name="code" inputmode="numeric"
                autocomplete="one-time-code" maxlength="6" required>
            </label>
            <button class="btn">Confirmar y activar</button>
          </form>
        </div>
      `;

      root.querySelector("#totp-confirm").onsubmit = async (e) => {
        e.preventDefault();
        const code = new FormData(e.target).get("code").trim();

        try {
          const result = await api.post("/api/auth/totp/confirm", { code });

          appState.user.totp_enabled = true;

          message.innerHTML = `
            <div class="stack">
              <h4>Autenticación activada</h4>
              <p class="muted small">
                Guarda estos códigos de recuperación. Cada uno
                puede utilizarse una sola vez. No volverán a mostrarse.
              </p>
              <div class="panelbox stack">
                ${result.recovery_codes.map(c => `<code>${esc(c)}</code>`).join("")}
              </div>
              <button class="btn ghost" id="totp-copy">Copiar códigos</button>
              <button class="btn" id="totp-finish">Terminé, guardar y continuar</button>
            </div>
          `;

          root.querySelector("#totp-copy").onclick = async () => {
            try {
              await navigator.clipboard.writeText(result.recovery_codes.join("\n"));
              toast("Códigos copiados");
            } catch {
              toast("No se pudieron copiar los códigos", true);
            }
          };

          root.querySelector("#totp-finish").onclick = () => ctxRefresh();

        } catch (err) {
          toast(err.message, true);
        }
      };

    } catch (err) {
      message.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    }
  });
    root.querySelector("#totp-disable")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fd = Object.fromEntries(new FormData(e.target));

    try {
      await api.post("/api/auth/totp/disable", fd);

      appState.user.totp_enabled = false;
      toast("Autenticación en dos pasos desactivada");
      ctxRefresh();
    } catch (err) {
      root.querySelector("#totp-message").innerHTML =
        `<p class="error">${esc(err.message)}</p>`;
    }
  });
    root.querySelector("#totp-regenerate")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fd = Object.fromEntries(new FormData(e.target));
    const message = root.querySelector("#totp-message");

    if (!confirm("Los códigos anteriores dejarán de funcionar. ¿Deseas generar 10 códigos nuevos?")) {
      return;
    }

    try {
      const result = await api.post("/api/auth/totp/recovery/regenerate", fd);

      message.innerHTML = `
        <div class="stack">
          <h4>Nuevos códigos de recuperación</h4>
          <p class="muted small">
            Los códigos anteriores ya no funcionan. Guarda estos 10 códigos;
            cada uno puede utilizarse una sola vez.
          </p>
          <div class="panelbox stack">
            ${result.recovery_codes.map(c => `<code>${esc(c)}</code>`).join("")}
          </div>
          <button class="btn ghost" id="totp-copy-new">Copiar códigos</button>
        </div>
      `;

      root.querySelector("#totp-copy-new").onclick = async () => {
        try {
          await navigator.clipboard.writeText(result.recovery_codes.join("\n"));
          toast("Códigos copiados");
        } catch {
          toast("No se pudieron copiar los códigos", true);
        }
      };
    } catch (err) {
      message.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    }
  });
  wirePrivacy(root, u);
  wireNotifications(root.querySelector("#notif-state"));
  wireInstall(root.querySelector("#install-box"));
  bindCentro(root.querySelector("#f [name=carrera]"), root.querySelector("#centro"), meta);
  wirePw(root);
  root.querySelector("#pw").onsubmit = async (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target));
    const err = (t) => (root.querySelector("#pwerr").innerHTML = t ? `<div class="error" role="alert">${esc(t)}</div>` : "");
    const bad = pwProblem(fd.new_password, meta.password_min);
    if (bad) return err(bad);
    if (fd.new_password !== fd.new_password2) return err("Las contraseñas no coinciden.");
    try {
      await api.put("/api/auth/password", { new_password: fd.new_password, current_password: fd.current_password });
      toast("Contraseña guardada"); appState.user.has_password = true; ctxRefresh();
    } catch (er) { err(er.message); }
  };
}

// ---------------------------------------------------------------- instalar como app (PWA)
async function wireInstall(box) {
  const { installPrompt } = await import("../main.js");
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const paint = (prompt) => {
    if (standalone) { box.innerHTML = `<span class="pill ok">${icon("check")} Estás usando la app instalada</span>`; return; }
    if (prompt) {
      box.innerHTML = `<button class="btn ghost" id="install">${icon("plus")} Instalar ECO-GALLO en este dispositivo</button>`;
      box.querySelector("#install").onclick = async () => { prompt.prompt(); await prompt.userChoice; paint(null); };
    } else {
      box.innerHTML = `<p class="muted small">${ios ? "En iPhone: toca Compartir y luego «Agregar a pantalla de inicio»."
        : "Para instalarla, abre el menú del navegador y elige «Instalar app» o «Agregar a la pantalla principal»."}</p>`;
    }
  };
  paint(installPrompt);
  document.addEventListener("eg:installable", async () => paint((await import("../main.js")).installPrompt), { once: true });
}

// ---------------------------------------------------------------- avisos del navegador
function wireNotifications(box) {
  const paint = () => {
    if (!("Notification" in window)) { box.innerHTML = '<p class="muted small">Este navegador no admite avisos.</p>'; return; }
    const p = Notification.permission;
    box.innerHTML = p === "granted" ? `<span class="pill ok">${icon("bell")} Avisos activados</span>`
      : p === "denied" ? '<p class="notice">Bloqueaste los avisos para este sitio. Puedes permitirlos desde la configuración del navegador (icono del candado junto a la dirección).</p>'
      : `<button class="btn ghost" id="notif-on">${icon("bell")} Activar avisos</button>`;
    box.querySelector("#notif-on")?.addEventListener("click", async () => { await Notification.requestPermission(); paint(); });
  };
  paint();
}

// ---------------------------------------------------------------- privacidad y derechos ARCO
function privacyPanel(u, state) {
  const accepted = u.terms_accepted_at
    ? `Aceptaste el aviso de privacidad y los términos (versión ${esc(u.terms_version)}) el ${new Date(u.terms_accepted_at * 1000).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" })}.`
    : "";
  const canProve = u.has_password || state.passwordResetAllowed;
  return `<div class="panelbox stack" id="privacy-panel"><h3>Privacidad y mis datos</h3>
    <p class="muted small">${accepted} Consulta el <a href="#/privacidad">aviso de privacidad</a> y los <a href="#/terminos">términos de uso</a>.</p>
    <div class="row wrap"><button class="btn ghost" id="export-data">${icon("note")} Descargar mis datos</button></div>
    <p class="muted small">Recibes un archivo con tu perfil, publicaciones, mensajes, compras, ventas, deseos y avisos (derecho de acceso). Para corregir tus datos usa «Mis datos» arriba.</p>
    <details class="danger-zone"><summary>Eliminar mi cuenta</summary>
      <div class="stack">
        <p class="small">Se borran tu nombre, correo, foto, biografía, publicaciones, fotos, deseos y avisos, y el texto de los mensajes que enviaste. Solo conservamos montos y estados de operaciones pasadas sin datos que te identifiquen. <b>No se puede deshacer.</b></p>
        ${u.role === "admin" ? '<p class="notice">Las cuentas de administración no pueden darse de baja solas. Pide que te retiren el rol primero.</p>'
          : !canProve ? '<p class="notice">Por seguridad, cierra sesión y vuelve a entrar con un código a tu correo. Después tendrás 10 minutos para eliminar tu cuenta.</p>'
          : `<form id="del-account" class="stack" novalidate>
          ${u.has_password ? pwField("password", "Tu contraseña", { autocomplete: "current-password" }) : '<p class="muted small">Entraste con un código a tu correo hace poco: no necesitas contraseña.</p>'}
          ${u.totp_enabled ? '<label class="field">Código de tu autenticador<input class="input" name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required></label>' : ""}
          <label class="field"><span>Escribe <b>ELIMINAR</b> para confirmar</span><input class="input" name="confirm" autocomplete="off" required></label>
          <div id="delerr"></div>
          <button class="btn danger">Eliminar mi cuenta definitivamente</button></form>`}
      </div></details></div>`;
}

function wirePrivacy(root, u) {
  root.querySelector("#export-data").onclick = async (e) => {
    const btn = e.currentTarget; btn.disabled = true;
    try {
      const res = await fetch("/api/me/export", { credentials: "same-origin" });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).message || "No se pudo generar el archivo.");
      const url = URL.createObjectURL(await res.blob());
      const a = Object.assign(document.createElement("a"), { href: url, download: "mis-datos-ecogallo.json" });
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("Descargamos tus datos");
    } catch (err) { toast(err.message, true); }
    btn.disabled = false;
  };
  const f = root.querySelector("#del-account");
  if (!f) return;
  f.onsubmit = async (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(f));
    const err = (t) => (root.querySelector("#delerr").innerHTML = `<div class="error" role="alert">${esc(t)}</div>`);
    if (fd.confirm.trim().toUpperCase() !== "ELIMINAR") return err("Escribe ELIMINAR para confirmar.");
    if (u.has_password && !fd.password) return err("Escribe tu contraseña.");
    if (!confirm("¿Seguro? Tu cuenta y tus datos se eliminarán y no podrás recuperarlos.")) return;
    try {
      await api.del("/api/me", fd);
      appState.user = null;
      toast("Tu cuenta fue eliminada");
      location.hash = "#/"; location.reload();
    } catch (er) { err(er.message); }
  };
}

async function impact(root) {
  const draw = (s) => {
    const cats = Object.entries(s.posts_by_category).sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...cats.map((c) => c[1]));
    const mmax = Math.max(1, ...s.monthly.map((m) => m.items));
    const tipo = s.reused_by_tipo || {};
    root.innerHTML = `
  <div class="stack">
    <div><h1>Impacto de la comunidad</h1><p class="muted">Lo que la UAA ha reutilizado en lugar de comprar nuevo o tirar. <span class="small" id="upd">Actualizado ${new Date(s.updated_at * 1000).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", second: "2-digit" })} · se actualiza solo</span></p></div>
    <div class="kpis">
      <div class="kpi"><div class="n">${money(s.savings_cents)}</div><div class="muted small">Ahorro económico estimado</div></div>
      <div class="kpi"><div class="n">${s.co2_kg} kg</div><div class="muted small">CO₂e evitado (estimado)</div></div>
      <div class="kpi"><div class="n">${s.reused_items}</div><div class="muted small">Artículos reutilizados</div></div>
      <div class="kpi"><div class="n">${s.users}</div><div class="muted small">Personas registradas</div></div>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="n">${tipo.venta || 0}</div><div class="muted small">Vendidos</div></div>
      <div class="kpi"><div class="n">${tipo.trueque || 0}</div><div class="muted small">Intercambiados</div></div>
      <div class="kpi"><div class="n">${tipo.donacion || 0}</div><div class="muted small">Donados</div></div>
      <div class="kpi"><div class="n">${s.active_posts}</div><div class="muted small">Publicaciones activas</div></div>
    </div>
    <div class="panelbox stack"><h3>Reutilización por mes</h3>
      <div class="bars">${s.monthly.length ? s.monthly.map((m) => `<div class="bar wide"><span>${esc(m.month)}</span><i style="width:${(m.items / mmax) * 100}%"></i><b>${m.items} · ${money(m.savings_cents)}</b></div>`).join("") : '<p class="muted">Aún no hay artículos reutilizados.</p>'}</div></div>
    <div class="panelbox stack"><h3>Publicaciones por categoría</h3>
      <div class="bars">${cats.length ? cats.map(([c, n]) => `<div class="bar"><span>${esc(c)}</span><i style="width:${(n / max) * 100}%"></i><b>${n}</b></div>`).join("") : '<p class="muted">Aún no hay datos.</p>'}</div></div>
    <p class="muted small">Cómo se calcula: ahorro = precio nuevo − precio pagado (las donaciones y trueques cuentan como $0 pagados). ${Math.round(s.declared_share * 100)}% del ahorro usa el precio nuevo que declararon los vendedores; el resto, un precio de referencia por categoría. ${esc(s.co2_note)} Dinero que cambió de manos por ventas completadas: ${money(s.money_cents)}.</p>
  </div>`;
  };
  draw(await api.get("/api/impact"));
  // «Tiempo real»: se vuelve a consultar cada 15 s mientras la página está abierta y visible.
  const timer = setInterval(async () => {
    if (!document.body.contains(root) || location.hash !== "#/impact") return clearInterval(timer);
    if (document.hidden) return;
    try { draw(await api.get("/api/impact")); } catch { /* reintenta */ }
  }, 15000);
}

// ---------------------------------------------------------------- historial de actividad (paginado)
const ACT_TABS = [["todo", "Todo"], ["publicaciones", "Publicaciones"], ["compras", "Compras"], ["ventas", "Ventas"], ["mensajes", "Mensajes"]];
const ORDER_LABEL = { HELD: "Pago retenido", DELIVERED: "Entregado, esperando confirmación", RELEASED: "Pago liberado", DISPUTED: "En disputa", REFUNDED: "Reembolsado" };
const POST_LABEL = { pending: "En revisión", active: "Activa", paused: "Pausada", reserved: "Reservada", sold: "Entregada", removed: "Eliminada" };
const ACT = {
  publicacion: ["list", "Publicaste", (i) => POST_LABEL[i.detail] || i.detail, (i) => (i.amount ? money(i.amount) : "")],
  compra: ["bag", "Compraste", (i) => ORDER_LABEL[i.detail] || i.detail, (i) => money(i.amount)],
  venta: ["box", "Vendiste", (i) => ORDER_LABEL[i.detail] || i.detail, (i) => money(i.amount)],
  mensaje_enviado: ["send", "Enviaste un mensaje", (i) => `Sobre «${i.detail || "publicación"}»`, () => ""],
  mensaje_recibido: ["chat", "Recibiste un mensaje", (i) => `Sobre «${i.detail || "publicación"}»`, () => ""],
};

function activity(tabs, box) {
  let kind = "todo", page = 1;
  const load = async () => {
    box.innerHTML = '<p class="muted">Cargando…</p>';
    try {
      const d = await api.get(`/api/activity?kind=${kind}&page=${page}`);
      page = d.page;
      if (!d.items.length) { box.innerHTML = '<p class="muted">Todavía no hay movimientos en esta sección.</p>'; return; }
      box.innerHTML = `<div class="actlist">${d.items.map((i) => {
        const [ic, verb, sub, amt] = ACT[i.kind];
        const main = i.kind.startsWith("mensaje") ? `“${esc(i.title)}”` : esc(i.title);
        return `<a class="act" href="${esc(i.link)}"><span class="ico">${icon(ic)}</span>
          <div class="grow"><div class="tt">${main}</div><div class="muted small">${verb} · ${esc(sub(i))}${amt(i) ? " · " + amt(i) : ""} · ${timeAgo(i.ts)}</div></div></a>`;
      }).join("")}</div>
      <div class="pager"><button class="btn ghost sm" id="pp" ${page <= 1 ? "disabled" : ""}>← Anterior</button>
        <span class="muted small">Página ${d.page} de ${d.pages} · ${d.total} movimiento(s)</span>
        <button class="btn ghost sm" id="pn" ${page >= d.pages ? "disabled" : ""}>Siguiente →</button></div>`;
      box.querySelector("#pp").onclick = () => { page--; load(); };
      box.querySelector("#pn").onclick = () => { page++; load(); };
    } catch (e) { box.innerHTML = `<div class="error" role="alert">${esc(e.message)}</div>`; }
  };
  tabs.querySelectorAll("button").forEach((b) => (b.onclick = () => {
    kind = b.dataset.k; page = 1;
    tabs.querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", x === b));
    load();
  }));
  load();
}


const KIND = { tarjeta: "Tarjeta de débito", clabe: "CLABE" };

function cardPanel(u, meta) {
  const p = u.payments || {};
  return `<div class="panelbox stack" id="cardpay-panel">
    <h3>${icon("card")} Pagos con tarjeta</h3>
    <p class="muted small">Para pagar o recibir pagos con tarjeta necesitas tu celular confirmado por SMS. Si un artículo no se entrega, la otra persona de la compra y administración podrán localizarte. Para pagar en efectivo no hace falta.</p>
    <div class="payrow"><span class="payic">${icon("chat")}</span>
      <div class="grow"><b>Celular</b><div class="muted small">${p.phone_verified ? `+52 ${esc(p.phone)} · <span class="oktxt">${icon("check")} Confirmado</span>` : "Sin confirmar"}</div></div>
      <button class="btn ${p.phone_verified ? "ghost" : ""}" id="phone-btn">${p.phone_verified ? "Cambiar" : "Confirmar celular"}</button></div>
    <div class="payrow"><span class="payic">${icon("cash")}</span>
      <div class="grow"><b>Cuenta para recibir tus ventas</b><div class="muted small">${p.payout ? `${esc(KIND[p.payout.kind] || "Cuenta")} ••${esc(p.payout.last4)} · ${esc(p.payout.holder)}` : p.phone_verified ? "Agrégala para que te puedan pagar con tarjeta." : "Primero confirma tu celular."}</div></div>
      <button class="btn ${p.payout ? "ghost" : ""}" id="payout-btn" ${p.phone_verified ? "" : "disabled"}>${p.payout ? "Cambiar" : "Agregar cuenta"}</button></div>
    ${p.payout_ready ? `<p class="small oktxt">${icon("check")} Listo: puedes pagar y recibir pagos con tarjeta.</p>` : p.card_ready ? `<p class="small">Ya puedes pagar con tarjeta. Para que te paguen con tarjeta, agrega tu cuenta.</p>` : ""}
  </div>`;
}
