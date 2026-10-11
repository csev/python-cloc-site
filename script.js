(() => {
  const trigger = document.querySelector('[data-modal-image]');
  const modal = document.getElementById('image-modal');
  const closeButton = modal?.querySelector('.modal-close');

  if (!trigger || !modal || !closeButton) return;

  const slides = trigger.matches('img')
    ? [trigger]
    : Array.from(trigger.querySelectorAll('img'));
  const fade = slides.length > 1 ? slides[slides.length - 1] : null;
  const modalImage = modal.querySelector('img');

  const currentSlide = () => {
    if (!fade) return slides[0];
    return parseFloat(getComputedStyle(fade).opacity) > 0.5 ? fade : slides[0];
  };

  if (fade && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    window.setInterval(() => {
      fade.classList.toggle('is-visible');
    }, 10000);
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

  trigger.addEventListener('click', openModal);
  trigger.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openModal();
    }
  });

  closeButton.addEventListener('click', closeModal);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeModal();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });
})();
