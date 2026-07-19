/* ================================================================
   TechRepair — Transiciones y efectos de interacción
   ================================================================ */

document.addEventListener('DOMContentLoaded', function () {

  /* ── 1. FADE-OUT al hacer clic en links de navegación ── */
  document.querySelectorAll('a[href]').forEach(function (link) {
    // Solo links internos, no âncoras, no target="_blank"
    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript')
        || link.target === '_blank' || link.hasAttribute('data-no-transition')) return;

    link.addEventListener('click', function (e) {
      // No interferir con Ctrl+Click, Cmd+Click
      if (e.ctrlKey || e.metaKey || e.shiftKey) return;
      e.preventDefault();
      const dest = link.href;
      document.body.classList.add('tr-leaving');
      setTimeout(function () { window.location.href = dest; }, 180);
    });
  });

  /* ── 2. RIPPLE en botones ── */
  document.querySelectorAll('.btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      const rect = btn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top  - size / 2;

      const ripple = document.createElement('span');
      ripple.className = 'tr-ripple';
      ripple.style.cssText = `width:${size}px;height:${size}px;left:${x}px;top:${y}px`;
      btn.appendChild(ripple);
      ripple.addEventListener('animationend', function () { ripple.remove(); });
    });
  });

  /* ── 3. SPINNER en botones de submit ── */
  document.querySelectorAll('form').forEach(function (form) {
    // No aplicar en forms GET (filtros, búsqueda)
    if (form.method && form.method.toUpperCase() === 'GET') return;

    form.addEventListener('submit', function () {
      const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
      if (!submitBtn || submitBtn.classList.contains('tr-loading')) return;

      // Guardar texto original y agregar spinner
      const originalHTML = submitBtn.innerHTML;
      const spinner = document.createElement('span');
      spinner.className = 'tr-spinner';
      submitBtn.classList.add('tr-loading');
      submitBtn.innerHTML = '';
      submitBtn.appendChild(spinner);

      const label = document.createElement('span');
      label.textContent = ' Procesando…';
      submitBtn.appendChild(label);

      // Restaurar por si el servidor devuelve error y recarga la página
      setTimeout(function () {
        if (submitBtn.classList.contains('tr-loading')) {
          submitBtn.classList.remove('tr-loading');
          submitBtn.innerHTML = originalHTML;
        }
      }, 8000);
    });
  });

  /* ── 4. BOTÓN PDF / INFORME: spinner especial ── */
  document.querySelectorAll('a[href*="pdf"], a[href*="informe"], a[href*="reporte"]').forEach(function (link) {
    link.addEventListener('click', function () {
      if (link.classList.contains('tr-loading')) return;
      const original = link.innerHTML;
      link.classList.add('tr-loading');
      const spinner = document.createElement('span');
      spinner.className = 'tr-spinner';
      link.innerHTML = '';
      link.appendChild(spinner);
      const label = document.createElement('span');
      label.textContent = ' Generando…';
      link.appendChild(label);

      setTimeout(function () {
        link.classList.remove('tr-loading');
        link.innerHTML = original;
      }, 4000);
    });
  });

  /* ── 5. CONFIRM en botones de eliminar / acción destructiva ── */
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      const msg = el.dataset.confirm || '¿Estás seguro?';
      if (!confirm(msg)) e.preventDefault();
    });
  });

  /* ── 6. CERRAR alertas con click ── */
  document.querySelectorAll('.alert-close, [data-dismiss="alert"]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const alert = btn.closest('.alert, .error, [class*="msg-"]');
      if (alert) {
        alert.style.transition = 'opacity .2s, transform .2s';
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-8px)';
        setTimeout(function () { alert.remove(); }, 220);
      }
    });
  });

  /* ── 7. AUTO-CERRAR mensajes de éxito después de 4s ── */
  document.querySelectorAll('.messages .success, .alert-success').forEach(function (msg) {
    setTimeout(function () {
      msg.style.transition = 'opacity .4s, transform .4s';
      msg.style.opacity = '0';
      msg.style.transform = 'translateY(-8px)';
      setTimeout(function () { msg.remove(); }, 420);
    }, 4000);
  });

});
