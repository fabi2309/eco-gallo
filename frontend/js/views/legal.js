// Aviso de privacidad y términos de uso (tesina, secciones 5.3, 5.5, 5.6 y 5.9).
// Si cambias el texto, sube LEGAL_VERSION en backend/config.py: se volverá a pedir la aceptación.
import { esc } from "../ui.js";

function who(m) {
  const l = (m && m.legal) || {};
  const mail = l.email
    ? `<a href="mailto:${esc(l.email)}">${esc(l.email)}</a>`
    : "<b>[correo de contacto pendiente de configurar]</b>";
  return { name: esc(l.operator || "Equipo ECO-GALLO UAA"), addr: esc(l.address || ""), mail, version: esc(l.version || "") };
}

export function privacyHtml(m) {
  const w = who(m);
  return `
  <h1>Aviso de privacidad integral</h1>
  <p class="muted small">Versión ${w.version}</p>

  <h2>1. Responsable</h2>
  <p><b>${w.name}</b>, con domicilio en ${w.addr}, es responsable del tratamiento de los datos personales que se recaban
  en ECO-GALLO UAA, conforme a la Ley Federal de Protección de Datos Personales en Posesión de los Particulares.
  Contacto para cualquier asunto de privacidad: ${w.mail}.</p>

  <h2>2. Datos que recabamos</h2>
  <ul>
    <li><b>Identificación y contacto:</b> nombre completo, correo electrónico (institucional o, para egresados, personal), carrera y centro académico.</li>
    <li><b>Perfil opcional:</b> fotografía y biografía.</li>
    <li><b>Cuenta Microsoft de la UAA:</b> si entras con ella, Microsoft nos confirma tu correo institucional; no recibimos tu contraseña.</li>
    <li><b>Verificación de egresados:</b> imagen o PDF de tu kárdex o título. Lo revisa solo administración y se borra al resolver la solicitud.</li>
    <li><b>Actividad en la plataforma:</b> publicaciones y sus fotografías, mensajes, compras y ventas, reportes, favoritos, lista de deseos y notificaciones.</li>
    <li><b>Pagos con tarjeta (solo si los usas):</b> número de celular confirmado por SMS; del comprador, marca y últimos 4 dígitos de la tarjeta con que pagó; del vendedor, titular, tipo (tarjeta de débito o CLABE) y últimos 4 dígitos de la cuenta donde recibe. Nunca guardamos el número completo de la tarjeta ni el código de seguridad (CVV): el navegador los valida y no se envían a ECO-GALLO.</li>
    <li><b>Ubicación (opcional):</b> si al publicar eliges «Usar mi ubicación actual», guardamos la ubicación aproximada del punto de entrega (redondeada a unos 100 m) y otros usuarios pueden verla en el mapa. Cuando usas «Cerca de mí», tu ubicación solo se usa para calcular distancias en ese momento y no se guarda.</li>
    <li><b>Seguridad:</b> contraseña (guardada solo como hash), secreto de verificación en dos pasos (cifrado), sesiones, intentos de acceso y la dirección IP desde la que se solicitan códigos.</li>
  </ul>
  <p>No solicitamos datos personales sensibles. Con Mercado Pago, los datos de tarjeta los recibe directamente Mercado Pago; ECO-GALLO no los ve ni los guarda.</p>

  <h2>3. Finalidades</h2>
  <p><b>Necesarias</b> para el servicio:</p>
  <ul>
    <li>Verificar que perteneces a la comunidad UAA y crear tu cuenta.</li>
    <li>Publicar, buscar, intercambiar, donar, comprar y vender materiales académicos.</li>
    <li>Permitir la comunicación entre usuarios y enviarte avisos sobre tu actividad.</li>
    <li>Moderar contenido, atender reportes y disputas, y prevenir fraudes o abusos.</li>
    <li>En compras con tarjeta, permitir que comprador y vendedor (y administración en una disputa) se localicen por teléfono si el artículo no se entrega.</li>
    <li>Mantener la seguridad del sistema y realizar respaldos cifrados.</li>
  </ul>
  <p><b>Secundarias</b> (puedes oponerte sin afectar el servicio): generar estadísticas agregadas y anónimas del impacto económico y ambiental de la plataforma.</p>

  <h2>4. Transferencias y encargados</h2>
  <p>No vendemos ni cedemos tus datos. Solo los compartimos con proveedores que nos prestan un servicio (hospedaje, envío de correos, inicio de sesión con Microsoft y, si se activan, pagos en línea con Mercado Pago o Stripe), quienes los tratan por nuestra cuenta, y con autoridades cuando una ley lo exija.</p>
  <p>Dentro de la plataforma, otros usuarios ven tu nombre, carrera, centro, foto, biografía, insignias y tus publicaciones. Tu correo no se muestra a otros usuarios. Tu celular solo lo ve la otra persona de una compra con tarjeta en la que participes, y administración. Para enviar los SMS de confirmación usamos un proveedor de mensajería (Twilio).</p>

  <h2>5. Tus derechos ARCO y revocación del consentimiento</h2>
  <ul>
    <li><b>Acceso:</b> en <a href="#/profile">Perfil → Privacidad y mis datos</a> puedes descargar una copia de todos tus datos.</li>
    <li><b>Rectificación:</b> corrige tu nombre, carrera y biografía desde tu perfil.</li>
    <li><b>Cancelación:</b> elimina tu cuenta desde tu perfil. Se borran tus datos personales; solo conservamos montos y estados de operaciones pasadas, sin datos que te identifiquen, mientras sea necesario para atender aclaraciones.</li>
    <li><b>Oposición y revocación:</b> escríbenos a ${w.mail} indicando tu nombre, el correo de tu cuenta y lo que solicitas. Respondemos en un máximo de 20 días hábiles.</li>
  </ul>

  <h2>6. Cookies y almacenamiento local</h2>
  <p>Usamos una cookie de sesión indispensable para mantenerte conectado. El navegador guarda además tu preferencia de modo claro u oscuro y tus búsquedas recientes; puedes borrarlas desde el buscador o desde tu navegador. No usamos cookies de publicidad ni de rastreo de terceros.</p>

  <h2>7. Conservación y seguridad</h2>
  <p>Conservamos tus datos mientras tengas una cuenta activa. Aplicamos conexión cifrada (HTTPS), contraseñas con hash, verificación en dos pasos opcional, control de acceso por roles y respaldos cifrados que se rotan periódicamente.</p>

  <h2>8. Cambios a este aviso</h2>
  <p>Si este aviso cambia, te lo mostraremos al iniciar sesión y te pediremos aceptarlo de nuevo antes de continuar.</p>`;
}

