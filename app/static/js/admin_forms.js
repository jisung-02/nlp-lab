const initAdminFormHelpers = () => {
  document.addEventListener("submit", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLFormElement)) {
      return;
    }

    const confirmMessage = target.dataset.confirmDelete;
    if (confirmMessage && !window.confirm(confirmMessage)) {
      event.preventDefault();
      return;
    }

    const displayOrderInput = target.querySelector('input[name="display_order"]');
    if (displayOrderInput instanceof HTMLInputElement && displayOrderInput.value !== "") {
      const displayOrder = Number(displayOrderInput.value);
      if (!Number.isFinite(displayOrder) || displayOrder < 0) {
        event.preventDefault();
        window.alert("표시 순서는 0 이상의 숫자여야 합니다.");
        displayOrderInput.focus();
        return;
      }
    }

    const startDateInput = target.querySelector('input[name="start_date"]');
    const endDateInput = target.querySelector('input[name="end_date"]');
    if (
      startDateInput instanceof HTMLInputElement &&
      endDateInput instanceof HTMLInputElement &&
      startDateInput.value &&
      endDateInput.value &&
      endDateInput.value < startDateInput.value
    ) {
      event.preventDefault();
      window.alert("종료일은 시작일보다 빠를 수 없습니다.");
      endDateInput.focus();
    }
  });
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAdminFormHelpers);
} else {
  initAdminFormHelpers();
}
