const initRevealSections = () => {
  const revealItems = document.querySelectorAll(".section, .page-hero, .page-content");
  if (revealItems.length === 0) {
    return;
  }

  if (!("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 },
  );

  revealItems.forEach((item) => observer.observe(item));
};

const initPublicUi = () => {
  initRevealSections();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initPublicUi);
} else {
  initPublicUi();
}
