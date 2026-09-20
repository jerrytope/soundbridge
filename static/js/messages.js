(() => {
  const panel = document.querySelector('[data-thread-url]');
  if (!panel) return;
  let previous = '';
  async function refresh() {
    if (document.hidden) return;
    try {
      const response = await fetch(panel.dataset.threadUrl, {credentials: 'same-origin', headers: {'Accept': 'application/json'}});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const {messages} = await response.json();
      const signature = messages.map(m => m.id).join(',');
      if (signature === previous) return;
      previous = signature;
      const nodes = messages.map(m => {
        const article = document.createElement('article');
        const title = document.createElement('strong'); title.textContent = m.sender;
        const date = document.createElement('time'); date.textContent = new Date(m.created_at).toLocaleString();
        const body = document.createElement('p'); body.textContent = m.body; body.style.whiteSpace = 'pre-wrap';
        article.append(title, date, body); return article;
      });
      panel.replaceChildren(...nodes);
    } catch (_) { /* Existing messages and the composer remain usable. */ }
  }
  setInterval(refresh, 10000);
})();
