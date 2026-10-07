(() => {
  const form = document.querySelector('.report-form');
  const overlay = document.getElementById('report-submit-overlay');
  if (!form || !overlay) return;

  const button = form.querySelector('.report-submit-button');
  const title = document.getElementById('report-submit-title');
  const detail = document.getElementById('report-submit-detail');
  let submitted = false;

  const showSavingState = () => {
    overlay.hidden = false;
    document.body.classList.add('is-submitting-report');
    if (button) {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      button.value = form.classList.contains('is-editing') ? 'Saving…' : 'Publishing…';
      button.textContent = form.classList.contains('is-editing') ? 'Saving…' : 'Publishing…';
    }
  };

  const optimizePhoto = async (file) => {
    if (!window.createImageBitmap || !window.DataTransfer || !window.File) return;
    const bitmap = await createImageBitmap(file);
    try {
      const scale = Math.min(1, 1440 / Math.max(bitmap.width, bitmap.height));
      const width = Math.max(1, Math.round(bitmap.width * scale));
      const height = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d', { alpha: false });
      if (!context) return;
      context.drawImage(bitmap, 0, 0, width, height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', 0.8));
      if (!blob || blob.size >= file.size) return;
      const optimized = new File([blob], `${file.name.replace(/\.[^.]+$/, '')}.webp`, {
        type: 'image/webp',
        lastModified: Date.now(),
      });
      const transfer = new DataTransfer();
      transfer.items.add(optimized);
      form.querySelector('input[type="file"]').files = transfer.files;
    } finally {
      bitmap.close?.();
    }
  };

  form.addEventListener('submit', async (event) => {
    if (submitted) {
      event.preventDefault();
      return;
    }
    submitted = true;
    event.preventDefault();
    showSavingState();
    window.setTimeout(() => {
      if (!document.body.contains(overlay)) return;
      if (title) title.textContent = 'Still working on it…';
      if (detail) detail.textContent = 'Your report is still saving. Please keep this page open.';
    }, 7000);

    const imageInput = form.querySelector('input[type="file"]');
    const image = imageInput?.files?.[0];
    if (image && title && detail) {
      title.textContent = 'Preparing your photo…';
      detail.textContent = 'Reducing the image size so your report uploads faster.';
      try {
        await optimizePhoto(image);
      } catch (_) {
        // Continue with the original image if this browser cannot resize it.
      }
    }

    if (title) title.textContent = form.classList.contains('is-editing') ? 'Saving your changes…' : 'Publishing your report…';
    if (detail) detail.textContent = 'Your report is being saved.';
    HTMLFormElement.prototype.submit.call(form);
  });
})();
