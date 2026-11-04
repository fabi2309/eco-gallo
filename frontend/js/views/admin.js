import { api } from "../api.js";
import { esc, icon, money, timeAgo, ask, toast } from "../ui.js";

export async function render(root, { state, refresh, go }) {
  if (state.user.role !== "admin") return go("#/");
  
  const [d, bks, metrics, pending] = await Promise.all([
    api.get("/api/admin/overview"),
    api.get("/api/admin/backups").catch(() => ({ ok: false, backups: [], config: {} })),
    api.get("/api/admin/metrics").catch(() => ({ ok: false, users_monthly: [], posts_category: [], transactions: [] })),
    api.get("/api/admin/posts/pending").catch(() => ({ ok: false, posts: [] })),
  ]);
  
  const s = d.stats;
  root.innerHTML = `
  <div class="stack">
    <h1>Administración</h1>
    <div class="kpis">
      <div class="kpi"><div class="n">${money(d.held.cents)}</div><div class="muted small">Retenido en ${d.held.orders} orden(es)</div></div>
      <div class="kpi"><div class="n">${d.disputes.length}</div><div class="muted small">Disputas abiertas</div></div>
      <div class="kpi"><div class="n">${d.reports.length}</div><div class="muted small">Reportes sin revisar</div></div>
      <div class="kpi"><div class="n">${s.users}</div><div class="muted small">Usuarios</div></div>
    </div>

    <!-- Módulo de Gráficas (Dashboard Centeno) -->
    <div class="panelbox stack">
      <h2>Métricas y Estadísticas del Sistema</h2>
      <div class="row wrap" style="gap:20px; align-items: flex-start;">
        <div style="flex:1; min-width:280px; background:var(--bg-card); padding:12px; border-radius:8px; border:1px solid var(--border)">
          <h3 class="small muted" style="margin-bottom:10px">Usuarios Registrados por Mes</h3>
          <canvas id="chartUsers" height="180"></canvas>
        </div>
        <div style="flex:1; min-width:280px; background:var(--bg-card); padding:12px; border-radius:8px; border:1px solid var(--border)">
          <h3 class="small muted" style="margin-bottom:10px">Publicaciones por Categoría</h3>
          <canvas id="chartCategories" height="180"></canvas>
        </div>
      </div>
      <div style="margin-top:15px; background:var(--bg-card); padding:12px; border-radius:8px; border:1px solid var(--border)">
        <h3 class="small muted" style="margin-bottom:10px">Transacciones / Órdenes Realizadas</h3>
        <canvas id="chartTransactions" height="120"></canvas>
      </div>
    </div>

    <div class="panelbox stack">
      <h2>Publicaciones pendientes de moderación ${pending.posts?.length ? `<span class="badge inline">${pending.posts.length}</span>` : ""}</h2>
      <p class="muted small">Revisa y autoriza las nuevas publicaciones antes de que sean visibles en el catálogo general.</p>
      ${pending.posts && pending.posts.length ? pending.posts.map((p) => `
        <div class="item" style="align-items: flex-start;">
          <div class="grow stack" style="gap:4px">
            <div class="t"><strong>${esc(p.title)}</strong> · <span class="muted small">${esc(p.category)} · ${p.price_cents ? money(p.price_cents) : p.tipo}</span></div>
            <div class="small">${esc(p.description)}</div>
            <div class="muted small">Publicado por ${esc(p.author.name)} (${esc(p.author.centro)}) · ${timeAgo(p.created_at)}</div>
          </div>
          <div class="row wrap" style="gap:8px">
            <button class="btn sm green" data-mod-post="${p.id}" data-mod-act="approve">Aprobar</button>
            <button class="btn sm danger" data-mod-post="${p.id}" data-mod-act="reject">Rechazar</button>
          </div>
        </div>
      `).join("") : '<p class="muted">No hay publicaciones pendientes de revisión.</p>'}
    </div>

    <div class="panelbox stack"><h2>Egresados por verificar ${d.verifications.length ? `<span class="badge inline">${d.verifications.length}</span>` : ""}</h2>
      <p class="muted small">Compara el nombre y la carrera con el documento. Al resolver, el archivo se borra.</p>
      ${d.verifications.length ? d.verifications.map((v) => `<div class="item verif" data-v="${v.id}"><div class="grow stack" style="gap:6px">
        <div class="t">${esc(v.name)} <span class="muted small">· ${esc(v.email)}</span></div>
        <div class="small">${esc(v.carrera)} <span class="muted">(${esc(v.centro)})</span></div>
        <div class="muted small">${esc(v.doc_label)} · enviado ${timeAgo(v.created_at)}</div>
        ${v.is_pdf ? `<a class="btn sm ghost" target="_blank" rel="noopener" href="/api/admin/verifications/${v.id}/file">Abrir PDF</a>`
          : `<a target="_blank" rel="noopener" href="/api/admin/verifications/${v.id}/file"><img class="doc" src="/api/admin/verifications/${v.id}/file" alt="${esc(v.doc_label)} de ${esc(v.name)}"></a>`}
        <div class="row wrap"><button class="btn sm green" data-ok="${v.id}">Aprobar</button><button class="btn sm danger" data-no="${v.id}">Rechazar</button></div></div></div>`).join("")
        : '<p class="muted">No hay documentos pendientes.</p>'}</div>
    <div class="panelbox stack"><h2>Disputas</h2>
      ${d.disputes.length ? d.disputes.map((o) => `<a class="item" href="#/order/${o.id}"><div class="grow"><div class="t">${esc(o.post_title)} · ${money(o.amount_cents)}</div>
        <div class="muted small">${esc(o.buyer.name)} ↔ ${esc(o.seller.name)} · ${timeAgo(o.updated_at)}</div><div class="small">“${esc(o.dispute_reason)}”</div></div><span class="btn sm">Resolver</span></a>`).join("") : '<p class="muted">No hay disputas pendientes.</p>'}</div>
    <div class="panelbox stack"><h2>Reportes</h2>
      ${d.reports.length ? d.reports.map((r) => `<div class="item"><div class="grow"><div class="t">${r.target_type === "post" ? "Publicación" : "Usuario"}: ${esc(r.target_label || "#" + r.target_id)}</div>
        <div class="small">${esc(r.reason)}</div><div class="muted small">Reportó ${esc(r.reporter)} · ${timeAgo(r.created_at)}</div></div>
        <div class="stack"><button class="btn sm ghost" data-r="${r.id}" data-a="dismiss">Descartar</button>
        <button class="btn sm danger" data-r="${r.id}" data-a="${r.target_type === "post" ? "remove_post" : "suspend_user"}">${r.target_type === "post" ? "Retirar" : "Suspender"}</button></div></div>`).join("") : '<p class="muted">Sin reportes.</p>'}</div>
    <div class="panelbox stack"><h2>Usuarios</h2><div class="list">
      ${d.users.map((u) => `<div class="item"><div class="grow"><div class="t">${esc(u.name || "(sin nombre)")} ${u.role === "admin" ? "· admin" : ""}${u.kind === "egresado" ? ` · egresado (${u.verif_status === "approved" ? "verificado" : u.verif_status === "rejected" ? "rechazado" : "pendiente"})` : ""}</div><div class="muted small">${esc(u.email)}</div></div>
        ${u.role === "admin" || u.id === state.user.id ? "" : `<div class="row"><button class="btn sm ${u.suspended ? "" : "ghost"}" data-u="${u.id}" data-s="${u.suspended ? 0 : 1}">${u.suspended ? "Reactivar" : "Suspender"}</button>
          <button class="btn sm danger ghosty" data-del="${u.id}" data-mail="${esc(u.email)}" data-name="${esc(u.name || u.email)}" aria-label="Eliminar cuenta de ${esc(u.name || u.email)}">${icon("trash")} Eliminar</button></div>`}</div>`).join("")}</div></div>
    <div class="panelbox stack">
      <div class="row wrap between" style="align-items:center">
        <h2>Respaldos del Sistema ${bks.backups?.length ? `<span class="badge inline">${bks.backups.length}</span>` : ""}</h2>
        <div class="row wrap" style="gap:8px">
          <label class="btn sm ghost" style="cursor:pointer;margin:0" title="Subir un archivo .zip de respaldo">+ Subir .zip<input type="file" id="input-upload-backup" accept=".zip" hidden></label>
          <button class="btn sm green" id="btn-create-backup">+ Crear respaldo ahora</button>
        </div>
      </div>
      <p class="muted small">
        Respaldos periódicos: ${bks.config?.enabled ? `Activo (cada ${bks.config.interval_hours} horas, retiene ${bks.config.keep} copias)` : "Desactivado"}.
        Empaqueta la base de datos SQLite y todas las fotografías/documentos en un archivo .zip descargable. Al restaurar, se crea automáticamente una copia preventiva del estado actual.
      </p>
      ${bks.backups && bks.backups.length ? `
        <div class="list">
          ${bks.backups.map((b) => `
            <div class="item" style="align-items:center">
              <div class="grow stack" style="gap:4px">
                <div class="t">${esc(b.filename)} <span class="badge inline small">${b.tag === "auto" ? "Automático" : b.tag === "pre_restore" ? "Preventivo" : b.tag === "subido" ? "Subido" : "Manual"}</span></div>
                <div class="muted small">Tamaño: ${esc(b.human_size)} · ${b.uploads_count} fotos · creado ${timeAgo(b.created_timestamp)}</div>
              </div>
              <div class="row wrap" style="gap:8px">
                <button class="btn sm ghost" data-restore-backup="${esc(b.filename)}" title="Restaurar el sistema a este punto">Restaurar</button>
                <a class="btn sm ghost" href="/api/admin/backups/${encodeURIComponent(b.filename)}/download" download>Descargar .zip</a>
                <button class="btn sm danger ghost" data-del-backup="${esc(b.filename)}">Eliminar</button>
              </div>
            </div>
          `).join("")}
        </div>
      ` : '<p class="muted">No hay respaldos registrados todavía.</p>'}
    </div>
  </div>`;

  // Inicializar Gráficas con Chart.js si la librería está cargada
  if (typeof Chart !== "undefined") {
    const uM = metrics.users_monthly || [];
    const pC = metrics.posts_category || [];
    const txM = metrics.transactions || [];

    new Chart(root.querySelector("#chartUsers"), {
      type: 'line',
      data: {
        labels: uM.map(x => x.month || "Actual"),
        datasets: [{ label: 'Usuarios', data: uM.map(x => x.count), borderColor: '#1d5c3a', backgroundColor: 'rgba(29, 92, 58, 0.1)', fill: true, tension: 0.3 }]
      },
      options: { responsive: true, plugins: { legend: { display: false } } }
    });

    new Chart(root.querySelector("#chartCategories"), {
      type: 'doughnut',
      data: {
        labels: pC.map(x => x.category || "General"),
        datasets: [{ data: pC.map(x => x.count), backgroundColor: ['#1d5c3a', '#2a8050', '#48b875', '#a3e6b5', '#888'] }]
      },
      options: { responsive: true }
    });

    new Chart(root.querySelector("#chartTransactions"), {
      type: 'bar',
      data: {
        labels: txM.map(x => x.month || "Sin datos"),
        datasets: [{ label: 'Órdenes', data: txM.map(x => x.count), backgroundColor: '#1d5c3a' }]
      },
      options: { responsive: true }
    });
  }

  // Event Listeners existentes
  root.querySelectorAll("[data-ok]").forEach((b) => (b.onclick = async () => {
    if (!(await ask({ title: "¿Aprobar este egresado?", text: "Confirma que el documento es legible y coincide con su nombre y carrera.", confirm: "Aprobar" }))) return;
    try { await api.post(`/api/admin/verifications/${b.dataset.ok}/review`, { action: "approve" }); toast("Egresado verificado"); refresh(); } catch (e) { toast(e.message, true); }
  }));
  root.querySelectorAll("[data-no]").forEach((b) => (b.onclick = async () => {
    const note = await ask({ title: "Rechazar documento", text: "Dile qué corregir; lo verá en su pantalla.", field: "Motivo (mín. 10 caracteres)", confirm: "Rechazar", danger: true });
    if (!note) return;
    try { await api.post(`/api/admin/verifications/${b.dataset.no}/review`, { action: "reject", note }); toast("Solicitud rechazada"); refresh(); } catch (e) { toast(e.message, true); }
  }));
  root.querySelectorAll("[data-r]").forEach((b) => (b.onclick = async () => {
    if (!(await ask({ title: "¿Confirmar?", confirm: "Confirmar" }))) return;
    try { await api.post(`/api/admin/reports/${b.dataset.r}/resolve`, { action: b.dataset.a }); toast("Listo"); refresh(); } catch (e) { toast(e.message, true); }
  }));
  root.querySelectorAll("[data-u]").forEach((b) => (b.onclick = async () => {
    try { await api.post(`/api/admin/users/${b.dataset.u}/suspend`, { suspended: b.dataset.s === "1" }); toast("Listo"); refresh(); } catch (e) { toast(e.message, true); }
  }));
  root.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    const mail = await ask({
      title: `Eliminar la cuenta de ${b.dataset.name}`,
      text: "Se borran de forma permanente su correo, nombre, carrera, foto, contraseña, mensajes enviados, lista de deseos, documentos de egresado y fotos de sus publicaciones. Sus publicaciones se retiran. Solo se conserva el historial anónimo de pagos. No se puede deshacer.",
      field: `Para confirmar escribe el correo: ${b.dataset.mail}`, confirm: "Eliminar para siempre", danger: true, minLength: 5,
    });
    if (!mail) return;
    try { await api.del(`/api/admin/users/${b.dataset.del}`, { confirm_email: mail }); toast("Cuenta eliminada y datos borrados"); refresh(); }
    catch (e) { toast(e.message, true); }
  }));

  root.querySelectorAll("[data-mod-post]").forEach((btn) => {
    btn.onclick = async () => {
      const pid = btn.dataset.modPost;
      const act = btn.dataset.modAct;
      const confirmText = act === "approve" ? "¿Aprobar esta publicación?" : "¿Rechazar esta publicación?";
      if (!(await ask({ title: confirmText, confirm: act === "approve" ? "Aprobar" : "Rechazar", danger: act === "reject" }))) return;
      try {
        await api.post(`/api/admin/posts/${pid}/moderate`, { action: act });
        toast(act === "approve" ? "Publicación aprobada" : "Publicación rechazada");
        refresh();
      } catch (e) {
        toast(e.message, true);
      }
    };
  });

  const btnCreate = root.querySelector("#btn-create-backup");
  if (btnCreate) {
    btnCreate.onclick = async () => {
      btnCreate.disabled = true;
      btnCreate.textContent = "Generando respaldo...";
      try {
        await api.post("/api/admin/backups", { tag: "manual" });
        toast("Respaldo generado con éxito");
        refresh();
      } catch (e) {
        toast(e.message, true);
        btnCreate.disabled = false;
        btnCreate.textContent = "+ Crear respaldo ahora";
      }
    };
  }

  root.querySelectorAll("[data-del-backup]").forEach((btn) => (btn.onclick = async () => {
    const fn = btn.dataset.delBackup;
    if (!(await ask({ title: "¿Eliminar respaldo?", text: `¿Deseas eliminar el archivo ${fn}?`, confirm: "Eliminar", danger: true }))) return;
    try {
      await api.del(`/api/admin/backups/${encodeURIComponent(fn)}`);
      toast("Respaldo eliminado");
      refresh();
    } catch (e) {
      toast(e.message, true);
    }
  }));

  root.querySelectorAll("[data-restore-backup]").forEach((btn) => (btn.onclick = async () => {
    const fn = btn.dataset.restoreBackup;
    const ok = await ask({
      title: "¿Restaurar este respaldo?",
      text: `Se reemplazará la base de datos y archivos multimedia con los del respaldo «${fn}». Se creará automáticamente una copia preventiva antes de proceder.`,
      confirm: "Sí, restaurar ahora",
      danger: true,
    });
    if (!ok) return;
    btn.disabled = true;
    btn.textContent = "Restaurando...";
    try {
      const res = await api.post(`/api/admin/backups/${encodeURIComponent(fn)}/restore`);
      toast(res.message || "Respaldo restaurado exitosamente");
      setTimeout(() => refresh(), 800);
    } catch (e) {
      toast(e.message, true);
      btn.disabled = false;
      btn.textContent = "Restaurar";
    }
  }));

  const inputUpload = root.querySelector("#input-upload-backup");
  if (inputUpload) {
    inputUpload.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (!file.name.toLowerCase().endsWith(".zip")) {
        return toast("Solo se admiten archivos .zip de respaldo", true);
      }
      const fd = new FormData();
      fd.append("backup_file", file);
      toast("Subiendo y validando respaldo...");
      try {
        await api.form("POST", "/api/admin/backups/upload", fd);
        toast("Respaldo subido exitosamente");
        refresh();
      } catch (err) {
        toast(err.message, true);
      }
    };
  }
}