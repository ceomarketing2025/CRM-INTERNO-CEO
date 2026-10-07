document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-target]');
  if (!button) return;
  const target = document.getElementById(button.dataset.copyTarget);
  if (!target) return;
  const text = 'value' in target ? target.value : target.innerText;
  try {
    await navigator.clipboard.writeText(text);
    const label = button.querySelector('.btn-label');
    if (label) {
      const original = label.textContent;
      label.textContent = 'Copiado ✓';
      setTimeout(() => { label.textContent = original; }, 1600);
    } else {
      const original = button.textContent;
      button.textContent = 'Copiado ✓';
      setTimeout(() => { button.textContent = original; window.crmDecorateButtons?.(document); }, 1600);
    }
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

// Sidebar V16: un solo panel desplegable abierto a la vez.
document.addEventListener("DOMContentLoaded", () => {
  const sections = Array.from(document.querySelectorAll("[data-nav-section]"));
  let locking = false;

  sections.forEach((section) => {
    section.addEventListener("toggle", () => {
      if (locking || !section.open) return;
      locking = true;
      sections.forEach((other) => {
        if (other !== section && other.open) other.open = false;
      });
      locking = false;
    });
  });

  document.querySelectorAll(".sidebar .nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      if (window.innerWidth <= 980) document.body.classList.remove("sidebar-open");
    });
  });
});

