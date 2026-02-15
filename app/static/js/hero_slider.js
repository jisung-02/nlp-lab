const initHeroSlider = () => {
  const slider = document.querySelector('.hero-slider');
  if (!(slider instanceof HTMLElement)) {
    return;
  }

  const slides = Array.from(slider.querySelectorAll('.hero-slide'));
  if (slides.length === 0) {
    return;
  }

  const prevButton = slider.querySelector('.hero-nav-prev');
  const nextButton = slider.querySelector('.hero-nav-next');
  const dots = Array.from(slider.querySelectorAll('.hero-dot'));
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  let activeIndex = slides.findIndex((slide) => slide.classList.contains('is-active'));
  if (activeIndex < 0) {
    activeIndex = 0;
    slides[0].classList.add('is-active');
  }

  let autoplayId = null;
  const autoplayMs = Number(slider.dataset.autoplay || 7000);
  const useReducedMotion = prefersReducedMotion.matches;

  const applySlidePositions = (nextIndex) => {
    slides.forEach((slide, index) => {
      const offset = index - nextIndex;
      slide.style.transform = `translateX(${offset * 100}%)`;
      slide.style.opacity = index === nextIndex ? '1' : '0';
      slide.style.pointerEvents = index === nextIndex ? 'auto' : 'none';
      slide.classList.toggle('is-active', index === nextIndex);
    });

    const activeDot = dots[nextIndex];
    dots.forEach((dot, index) => {
      dot.classList.toggle('is-active', index === nextIndex);
      dot.setAttribute('aria-current', index === nextIndex ? 'true' : 'false');
    });
    if (activeDot instanceof HTMLButtonElement) {
      activeDot.setAttribute('aria-current', 'true');
    }
  };

  if (slides.length <= 1) {
    dots.forEach((dot) => {
      dot.style.display = 'none';
    });
    if (prevButton instanceof HTMLElement) {
      prevButton.style.display = 'none';
    }
    if (nextButton instanceof HTMLElement) {
      nextButton.style.display = 'none';
    }
    return;
  }

  const applyActiveState = (nextIndex) => {
    const normalized = (nextIndex + slides.length) % slides.length;
    if (normalized === activeIndex) {
      return;
    }

    activeIndex = normalized;
    applySlidePositions(activeIndex);
  };

  const goTo = (index) => {
    applyActiveState(index);
  };

  const goPrev = () => {
    goTo(activeIndex - 1);
  };

  const goNext = () => {
    goTo(activeIndex + 1);
  };

  const clearAutoplay = () => {
    if (autoplayId === null) {
      return;
    }
    window.clearInterval(autoplayId);
    autoplayId = null;
  };

  const startAutoplay = () => {
    clearAutoplay();
    if (useReducedMotion || slides.length <= 1) {
      return;
    }
    autoplayId = window.setInterval(() => {
      goNext();
    }, Number.isFinite(autoplayMs) && autoplayMs > 500 ? autoplayMs : 7000);
  };

  if (useReducedMotion) {
    slides.forEach((slide) => {
      slide.style.transition = 'none';
    });
  }

  slider.addEventListener('mouseenter', clearAutoplay);
  slider.addEventListener('focusin', clearAutoplay);
  slider.addEventListener('mouseleave', startAutoplay);
  slider.addEventListener('focusout', startAutoplay);

  if (prevButton instanceof HTMLElement) {
    prevButton.addEventListener('click', () => {
      goPrev();
      startAutoplay();
    });
  }

  if (nextButton instanceof HTMLElement) {
    nextButton.addEventListener('click', () => {
      goNext();
      startAutoplay();
    });
  }

  dots.forEach((dot, index) => {
    if (!(dot instanceof HTMLButtonElement)) {
      return;
    }

    dot.addEventListener('click', () => {
      goTo(index);
      startAutoplay();
    });
  });

  if (dots[activeIndex]) {
    dots[activeIndex]?.setAttribute('aria-current', 'true');
  }

  applySlidePositions(activeIndex);

  startAutoplay();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initHeroSlider);
} else {
  initHeroSlider();
}