export function termsHtml(m) {
  const w = who(m);
  return `
  <h1>Términos y condiciones de uso</h1>
  <p class="muted small">Versión ${w.version}</p>

  <h2>1. Quién puede usar ECO-GALLO</h2>
  <p>Solo estudiantes con correo institucional de la UAA y egresados cuyo documento haya sido verificado por administración. La cuenta es personal e intransferible; eres responsable de lo que se haga con ella.</p>

  <h2>2. Qué hace la plataforma</h2>
  <p>ECO-GALLO pone en contacto a miembros de la comunidad para vender, intercambiar o donar materiales académicos. ECO-GALLO no es dueño de los artículos ni parte en los acuerdos entre usuarios. No ofrece envío a domicilio: la entrega se coordina entre las partes, de preferencia en los puntos de encuentro seguros del campus.</p>

  <h2>3. Publicaciones</h2>
  <ul>
    <li>Describe el artículo con veracidad, incluido su estado físico, y usa fotografías propias del artículo.</li>
    <li>Toda publicación pasa por revisión antes de mostrarse y vuelve a revisarse si cambias su contenido.</li>
    <li>Está prohibido publicar armas, sustancias ilegales o controladas, alcohol, tabaco, medicamentos, animales, artículos robados, falsificados o cualquier cosa ajena a la vida académica.</li>
    <li>Respeta los derechos de autor: no ofrezcas fotocopias o copias digitales no autorizadas de libros, software o materiales protegidos.</li>
  </ul>

  <h2>4. Conducta</h2>
  <p>No acoses, engañes ni amenaces a otros usuarios, no envíes publicidad no solicitada y no intentes vulnerar la seguridad del sistema. Puedes reportar publicaciones o usuarios; administración puede retirar contenido y suspender o eliminar cuentas que incumplan estos términos o la normativa de la UAA.</p>

  <h2>5. Compras y pagos</h2>
  <p>Hay dos formas de pago: <b>tarjeta</b> y <b>efectivo al entregar</b>. Para pagar o cobrar con tarjeta, comprador y vendedor deben confirmar su número de celular por SMS; ese número se comparte entre ambos (y con administración) para poder localizarse si el artículo no se entrega. En efectivo, el pago se hace en mano al recibir el artículo en el campus y ECO-GALLO no interviene en el dinero. Cuando la plataforma está en modo de prueba, los pagos con tarjeta son simulados y no se mueve dinero real. Con tarjeta, el importe queda retenido hasta que el comprador confirma la recepción; las disputas las resuelve administración. Fuera de la plataforma, ECO-GALLO no puede proteger tu dinero.</p>

  <h2>6. Responsabilidad</h2>
  <p>Cada usuario responde por los artículos que ofrece y por los acuerdos que celebra. ECO-GALLO procura que el servicio esté disponible y seguro, pero no garantiza la calidad de los artículos ni el cumplimiento de terceros. Las cifras de impacto ambiental son estimaciones orientativas.</p>

  <h2>7. Datos personales</h2>
  <p>El tratamiento de tus datos se rige por el <a href="#/privacidad">aviso de privacidad</a>.</p>

  <h2>8. Cambios y contacto</h2>
  <p>Podemos actualizar estos términos; te pediremos aceptarlos de nuevo antes de seguir usando la plataforma. Dudas: ${w.mail}.</p>`;
}

