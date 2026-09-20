/* Landing page behaviour, matching src/Landing.jsx: the mobile menu opens and
   closes (including on Escape and on any click inside it), and the buttons
   that called navigate() follow their data-href. */
(function () {
  const openButton = document.getElementById('openMenuButton');
  const closeButton = document.getElementById('closeMenuButton');
  const menu = document.getElementById('mobileNavigation');

  function setMenu(active) {
    if (!menu) return;
    menu.classList.toggle('active', active);
    menu.setAttribute('aria-hidden', active ? 'false' : 'true');
    openButton?.setAttribute('aria-expanded', active ? 'true' : 'false');
  }

  openButton?.addEventListener('click', () => setMenu(true));
  closeButton?.addEventListener('click', event => { event.stopPropagation(); setMenu(false); });
  menu?.addEventListener('click', () => setMenu(false));
  document.querySelector('[data-landing]')?.addEventListener('keydown', event => {
    if (event.key === 'Escape') setMenu(false);
  });

  document.querySelectorAll('[data-href]').forEach(button => {
    button.addEventListener('click', () => { window.location.assign(button.dataset.href); });
  });
})();
