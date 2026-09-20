/* Discover filters: the React screen filtered as you typed, so the form
   submits on change and shortly after typing stops. "Clear filters" resets
   every control, as it did before. */
(function () {
  const form = document.querySelector('[data-autofilter]');
  if (!form) return;
  let timer;
  form.querySelectorAll('select').forEach(select => {
    select.addEventListener('change', () => form.submit());
  });
  form.querySelectorAll('input[name="search"]').forEach(input => {
    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => form.submit(), 400);
    });
  });
  form.querySelector('[data-clear-filters]')?.addEventListener('click', () => {
    window.location.assign(form.getAttribute('action'));
  });
})();
