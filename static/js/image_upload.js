/* Image picker behaviour from src/components/ImageUpload.jsx: the visible
   button opens the hidden file input, and choosing a file submits immediately
   so the server can resize and store it. */
(function () {
  document.querySelectorAll('[data-image-upload]').forEach(form => {
    const input = form.querySelector('[data-image-input]');
    const choose = form.querySelector('[data-image-choose]');
    choose?.addEventListener('click', () => input?.click());
    input?.addEventListener('change', () => {
      if (!input.files?.length) return;
      form.setAttribute('aria-busy', 'true');
      if (choose) choose.textContent = 'Preparing image…';
      form.submit();
    });
  });
})();
