/* Statement upload: choosing a file submits immediately and the drop zone
   accepts a dragged file, as the React screen did. */
(function () {
  const form = document.querySelector('[data-upload-form]');
  const input = form?.querySelector('[data-upload-input]');
  if (!form || !input) return;
  input.addEventListener('change', () => { if (input.files?.length) form.submit(); });
  form.addEventListener('dragover', event => event.preventDefault());
  form.addEventListener('drop', event => {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    form.submit();
  });
})();
