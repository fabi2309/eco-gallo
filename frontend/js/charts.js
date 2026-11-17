import { esc } from './ui.js';

// Local accessible charts: no CDN, network dependency or third-party scripts.
export function renderBars(root, values) {
  const max = Math.max(1, ...values.map(([, value]) => Number(value) || 0));
  root.innerHTML = values.length ? values.map(([label, value]) =>
    `<div class="chart-row"><span>${esc(label || 'Sin fecha')}</span><span class="chart-bar" style="width:${Math.max(1, Number(value) / max * 100)}%" aria-hidden="true"></span><b>${esc(value)}</b></div>`
  ).join('') : '<p class="muted">Todavía no hay datos.</p>';
}