/** Página pública (sin sesión) o dentro de la app. */
export function render(root, { extra, state, inShell = false }) {
  const body = extra === "terminos" ? termsHtml(state.meta) : privacyHtml(state.meta);
  const back = inShell ? "" : `<p><a class="btn ghost sm" href="#/">← Volver</a></p>`;
  const html = `<article class="legal">${back}${body}
    <p class="muted small">${extra === "terminos"
      ? '<a href="#/privacidad">Ver aviso de privacidad</a>'
      : '<a href="#/terminos">Ver términos y condiciones</a>'}</p></article>`;
  if (inShell) { root.innerHTML = html; return; }
  root.innerHTML = `<main class="legalpage">${html}</main>`;
}

/** Casilla de aceptación para formularios de registro. Los enlaces abren el texto en una ventana encima,
 *  sin salir del formulario (antes abrían otra pestaña que podía mostrar el registro en lugar del texto). */
export const consentBox = (version) => `
  <label class="consent"><input type="checkbox" name="accept_terms" value="${esc(version)}" required>
    <span>He leído y acepto el <a href="#/privacidad" data-legal="privacidad">aviso de privacidad</a>
    y los <a href="#/terminos" data-legal="terminos">términos de uso</a>.</span></label>`;

/** Muestra el aviso o los términos en una ventana sobre la página actual. */
export function openLegal(which, meta) {
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `<div class="modal legalmodal" role="dialog" aria-modal="true" aria-label="${which === "terminos" ? "Términos y condiciones de uso" : "Aviso de privacidad"}">
    <div class="legal">${which === "terminos" ? termsHtml(meta) : privacyHtml(meta)}</div>
    <button type="button" class="btn block" data-x>Cerrar</button></div>`;
  const close = () => { ov.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => e.key === "Escape" && close();
  ov.addEventListener("click", (e) => {
    if (e.target === ov || e.target.closest("[data-x]")) return close();
    const other = e.target.closest("a[href='#/privacidad'], a[href='#/terminos']");
    if (other) { e.preventDefault(); close(); openLegal(other.getAttribute("href").slice(2), meta); }
  });
  document.addEventListener("keydown", onKey);
  document.body.append(ov);
  ov.querySelector("[data-x]").focus();
}

/** Pantalla que pide aceptar una versión nueva (o la primera) a usuarios ya registrados. */
export function renderAccept(root, { state, api, onDone, onLogout }) {
  const v = state.meta.legal.version;
  root.innerHTML = `<main class="legalpage"><article class="legal">
    <div class="notice">Para seguir usando ECO-GALLO necesitamos que leas y aceptes el aviso de privacidad y los términos de uso vigentes.</div>
    <details open><summary><b>Aviso de privacidad</b></summary>${privacyHtml(state.meta)}</details>
    <details><summary><b>Términos y condiciones de uso</b></summary>${termsHtml(state.meta)}</details>
    <form id="acc" class="stack" novalidate>
      ${consentBox(v)}
      <div id="err"></div>
      <div class="row wrap"><button class="btn">Aceptar y continuar</button><button type="button" class="btn ghost" id="out">Cerrar sesión</button></div>
    </form></article></main>`;
  root.querySelector("#out").onclick = onLogout;
  root.querySelector("#acc").onsubmit = async (e) => {
    e.preventDefault();
    if (!e.target.accept_terms.checked) {
      root.querySelector("#err").innerHTML = '<div class="error" role="alert">Marca la casilla para aceptar.</div>';
      return;
    }
    try { await api.post("/api/me/terms", { accept: true, version: v }); onDone(); }
    catch (err) { root.querySelector("#err").innerHTML = `<div class="error" role="alert">${esc(err.message)}</div>`; }
  };
}
