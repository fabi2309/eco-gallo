import { api } from "../api.js";
import { esc, icon, timeAgo, clock, avatar, badges, toast } from "../ui.js";

export async function render(root, ctx) {
  return ctx.args.length ? thread(root, ctx) : inbox(root);
}

async function inbox(root) {
  const { threads } = await api.get("/api/threads");
  root.innerHTML = `<h1 style="margin-bottom:16px">Mensajes</h1>` + (threads.length
    ? `<div class="list">${threads.map((t) => `<a class="item" href="#/chat/${t.post_id}/${t.other.id}">
        ${avatar(t.other)}
        <div class="grow"><div class="t">${esc(t.other.name)} ${badges(t.other, { compact: true })} <span class="muted small">· ${esc(t.post_title)}</span></div>
        <div class="muted small" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t.last.mine ? "Tú: " : ""}${esc(t.last.content)}</div></div>
        <div class="muted small">${timeAgo(t.last.created_at)}</div>${t.unread ? `<span class="badge">${t.unread}</span>` : ""}</a>`).join("")}</div>`
    : `<div class="empty">${icon("chat")}<h2>Aquí aparecerán tus conversaciones</h2><p>Abre un artículo y escribe al vendedor para coordinar la entrega.</p><a class="btn" href="#/">Ver artículos</a></div>`);
}

async function thread(root, { args, state, isCurrent }) {
  const [postId, otherId] = args.map(Number);
  let data = await api.get(`/api/threads/${postId}/${otherId}`);
  root.innerHTML = `
  <a href="#/messages" class="small">← Mensajes</a>
  <div class="chat" style="margin-top:10px">
    <header>${avatar(data.other)}
      <div class="grow"><b>${esc(data.other.name)}</b>${badges(data.other) ? `<div>${badges(data.other)}</div>` : ""}<div class="muted small">${esc(data.other.carrera || "")}</div></div>
      <a class="btn ghost sm" href="#/post/${postId}">${esc(data.post.title.slice(0, 22))}${data.post.title.length > 22 ? "…" : ""}</a></header>
    <div class="msgs" id="msgs" aria-live="polite"></div>
    <div><div class="safe">${icon("shield")} Encuentros seguros en el campus: ${esc(data.meeting_points.join(" · "))}. Nunca pagues fuera de ECO-GALLO si quieres tener protección.</div>
      <form class="composer" id="f"><input class="input" name="c" maxlength="1000" placeholder="Escribe un mensaje" autocomplete="off" required aria-label="Mensaje">
      <button class="btn" aria-label="Enviar">${icon("send")}</button></form></div>
  </div>`;
  const box = root.querySelector("#msgs");
  const msgs = data.messages;
  let seenUpTo = 0;
  const lastId = () => (msgs.length ? msgs[msgs.length - 1].id : 0);
  const bubble = (m) => `<div class="bubble ${m.sender_id === state.user.id ? "me" : ""}${m.pending ? " pending" : ""}" data-id="${m.id || ""}">${esc(m.content)}<time>${clock(m.created_at)}${m.sender_id === state.user.id && m.id && m.id <= seenUpTo ? " · Visto" : ""}</time></div>`;
  const draw = () => {
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    box.innerHTML = msgs.length
      ? msgs.map(bubble).join("")
      : `<p class="muted" style="margin:auto;text-align:center">Saluda a ${esc(data.other.name.split(" ")[0])} para coordinar.</p>`;
    if (atBottom || !draw.done) box.scrollTop = box.scrollHeight;
    draw.done = true;
  };
  draw();
  const merge = (incoming) => {
    let changed = false;
    for (const m of incoming) {
      if (msgs.some((x) => x.id === m.id)) continue;
      const i = msgs.findIndex((x) => x.pending && x.content === m.content && m.sender_id === state.user.id);
      if (i >= 0) msgs.splice(i, 1);
      msgs.push(m); changed = true;
    }
    msgs.sort((a, b) => (a.id || Infinity) - (b.id || Infinity));
    return changed;
  };
  root.querySelector("#f").onsubmit = async (e) => {
    e.preventDefault();
    const input = e.target.c; const content = input.value.trim(); if (!content) return;
    input.value = "";
    // Se muestra al instante; se confirma cuando el servidor responde.
    const temp = { pending: true, sender_id: state.user.id, content, created_at: Date.now() / 1000 };
    msgs.push(temp); draw(); box.scrollTop = box.scrollHeight;
    try {
      const r = await api.post("/api/messages", { post_id: postId, receiver_id: otherId, content });
      msgs.splice(msgs.indexOf(temp), 1); merge([r.message]); draw();
    } catch (err) { msgs.splice(msgs.indexOf(temp), 1); draw(); toast(err.message, true); input.value = content; }
  };
  // Tiempo real: sondeo incremental cada 1 s mientras la conversación está visible (objetivo < 2 s).
  let busy = false;
  async function poll() {
    if (busy || !isCurrent() || !document.body.contains(box) || document.hidden) return;
    busy = true;
    try {
      const r = await api.get(`/api/threads/${postId}/${otherId}/since?after=${lastId()}`);
      const seenChanged = r.seen_up_to !== seenUpTo; seenUpTo = r.seen_up_to;
      if (merge(r.messages) || seenChanged) draw();
    } catch { /* reintenta en el siguiente ciclo */ }
    busy = false;
  }
  poll();
  const timer = setInterval(() => { if (!isCurrent() || !document.body.contains(box)) { clearInterval(timer); document.removeEventListener("visibilitychange", poll); } else poll(); }, 1000);
  document.addEventListener("visibilitychange", poll);
}
