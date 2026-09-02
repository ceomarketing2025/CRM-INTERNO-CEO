document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-target]');
  if (!button) return;
  const target = document.getElementById(button.dataset.copyTarget);
  if (!target) return;
  const text = 'value' in target ? target.value : target.innerText;
  try {
    await navigator.clipboard.writeText(text);
    const original = button.textContent;
    button.textContent = 'Copiado ✓';
    setTimeout(() => { button.textContent = original; }, 1600);
  } catch (e) {
    target.focus();
    if (target.select) target.select();
    document.execCommand('copy');
  }
});
