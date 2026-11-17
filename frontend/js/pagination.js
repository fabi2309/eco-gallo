import { toast } from './ui.js';

export function pager(root, page, pages, onPage, label = 'Página') {
  root.querySelector('[data-pagination]')?.remove();
  if (pages <= 1) return;
  const nav = document.createElement('nav');
  nav.dataset.pagination = '1';
  nav.className = 'pager';
  nav.setAttribute('aria-label', label);
  const previous = document.createElement('button');
  previous.textContent = 'Anterior'; previous.className = 'btn ghost'; previous.disabled = page <= 1;
  const next = document.createElement('button');
  next.textContent = 'Siguiente'; next.className = 'btn ghost'; next.disabled = page >= pages;
  const text = document.createElement('span');
  text.textContent = `${label} ${page} de ${pages}`;
  for (const [button, target] of [[previous, page - 1], [next, page + 1]]) {
    button.onclick = async () => {
      button.disabled = true;
      try { await onPage(target); } catch (error) { toast(error.message, true); button.disabled = false; }
    };
  }
  nav.append(previous, text, next); root.append(nav);
}
