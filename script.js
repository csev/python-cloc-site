(() => {
  const trigger = document.querySelector('[data-modal-image]');
  const modal = document.getElementById('image-modal');
  const closeButton = modal?.querySelector('.modal-close');

  if (!trigger || !modal || !closeButton) return;

  const slides = trigger.matches('img')
    ? [trigger]
    : Array.from(trigger.querySelectorAll('img'));
  const carousel = slides.length > 1;
  const modalImage = modal.querySelector('img');
  let index = 0;

  const show = (next) => {
    index = (next + slides.length) % slides.length;
    slides.forEach((img, i) => {
      if (i === 0) return;
      img.classList.toggle('is-visible', i === index);
    });
  };

  const currentSlide = () => slides[index] || slides[0];

  let flipTimer = 0;
  const armFlipTimer = () => {
    window.clearInterval(flipTimer);
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    flipTimer = window.setInterval(() => show(index + 1), 10000);
  };

  if (carousel) {
    const flipNow = (event) => {
      event.preventDefault();
      show(index + 1);
      armFlipTimer();
    };
    trigger.addEventListener('click', flipNow);
    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') flipNow(event);
    });
    armFlipTimer();
  }

  const openModal = () => {
    const current = currentSlide();
    if (current && modalImage) {
      modalImage.src = current.currentSrc || current.src;
      modalImage.alt = current.alt ? `${current.alt} enlarged` : modalImage.alt;
    }
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    closeButton.focus();
  };

  const closeModal = () => {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    trigger.focus();
  };

  if (!carousel) {
    trigger.addEventListener('click', openModal);
    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openModal();
      }
    });
  }

  closeButton.addEventListener('click', closeModal);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeModal();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });
})();
