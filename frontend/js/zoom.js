// Visor de imágenes con zoom interactivo (sin librerías, compatible con la CSP `script-src 'self'`).
//  · Rueda del ratón o botones +/−   · doble clic/toque: acerca o restablece
//  · Arrastrar para mover            · Pellizco con dos dedos en pantallas táctiles
//  · ← → cambian de foto             · Esc cierra
import { esc, icon } from "./ui.js";

const MIN = 1, MAX = 5;

export function openLightbox(images, start = 0, alt = "") {
  if (!images.length) return;
  const opener = document.activeElement;
  let i = Math.min(Math.max(start, 0), images.length - 1);
  let s = 1, tx = 0, ty = 0;

  const ov = document.createElement("div");
  ov.className = "lightbox";
  ov.setAttribute("role", "dialog");
  ov.setAttribute("aria-modal", "true");
  ov.setAttribute("aria-label", "Visor de fotos");
  ov.innerHTML = `
    <header>
      <div class="grow" id="lbcount"></div>
      <button class="lbbtn" data-z="out" aria-label="Alejar">${icon("zoomout")}</button>
      <button class="lbbtn" data-z="in" aria-label="Acercar">${icon("zoomin")}</button>
      <button class="lbbtn" data-close aria-label="Cerrar">${icon("x")}</button>
    </header>
    <div class="stage" id="stage">
      <img id="lbimg" alt="${esc(alt)}" draggable="false">
      ${images.length > 1 ? `<button class="lbbtn navbtn prev" aria-label="Foto anterior">${icon("left")}</button>
      <button class="lbbtn navbtn next" aria-label="Foto siguiente">${icon("right")}</button>` : ""}
    </div>
    <footer>Rueda o pellizco para acercar · arrastra para mover · doble clic para ampliar</footer>`;
  document.body.append(ov);
  const prevOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";

  const stage = ov.querySelector("#stage");
  const img = ov.querySelector("#lbimg");
  const count = ov.querySelector("#lbcount");

  const clamp = () => {
    const mx = Math.max(0, (img.offsetWidth * s - stage.clientWidth) / 2);
    const my = Math.max(0, (img.offsetHeight * s - stage.clientHeight) / 2);
    tx = Math.min(mx, Math.max(-mx, tx));
    ty = Math.min(my, Math.max(-my, ty));
  };
  const apply = () => {
    if (s <= MIN) { tx = 0; ty = 0; }
    clamp();
    img.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
    stage.classList.toggle("zoomed", s > MIN);
    ov.querySelector('[data-z="out"]').disabled = s <= MIN;
    ov.querySelector('[data-z="in"]').disabled = s >= MAX;
  };
  /** Cambia la escala manteniendo fijo el punto (px, py) medido desde el centro del visor. */
  const zoomTo = (ns, px = 0, py = 0) => {
    ns = Math.min(MAX, Math.max(MIN, ns));
    const k = ns / s;
    tx = px - (px - tx) * k; ty = py - (py - ty) * k;
    s = ns; apply();
  };
  const centerOf = (e) => { const r = stage.getBoundingClientRect(); return [e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2]; };

  const show = (n) => {
    i = (n + images.length) % images.length;
    s = 1; tx = 0; ty = 0;
    img.src = images[i];
    count.textContent = images.length > 1 ? `Foto ${i + 1} de ${images.length}` : "Foto";
    apply();
  };

  // --- rueda
  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    const [px, py] = centerOf(e);
    zoomTo(s * Math.exp(-e.deltaY * 0.0018), px, py);
  }, { passive: false });

  // --- arrastre y pellizco (pointer events)
  const ptrs = new Map();
  let startDist = 0, startScale = 1, moved = 0, lastTap = 0;
  stage.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".navbtn")) return;
    stage.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    moved = 0;
    if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      startDist = Math.hypot(a.x - b.x, a.y - b.y) || 1; startScale = s;
    }
    if (s > MIN) stage.classList.add("drag");
  });
  stage.addEventListener("pointermove", (e) => {
    const p = ptrs.get(e.pointerId); if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    moved += Math.abs(dx) + Math.abs(dy);
    if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const r = stage.getBoundingClientRect();
      zoomTo(startScale * (d / startDist), (a.x + b.x) / 2 - r.left - r.width / 2, (a.y + b.y) / 2 - r.top - r.height / 2);
    } else if (s > MIN) { tx += dx; ty += dy; apply(); }
  });
  const end = (e) => {
    const was = ptrs.has(e.pointerId);
    ptrs.delete(e.pointerId);
    if (!ptrs.size) stage.classList.remove("drag");
    // doble toque en pantallas táctiles (el dblclick no se dispara con pointer capture en todos los navegadores)
    if (was && e.type === "pointerup" && e.pointerType === "touch" && moved < 8) {
      const t = Date.now();
      if (t - lastTap < 320) { const [px, py] = centerOf(e); zoomTo(s > MIN ? MIN : 2.5, px, py); lastTap = 0; } else lastTap = t;
    }
  };
  stage.addEventListener("pointerup", end);
  stage.addEventListener("pointercancel", end);
  stage.addEventListener("dblclick", (e) => { const [px, py] = centerOf(e); zoomTo(s > MIN ? MIN : 2.5, px, py); });

  // --- botones
  ov.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.hasAttribute("data-close")) return close();
    if (b.dataset.z) return zoomTo(s * (b.dataset.z === "in" ? 1.5 : 1 / 1.5));
    if (b.classList.contains("prev")) show(i - 1);
    if (b.classList.contains("next")) show(i + 1);
  });

  // --- teclado
  const onKey = (e) => {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft" && images.length > 1) show(i - 1);
    else if (e.key === "ArrowRight" && images.length > 1) show(i + 1);
    else if (e.key === "+" || e.key === "=") zoomTo(s * 1.5);
    else if (e.key === "-") zoomTo(s / 1.5);
    else if (e.key === "0") zoomTo(MIN);
  };
  const onResize = () => apply();
  document.addEventListener("keydown", onKey);
  window.addEventListener("resize", onResize);
  // si el usuario navega (hash) con el visor abierto, se cierra
  window.addEventListener("hashchange", close, { once: true });

  function close() {
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("resize", onResize);
    window.removeEventListener("hashchange", close);
    document.body.style.overflow = prevOverflow;
    ov.remove();
    if (opener && opener.focus) opener.focus();
  }

  show(i);
  ov.querySelector("[data-close]").focus();
}
