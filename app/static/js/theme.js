(() => {
  const root = document.documentElement;
  const saved = localStorage.getItem('foundry-theme');
  if (saved === 'light' || saved === 'dark') root.dataset.theme = saved;

  const updateLabel = () => {
    const light = root.dataset.theme === 'light';
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    toggle.setAttribute('aria-label', `Switch to ${light ? 'dark' : 'light'} theme`);
    const label = toggle.querySelector('.toggle-label');
    if (label) label.textContent = `${light ? 'Dark' : 'Light'} mode`;
  };

  document.addEventListener('DOMContentLoaded', () => {
    updateLabel();
    document.querySelector('.theme-toggle')?.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
      localStorage.setItem('foundry-theme', root.dataset.theme);
      updateLabel();
    });
  });
})();