// V25 · ROOT UI SYSTEM: un único lenguaje para botones y acciones del CRM.
(function () {
  const ICONS = {
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18l-6-6 6-6"/><path d="M9 12h11"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/><path d="M4 12h11"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    save: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h12l2 2v14H5V4Z"/><path d="M8 4v6h8V4M8 20v-6h8v6"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5m4-5v5"/></svg>',
    edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l11-11-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/></svg>',
    eye: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/></svg>',
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>',
    filter: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M10 18h4"/></svg>',
    reset: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8v5h5"/><path d="M5.5 17a8 8 0 1 0 1-10L4 10"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5"/><path d="M18.5 5.5A8 8 0 1 0 20 14"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4 10-10"/></svg>',
    download: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/></svg>',
    upload: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20V9"/><path d="m7 13 5-5 5 5"/><path d="M5 4h14"/></svg>',
    copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
    send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 18-8-8 18-2-7-8-3Z"/><path d="m11 14 5-5"/></svg>',
    calendar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v15H5zM8 3v4m8-4v4M5 9h14"/></svg>',
    link: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/></svg>',
    unlink: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 15l-2 2a4 4 0 0 1-6-6l3-3M15 9l2-2a4 4 0 0 1 6 6l-3 3M8 12h8M4 4l16 16"/></svg>',
    file: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h9l3 3v15H6V3Z"/><path d="M9 12h6M9 16h4"/></svg>',
    folder: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h7l2 2h9v10H3V7Z"/></svg>',
    tasks: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 6 1 1 2-2m-3 7 1 1 2-2m-3 7 1 1 2-2"/></svg>',
    users: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a5 5 0 0 1 10 0v2M16 11a3 3 0 1 0 0-6M15 15a5 5 0 0 1 6 5"/></svg>',
    key: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="15" r="4"/><path d="m11 12 8-8m-3 3 2 2m-5 1 2 2"/></svg>',
    wallet: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h15v13H4z"/><path d="M4 9h16v6h-5a3 3 0 0 1 0-6h5"/></svg>',
    briefcase: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16v12H4zM9 7V4h6v3M4 12h16"/></svg>',
    palette: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18h2a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h8A9 9 0 0 0 12 3Z"/><circle cx="7.5" cy="10" r=".7"/><circle cx="10" cy="6.8" r=".7"/><circle cx="14" cy="6.5" r=".7"/><circle cx="17" cy="9" r=".7"/></svg>',
    image: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m5 18 5-5 3 3 2-2 4 4"/></svg>',
    bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 17h12l-1.5-2v-4a4.5 4.5 0 0 0-9 0v4L6 17Z"/><path d="M10 20h4"/></svg>',
    clipboard: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h10v16H7z"/><path d="M9 5V3h6v2M10 10h4m-4 4h4"/></svg>',
    grid: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></svg>',
    login: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 8l4 4-4 4M18 12H8"/><path d="M10 4H5v16h5"/></svg>',
    logout: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 4H5v16h5M14 8l4 4-4 4M18 12H9"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6v12M16 6v12"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7V5Z"/></svg>',
    home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 9-7 9 7"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></svg>',
    globe: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
    video: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/></svg>',
    map: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6l5-2 6 2 5-2v14l-5 2-6-2-5 2V6Z"/><path d="M9 4v14M15 6v14"/></svg>',
    megaphone: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13V9h4l9-4v12l-9-4H4Z"/><path d="M8 13l2 6h3"/></svg>'
  };

  const EXEMPT_SELECTOR = [
    '.menu-toggle',
    '.requirement-card-head',
    '.mk-select__button',
    '.preview-hero button',
    '.palette-live-preview button',
    '.mini-check',
    '.development-filter',
    '.area-filter-btn-v11'
  ].join(',');

  const ICON_ONLY_SELECTOR = [
    '.icon-danger',
    '.icon-action',
    '.table-copy',
    '.production-edit-btn',
    '.seo-modal-close',
    '.production-popup-close',
    '.project-eye-button-v21',
    '.design-eye .btn',
    '.table-actions a',
    '.icon-only'
  ].join(',');

  const EXTRA_ACTION_SELECTOR = [
    '.copy-mini',
    '.mini-copy',
    '.row-remove',
    '.service-remove',
    '.service-category-remove',
    '.service-make-primary',
    '.add-service-inside',
    '.seo-matrix-action',
    '.seo-open-modal',
    '.requirement-save-close',
    '.save-project-v11',
    '.icon-danger',
    '.icon-action',
    '.table-copy',
    '.production-edit-btn',
    '.project-eye-button-v21',
    '.production-popup-close',
    '.seo-modal-close',
    '.table-actions a'
  ].join(',');

  function normalize(value) {
    return (value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function readableLabel(button) {
    const existing = button.querySelector(':scope > .btn-label');
    if (existing && existing.textContent.trim()) return existing.textContent.trim();

    const explicit = button.getAttribute('aria-label') || button.getAttribute('title') || button.dataset.crmLabel;
    const raw = (button.textContent || '').replace(/\s+/g, ' ').trim();
    if (/^[↺⟳]$/.test(raw)) return 'Reabrir';
    if (/^[✓✔]$/.test(raw)) return 'Completar';
    if (/^[×✕✖]$/.test(raw)) return explicit || 'Cerrar';

    const text = raw.replace(/[＋+✓✔↺⟳←→↗×✕✖⌫⧉✎👁○●🎥]/g, ' ').replace(/\s+/g, ' ').trim();
    if (text) return text;
    if (explicit) return explicit.trim();
    if (button.classList.contains('production-edit-btn') || button.classList.contains('icon-action')) return 'Editar';
    if (button.classList.contains('table-copy') || button.classList.contains('copy-mini') || button.classList.contains('mini-copy')) return 'Copiar';
    if (button.classList.contains('icon-danger') || button.classList.contains('row-remove')) return 'Eliminar';
    if (button.classList.contains('project-eye-button-v21')) return 'Ver';
    return 'Abrir';
  }

  function formActionValue(button) {
    const form = button.closest('form');
    if (!form) return '';
    const hidden = form.querySelector('input[name="action"]');
    return normalize(hidden && hidden.value);
  }

  function actionFor(label, button) {
    const value = normalize(label);
    const href = normalize(button.getAttribute('href'));
    const name = normalize(button.getAttribute('name'));
    const ownValue = normalize(button.getAttribute('value'));
    const formValue = formActionValue(button);
    const actionValue = ownValue || formValue;

    if (actionValue === 'rejected') return ['close', 'danger'];
    if (actionValue === 'approved' || actionValue === 'ready' || actionValue === 'complete') return ['check', 'success'];
    if (actionValue === 'start') return ['play', 'success'];
    if (actionValue === 'resume') return ['refresh', 'success'];
    if (actionValue === 'pause') return ['pause', 'warning'];
    if (actionValue === 'review') return ['send', 'info'];
    if (actionValue === 'reopen') return ['reset', 'neutral'];
    if (actionValue === 'toggle_created') return ['check', 'success'];
    if (actionValue === 'toggle_published') return ['send', 'success'];

    if (/mes anterior|\banterior\b/.test(value)) return ['back', 'neutral'];
    if (/mes siguiente|\bsiguiente\b/.test(value)) return ['next', 'info'];
    if (/volver|regresar|atrás|atras/.test(value)) return ['back', 'back'];
    if (/cancelar|rechazar|denegar|cerrar$/.test(value)) return ['close', 'danger'];
    if (/eliminar|borrar|delete|quitar/.test(value)) return ['trash', 'danger'];
    if (/desconectar/.test(value)) return ['unlink', 'danger'];
    if (/cerrar sesión|cerrar sesion|logout|salir/.test(value)) return ['logout', 'danger'];
    if (/ingresar|iniciar sesión|iniciar sesion/.test(value)) return ['login', 'success'];
    if (/guardar borrador|borrador|draft/.test(value)) return ['file', 'neutral'];
    if (/descargar|download|exportar/.test(value)) return ['download', 'success'];
    if (/subir|upload|importar/.test(value)) return ['upload', 'info'];
    if (/copiar|copy/.test(value)) return ['copy', 'info'];
    if (/filtrar/.test(value)) return ['filter', 'info'];
    if (/buscar|search/.test(value)) return ['search', 'info'];
    if (/limpiar|reabrir|restablecer|reset/.test(value)) return ['reset', 'neutral'];
    if (/sincronizar|reintentar/.test(value)) return ['refresh', 'info'];
    if (/editar|modificar|cambiar/.test(value)) return ['edit', 'neutral'];
    if (/mostrar|ocultar|ver|abrir|detalle|ficha|resumen|panel|vista previa/.test(value)) return ['eye', 'info'];
    if (/paleta/.test(value)) return ['palette', 'info'];
    if (/recursos|imágenes|imagenes|fotos/.test(value)) return ['image', 'info'];
    if (/credenciales/.test(value)) return ['key', 'info'];
    if (/billetera|pago|gastos|finanzas/.test(value)) return ['wallet', 'info'];
    if (/producción|produccion/.test(value)) return ['briefcase', 'info'];
    if (/cliente|equipo|responsable/.test(value)) return ['users', value.includes('asignar') ? 'success' : 'info'];
    if (/proyecto|proyectos/.test(value)) return ['folder', 'info'];
    if (/servicio|servicios/.test(value)) return ['grid', 'info'];
    if (/tarea|tareas/.test(value)) return ['tasks', /nueva|crear|agregar|añadir/.test(value) ? 'success' : 'info'];
    if (/recordatorio/.test(value)) return ['bell', /nuevo|crear/.test(value) ? 'success' : 'info'];
    if (/auditoría|auditoria/.test(value)) return ['clipboard', 'info'];
    if (/diseño$|marketing$|desarrollo$|administración$|administracion$/.test(value)) return ['grid', 'info'];
    if (/hoy|reunión|reunion|calendario|agenda|fecha/.test(value)) return ['calendar', 'info'];
    if (/conectar|link|enlace|website|sitio/.test(value)) return ['link', /conectar/.test(value) ? 'success' : 'info'];
    if (/documento|pdf|archivo/.test(value)) return ['file', 'info'];
    if (/social media/.test(value)) return ['image', 'info'];
    if (/dominio|hosting/.test(value)) return ['globe', 'info'];
    if (/google meet|unirse/.test(value)) return ['video', 'success'];
    if (/ciudad|estructura base/.test(value)) return ['map', 'info'];
    if (/publicidad digital|campaña|campanas|campañas/.test(value)) return ['megaphone', 'info'];
    if (/planes y publicaciones/.test(value)) return ['tasks', 'info'];
    if (/enviar|publicar|lanzar|compartir/.test(value)) return ['send', 'success'];
    if (/pausar|pendiente/.test(value)) return ['pause', 'warning'];
    if (/aprobar|validar|revisar|completar|completo|listo|marcar|activar|confirmar|aplicar globalmente/.test(value)) return ['check', 'success'];
    if (/guardar|crear|nuevo|nueva|agregar|añadir|registrar|actualizar|principal|cargar/.test(value)) return [value.includes('guardar') ? 'save' : 'plus', 'success'];
    if (/información|informacion/.test(value)) return ['info', 'info'];

    if (name === 'action' && ownValue === 'complete') return ['check', 'success'];
    if (href.includes('/new') || href.includes('/create')) return ['plus', 'success'];
    if (button.classList.contains('btn-danger') || button.classList.contains('btn-danger-soft')) return ['close', 'danger'];
    if (button.classList.contains('btn-primary')) return ['check', 'success'];
    if (button.classList.contains('btn-light')) return ['info', 'info'];
    return ['next', 'neutral'];
  }

  function shouldDecorate(element) {
    if (!(element instanceof Element)) return false;
    if (element.matches(EXEMPT_SELECTOR)) return false;
    if (element.tagName === 'BUTTON') return true;
    if (element.matches('a.btn')) return true;
    if (element.matches(EXTRA_ACTION_SELECTOR)) return true;
    return false;
  }

  function promoteAction(element) {
    if (!shouldDecorate(element)) return;
    element.classList.add('btn');
    if (element.matches(ICON_ONLY_SELECTOR)) element.classList.add('crm-icon-only');
    if ((element.classList.contains('row-remove') || element.classList.contains('service-remove') || element.classList.contains('service-category-remove')) && !element.classList.contains('btn-sm')) {
      element.classList.add('btn-sm');
    }
  }

  function decorateButton(button) {
    if (!shouldDecorate(button)) return;
    promoteAction(button);

    const label = readableLabel(button);
    const [iconName, tone] = actionFor(label, button);
    button.dataset.crmLabel = label;
    button.classList.add('crm-action-button');
    if (button.classList.contains('icon-only')) button.classList.add('crm-icon-only');
    button.classList.remove('crm-tone-success','crm-tone-danger','crm-tone-neutral','crm-tone-info','crm-tone-warning','crm-tone-back');
    button.classList.add(`crm-tone-${tone}`);

    let icon = button.querySelector(':scope > .btn-icon');
    let text = button.querySelector(':scope > .btn-label');
    if (!icon) {
      icon = document.createElement('span');
      icon.className = 'btn-icon';
      icon.setAttribute('aria-hidden', 'true');
    }
    if (!text) {
      text = document.createElement('span');
      text.className = 'btn-label';
    }
    icon.innerHTML = ICONS[iconName] || ICONS.next;
    text.textContent = label;

    const needsRefresh = button.dataset.crmButtonIcon !== iconName || button.dataset.crmButtonTone !== tone || !button.contains(icon) || !button.contains(text);
    if (needsRefresh || button.children.length !== 2 || button.firstElementChild !== icon || button.lastElementChild !== text) {
      button.replaceChildren(icon, text);
    }
    button.dataset.crmButtonIcon = iconName;
    button.dataset.crmButtonTone = tone;
    button.dataset.crmButtonReady = '1';

    if (button.classList.contains('crm-icon-only')) {
      if (!button.getAttribute('aria-label')) button.setAttribute('aria-label', label);
      if (!button.getAttribute('title')) button.setAttribute('title', label);
    }
  }

  function decorateAllButtons(root) {
    const scope = root && root.querySelectorAll ? root : document;
    const selectors = ['button', 'a.btn', EXTRA_ACTION_SELECTOR].join(',');
    if (scope instanceof Element && scope.matches(selectors)) decorateButton(scope);
    scope.querySelectorAll(selectors).forEach(decorateButton);
  }

  document.addEventListener('DOMContentLoaded', () => {
    decorateAllButtons(document);

    document.addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-pause-trigger]');
      if (!trigger) return;
      const targetId = trigger.getAttribute('data-pause-trigger');
      const panel = targetId ? document.getElementById(targetId) : null;
      if (!panel) return;
      event.preventDefault();
      panel.hidden = !panel.hidden;
      trigger.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');
      if (!panel.hidden) {
        const field = panel.querySelector('textarea, input[name="note"]');
        if (field) field.focus();
      }
    });
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) decorateAllButtons(node);
        });
        const target = mutation.target instanceof Element ? mutation.target : mutation.target.parentElement;
        if (target && target.closest) {
          const action = target.closest('button, a.btn');
          if (action && !action.querySelector(':scope > .btn-icon')) decorateButton(action);
        }
      }
    });
    observer.observe(document.body, {childList:true, subtree:true, characterData:true});
  });

  window.crmDecorateButtons = decorateAllButtons;
})();
