// Tema claro/oscuro. Se carga en <head> (script normal) para que no parpadee al abrir.
(function () {
  var stored = null;
  try { stored = localStorage.getItem("eg_theme"); } catch (e) { /* almacenamiento bloqueado */ }
  var dark = stored ? stored === "dark" : window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
})();
