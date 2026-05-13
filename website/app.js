/* Captain Taxi — public website JS */

// ── Year in footer
document.getElementById('year').textContent = new Date().getFullYear();

// ── Sticky header class on scroll
(function () {
  const header = document.getElementById('site-header');
  if (!header) return;
  window.addEventListener('scroll', () => {
    header.classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });
})();

// ── Mobile menu toggle
function toggleMenu() {
  const menu = document.getElementById('mobile-menu');
  if (!menu) return;
  const open = menu.style.display === 'flex';
  menu.style.display = open ? 'none' : 'flex';
}

// ── Show/hide scheduled time field based on service selection
(function () {
  const svc = document.getElementById('service');
  const row = document.getElementById('schedule-row');
  const ts  = document.getElementById('scheduled_time');
  if (!svc || !row) return;

  svc.addEventListener('change', function () {
    const needsTime = this.value === 'prebook' || this.value === 'airport';
    row.style.display = needsTime ? '' : 'none';
    if (ts) ts.required = needsTime;
  });
})();

// ── Booking form submission
(function () {
  const form = document.getElementById('booking-form');
  if (!form) return;

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = 'Sending…';

    const city    = document.getElementById('city').value;
    const phone   = city === 'regina' ? '306-775-2222' : '306-242-0000';
    const payload = Object.fromEntries(new FormData(form));

    try {
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        btn.innerHTML = '✓ Booking received! SMS on its way.';
        btn.style.background = '#22c55e';
        form.reset();
        setTimeout(() => {
          btn.innerHTML = original;
          btn.style.background = '';
          btn.disabled = false;
        }, 5000);
      } else {
        throw new Error('Server error');
      }
    } catch {
      // Fallback: direct user to call
      btn.innerHTML = original;
      btn.disabled = false;
      const city = document.getElementById('city').value;
      const num  = city === 'regina' ? '+13067752222' : '+13062420000';
      if (confirm(`Online booking unavailable right now.\n\nCall us directly at ${phone}?`)) {
        window.location.href = 'tel:' + num;
      }
    }
  });
})();

// ── Smooth anchor scroll with header offset
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', function (e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    const offset = 80;
    const top = target.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top, behavior: 'smooth' });
  });
});

// ── Intersection Observer: fade-in on scroll
(function () {
  const els = document.querySelectorAll(
    '.service-card, .area-card, .review-card, .faq-item, .step, .why-point, .trust-item, .visual-card'
  );
  if (!('IntersectionObserver' in window)) return;

  const style = document.createElement('style');
  style.textContent = `
    .fade-ready { opacity: 0; transform: translateY(20px); transition: opacity 0.5s ease, transform 0.5s ease; }
    .fade-ready.visible { opacity: 1; transform: translateY(0); }
  `;
  document.head.appendChild(style);

  els.forEach(el => el.classList.add('fade-ready'));

  const obs = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  els.forEach(el => obs.observe(el));
})();
