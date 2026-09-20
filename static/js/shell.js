/* Shell behaviour ported from the Shell component in src/main.jsx: mobile
   drawer with focus trap and scroll lock, the workspace search dialog, and the
   dismissible notice. Same DOM, same ARIA attributes, same 761px breakpoint. */
(function () {
  const drawer = document.querySelector('[data-drawer]');
  const scrim = document.querySelector('[data-scrim]');
  const toggle = document.querySelector('[data-menu-toggle]');
  const closeButton = document.querySelector('[data-drawer-close]');
  const main = document.querySelector('.workspace-main');
  const desktop = window.matchMedia('(min-width: 761px)');
  let previousOverflow = '';

  function focusables() {
    return [...drawer.querySelectorAll('a,button')].filter(el => el.getClientRects().length);
  }

  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add('open');
    if (scrim) scrim.hidden = false;
    if (toggle) toggle.setAttribute('aria-expanded', 'true');
    if (main) main.setAttribute('inert', '');
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    focusables()[0]?.focus();
  }

  function closeDrawer(returnFocus) {
    if (!drawer) return;
    drawer.classList.remove('open');
    if (scrim) scrim.hidden = true;
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    if (main) main.removeAttribute('inert');
    document.body.style.overflow = previousOverflow;
    if (returnFocus) requestAnimationFrame(() => toggle?.focus());
  }

  toggle?.addEventListener('click', openDrawer);
  closeButton?.addEventListener('click', () => closeDrawer(true));
  scrim?.addEventListener('click', () => closeDrawer(true));
  desktop.addEventListener('change', () => { if (desktop.matches) closeDrawer(false); });

  document.addEventListener('keydown', event => {
    if (!drawer?.classList.contains('open')) return;
    if (event.key === 'Escape') closeDrawer(true);
    if (event.key === 'Tab') {
      const targets = focusables();
      const first = targets[0];
      const last = targets[targets.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  const dialog = document.querySelector('[data-search-dialog]');
  const input = document.querySelector('[data-search-input]');
  const items = [...document.querySelectorAll('[data-search-item]')];
  const emptyMessage = document.querySelector('[data-search-empty]');

  function filter() {
    const term = (input?.value || '').toLowerCase();
    let matches = 0;
    items.forEach(item => {
      const hit = item.dataset.label.includes(term);
      item.hidden = !hit;
      if (hit) matches += 1;
    });
    if (emptyMessage) emptyMessage.hidden = matches > 0;
  }

  document.querySelector('[data-search-open]')?.addEventListener('click', () => {
    if (!dialog) return;
    if (input) input.value = '';
    filter();
    dialog.showModal();
    input?.focus();
  });
  document.querySelector('[data-search-close]')?.addEventListener('click', () => dialog?.close());
  input?.addEventListener('input', filter);
  dialog?.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });

  document.querySelectorAll('[data-notice-dismiss]').forEach(button => {
    button.addEventListener('click', () => button.parentElement?.remove());
  });
})();
