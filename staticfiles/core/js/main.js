/* ================================================================
   TechRepair — JavaScript principal (extraído de base.html)
   ================================================================ */

/* ── COUNTDOWN en tiempo real ── */
function actualizarCountdowns() {
  const ahora = new Date();
  document.querySelectorAll('.countdown[data-target]').forEach(el => {
    const target = new Date(el.dataset.target);
    if (isNaN(target.getTime())) return;
    let diff = (target - ahora) / 1000;
    const vencido = diff < 0;
    diff = Math.abs(diff);
    const dias  = Math.floor(diff / 86400);
    const horas = Math.floor((diff % 86400) / 3600);
    const mins  = Math.floor((diff % 3600) / 60);
    const segs  = Math.floor(diff % 60);

    let texto;
    if (dias > 0)       texto = `${dias}d ${horas}h ${mins}m`;
    else if (horas > 0) texto = `${horas}h ${mins}m ${segs}s`;
    else                texto = `${mins}m ${segs}s`;

    if (vencido) {
      el.textContent = `Vencido hace ${texto}`;
      el.style.color = 'var(--danger)';
    } else {
      el.textContent = texto;
      el.style.color = (dias > 0 || horas >= 1) ? 'var(--warn)' : 'var(--success)';
    }
  });
}
actualizarCountdowns();
setInterval(actualizarCountdowns, 1000);

/* ── AUTO-FILTRO: debounce en forms GET con campo q ── */
(function () {
  let _debounceTimer = null;

  function autoSubmit(form) {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(function () { form.submit(); }, 420);
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[method="GET"]').forEach(function (form) {
      const qInput = form.querySelector('input[name="q"]');
      if (!qInput) return;

      qInput.addEventListener('input', function () { autoSubmit(form); });

      form.querySelectorAll('select').forEach(function (sel) {
        sel.addEventListener('change', function () { autoSubmit(form); });
      });
    });
  });
})();
