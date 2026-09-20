/* Release checklist: ticking a task submits its form, matching the immediate
   save the React screen performed on change. */
(function () {
  document.querySelectorAll('[data-task-toggle]').forEach(box => {
    box.addEventListener('change', () => box.closest('form')?.submit());
  });
})();
