/* Studio composer behaviour from src/ai/AiStudio.jsx: starter prompts fill the
   message box, the character count updates as you type, the draft is saved
   while you work, and sending shows the "working with your brief" status. */
(function () {
  const composer = document.querySelector('[data-composer]');
  const box = composer?.querySelector('[data-message]');
  const count = composer?.querySelector('[data-count]');
  const messages = document.querySelector('.conversation-messages');

  document.querySelectorAll('[data-starter]').forEach(button => {
    button.addEventListener('click', () => {
      if (!box) return;
      box.value = button.dataset.starter;
      box.focus();
      update();
    });
  });

  function update() {
    if (count && box) count.textContent = String(box.value.length);
  }

  let timer;
  box?.addEventListener('input', () => {
    update();
    clearTimeout(timer);
    timer = setTimeout(saveDraft, 800);
  });

  function saveDraft() {
    const session = composer?.querySelector('input[name="session"]')?.value;
    const token = composer?.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    if (!session || !box) return;
    const body = new FormData();
    body.append('session', session);
    body.append('draft', box.value);
    body.append('csrfmiddlewaretoken', token || '');
    fetch('/assistants/draft', { method: 'POST', body, credentials: 'same-origin' }).catch(() => {});
  }

  composer?.addEventListener('submit', () => {
    clearTimeout(timer);
    if (!messages) return;
    const agent = document.querySelector('.conversation-heading h2')?.textContent || 'Your specialist';
    const thinking = document.createElement('div');
    thinking.className = 'thinking';
    thinking.setAttribute('role', 'status');
    thinking.textContent = `✦ ${agent} is working with your brief…`;
    messages.appendChild(thinking);
    thinking.scrollIntoView({ behavior: 'auto', block: 'nearest' });
  });

  messages?.scrollIntoView({ behavior: 'auto', block: 'nearest' });
})();
