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


document.addEventListener("DOMContentLoaded", () => {
  const filterButtons = document.querySelectorAll(".development-filter");
  const projectCards = document.querySelectorAll(".development-card-v5");

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const filter = button.dataset.filter;
      filterButtons.forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");

      projectCards.forEach((card) => {
        card.style.display = filter === "all" || card.dataset.status === filter ? "" : "none";
      });

      document.getElementById("development-projects")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    });
  });
});
