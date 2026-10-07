(() => {
  const form = document.querySelector('.reply-form');
  const button = form?.querySelector('button[type="submit"]');
  if (!form || !button) return;

  form.addEventListener('submit', () => {
    if (button.disabled) return;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    const label = button.firstChild;
    if (label?.nodeType === Node.TEXT_NODE) label.textContent = ' Sending… ';
  });
})();
