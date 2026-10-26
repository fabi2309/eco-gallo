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
