const initPublicationsFilter = () => {
  const form = document.querySelector("[data-publications-filter]");
  if (!(form instanceof HTMLFormElement)) {
    return;
  }

  const yearSelect = form.querySelector("[data-year-select]");
  if (!(yearSelect instanceof HTMLSelectElement)) {
    return;
  }

  yearSelect.addEventListener("change", () => {
    form.requestSubmit();
  });
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initPublicationsFilter);
} else {
  initPublicationsFilter();
}
