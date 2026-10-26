import { api } from "../api.js";
import { esc, icon, timeAgo, clock, avatar, toast } from "../ui.js";

export async function render(root, ctx) {
  return ctx.args.length ? thread(root, ctx) : inbox(root);
}

async function inbox(root) {
  const { threads } = await api.get("/api/threads");
  root.innerHTML = `<h1 style="margin-bottom:16px">Mensajes</h1>` + (threads.length
    ? `<div class="list">${threads.map((t) => `<a class="item" href="#/chat/${t.post_id}/${t.other.id}">
        ${avatar(t.other)}
        <div class="grow"><div class="t">${esc(t.other.name)} <span class="muted small">· ${esc(t.post_title)}</span></div>
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
      <div class="grow"><b>${esc(data.other.name)}</b><div class="muted small">${esc(data.other.carrera || "")}</div></div>
      <a class="btn ghost sm" href="#/post/${postId}">${esc(data.post.title.slice(0, 22))}${data.post.title.length > 22 ? "…" : ""}</a></header>
    <div class="msgs" id="msgs" aria-live="polite"></div>
    <div><div class="safe">${icon("shield")} Encuentros seguros en el campus: ${esc(data.meeting_points.join(" · "))}. Nunca pagues fuera de ECO-GALLO si quieres tener protección.</div>
      <form class="composer" id="f"><input class="input" name="c" maxlength="1000" placeholder="Escribe un mensaje" autocomplete="off" required aria-label="Mensaje">
      <button class="btn" aria-label="Enviar">${icon("send")}</button></form></div>
  </div>`;
  const box = root.querySelector("#msgs");
  const draw = () => {
    box.innerHTML = data.messages.length
      ? data.messages.map((m) => `<div class="bubble ${m.sender_id === state.user.id ? "me" : ""}">${esc(m.content)}<time>${clock(m.created_at)}</time></div>`).join("")
      : `<p class="muted" style="margin:auto;text-align:center">Saluda a ${esc(data.other.name.split(" ")[0])} para coordinar.</p>`;
    box.scrollTop = box.scrollHeight;
  };
  draw();
  root.querySelector("#f").onsubmit = async (e) => {
    e.preventDefault();
    const input = e.target.c; const content = input.value.trim(); if (!content) return;
    input.value = "";
    try { await api.post("/api/messages", { post_id: postId, receiver_id: otherId, content }); await poll(); }
    catch (err) { toast(err.message, true); input.value = content; }
  };
  async function poll() {
    if (!isCurrent()) return;
    try { data = await api.get(`/api/threads/${postId}/${otherId}`); draw(); } catch { /* reintenta */ }
  }
  const timer = setInterval(() => { if (!isCurrent() || !document.body.contains(box)) clearInterval(timer); else poll(); }, 5000);
}
