import { api } from "../api.js";
import { esc, icon, money, avatar, toast, timeAgo, TIPO, carreraOptions, bindCentro, pwField, wirePw, pwProblem } from "../ui.js";
import { state as appState } from "../main.js";
import { card } from "./home.js";

export async function render(root, ctx) {
  if (ctx.extra === "mine") return mine(root);
  if (ctx.extra === "impact") return impact(root);
  return profile(root, ctx);
}

async function mine(root) {
  const { posts } = await api.get("/api/posts?mine=1");
  const live = posts.filter((p) => ["active", "paused", "reserved"].includes(p.status));
  const done = posts.filter((p) => p.status === "sold");
  root.innerHTML = `
    <div class="row"><h1 class="grow">Mis publicaciones</h1><a class="btn accent" href="#/new">${icon("plus")} Publicar</a></div>
    ${live.length ? `<div class="grid" style="margin-top:18px">${live.map(card).join("")}</div>`
      : `<div class="empty">${icon("list")}<h2>No tienes publicaciones activas</h2><p>Lo que ya no uses puede ayudar a otro estudiante.</p><a class="btn" href="#/new">Publicar mi primer artículo</a></div>`}
    ${done.length ? `<div class="sectionhd"><h2>Ya entregados</h2></div><div class="grid">${done.map(card).join("")}</div>` : ""}`;
}

async function profile(root, { state, refresh }) {
  const ctxRefresh = refresh;
  const u = state.user;
  const [orders, w] = await Promise.all([api.get("/api/orders"), api.get("/api/wallet")]);
  const meta = state.meta;
  root.innerHTML = `
  <div style="max-width:720px;margin:0 auto" class="stack">
    <div class="row"><div class="avbox">${avatar(u, "big")}<label class="avedit" title="Cambiar foto" aria-label="Cambiar foto de perfil">${icon("camera")}<input type="file" id="avfile" accept="image/jpeg,image/png,image/webp" hidden></label></div>
      <div class="grow"><h1 style="font-size:1.6rem">${esc(u.name)}</h1><div class="muted">${esc(u.email)}</div>${u.bio ? `<div class="small bio">${esc(u.bio)}</div>` : ""}
        ${u.avatar ? '<button class="linkbtn" id="avdel">Quitar foto</button>' : ""}
        ${u.kind === "egresado" ? `<span class="pill ok">${icon("shield")} Egresado verificado</span>` : ""}</div></div>
    <div class="kpis"><div class="kpi"><div class="n">${money(w.available_cents)}</div><div class="muted small">Cobrado por ventas</div></div>
      <div class="kpi"><div class="n">${money(w.pending_cents)}</div><div class="muted small">Retenido, por liberar</div></div></div>
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
      <form id="pw" class="stack" novalidate>
        ${u.has_password ? pwField("current_password", "Contraseña actual", { autocomplete: "current-password" }) : ""}
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
      ${orders.orders.length ? `<div class="log">${orders.orders.slice(0, 8).map((o) => `<div><a href="#/order/${o.id}">${esc(o.post_title)}</a> · ${o.role === "buyer" ? "compra" : "venta"} · ${money(o.amount_cents)}<br><span class="muted">${esc(o.status)} · ${timeAgo(o.updated_at)}</span></div>`).join("")}</div>` : '<p class="muted">Todavía no hay movimientos.</p>'}</div>
    <div class="row wrap"><a class="btn ghost" href="#/wishlist">${icon("heart")} Mi lista de deseos</a><a class="btn ghost" href="#/impact">${icon("leaf")} Impacto de la comunidad</a></div>
  </div>`;
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

async function impact(root) {
  const s = await api.get("/api/impact");
  const cats = Object.entries(s.posts_by_category).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...cats.map((c) => c[1]));
  root.innerHTML = `
  <div class="stack">
    <div><h1>Impacto de la comunidad</h1><p class="muted">Lo que la UAA ha reutilizado en lugar de comprar nuevo o tirar.</p></div>
    <div class="kpis">
      <div class="kpi"><div class="n">${s.reused_items}</div><div class="muted small">Artículos reutilizados</div></div>
      <div class="kpi"><div class="n">${s.co2_kg} kg</div><div class="muted small">CO₂e evitado (estimado)</div></div>
      <div class="kpi"><div class="n">${s.active_posts}</div><div class="muted small">Publicaciones activas</div></div>
      <div class="kpi"><div class="n">${s.users}</div><div class="muted small">Personas registradas</div></div>
    </div>
    <div class="panelbox stack"><h3>Publicaciones por categoría</h3>
      <div class="bars">${cats.length ? cats.map(([c, n]) => `<div class="bar"><span>${esc(c)}</span><i style="width:${(n / max) * 100}%"></i><b>${n}</b></div>`).join("") : '<p class="muted">Aún no hay datos.</p>'}</div></div>
    <p class="muted small">${esc(s.co2_note)} Dinero que cambió de manos por ventas completadas: ${money(s.money_cents)}.</p>
  </div>`;
}
