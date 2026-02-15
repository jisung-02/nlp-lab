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

const renderHeroUploadPreview = (files) => {
  const preview = document.getElementById("hero-image-preview");
  if (!(preview instanceof HTMLElement)) {
    return;
  }

  if (!Array.isArray(files) || files.length === 0) {
    preview.innerHTML = '<p class="meta-line">선택된 파일 없음</p>';
    return;
  }

  const rows = files.map((file) => `<li>${file.name} (${Math.ceil(file.size / 1024)}KB)</li>`);
  preview.innerHTML = `<ul>${rows.join("")}</ul>`;
};

const applyHeroImageFiles = (files) => {
  const dropzone = document.getElementById("hero-image-dropzone");
  const fileInput = document.getElementById("hero-image-files");
  if (!(dropzone instanceof HTMLElement) || !(fileInput instanceof HTMLInputElement)) {
    return;
  }

  const incomingFiles = Array.from(files).filter((file) => file.type.startsWith("image/"));
  const dataTransfer = new DataTransfer();

  incomingFiles.forEach((file) => {
    dataTransfer.items.add(file);
  });

  fileInput.files = dataTransfer.files;
  renderHeroUploadPreview(Array.from(fileInput.files));
  if (incomingFiles.length > 0) {
    dropzone.classList.remove("is-active");
  }
};

const initHeroImageUpload = () => {
  const dropzone = document.getElementById("hero-image-dropzone");
  const picker = document.getElementById("hero-image-picker");
  const fileInput = document.getElementById("hero-image-files");
  if (
    !(dropzone instanceof HTMLElement) ||
    !(picker instanceof HTMLElement) ||
    !(fileInput instanceof HTMLInputElement)
  ) {
    return;
  }

  const isImageFile = (file) => file.type.startsWith("image/");
  const handleFiles = (files) => {
    const imageFiles = Array.from(files).filter(isImageFile);
    if (imageFiles.length === 0) {
      renderHeroUploadPreview([]);
      return;
    }
    applyHeroImageFiles(imageFiles);
  };

  const openPicker = () => {
    if (typeof fileInput.showPicker === "function") {
      try {
        fileInput.showPicker();
        return;
      } catch {
        // showPicker can throw when a browser blocks programmatic invocation.
      }
    }
    fileInput.click();
  };

  if (!(picker instanceof HTMLLabelElement)) {
    picker.addEventListener("click", (event) => {
      event.preventDefault();
      openPicker();
    });
  }

  fileInput.addEventListener("change", () => {
    const files = Array.from(fileInput.files);
    if (files.length === 0) {
      return;
    }
    handleFiles(files);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.add("is-active");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("is-active");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    if (!(event.dataTransfer instanceof DataTransfer)) {
      return;
    }
    handleFiles(event.dataTransfer.files);
  });
};

const renderMemberPhotoPreview = (file) => {
  const preview = document.getElementById("member-photo-preview");
  if (!(preview instanceof HTMLElement)) {
    return;
  }

  if (!(file instanceof File)) {
    preview.innerHTML = '<p class="meta-line">선택된 파일 없음</p>';
    return;
  }

  const imageUrl = URL.createObjectURL(file);
  preview.innerHTML = `
    <div class="member-photo-upload-preview">
      <img src="${imageUrl}" alt="선택한 멤버 사진 미리보기" />
      <p class="meta-line">${file.name} (${Math.ceil(file.size / 1024)}KB)</p>
    </div>
  `;

  const previewImage = preview.querySelector("img");
  if (previewImage instanceof HTMLImageElement) {
    previewImage.onload = () => {
      URL.revokeObjectURL(imageUrl);
    };
  }
};

const applyMemberPhotoFile = (file) => {
  const fileInput = document.getElementById("member-photo-file");
  const dropzone = document.getElementById("member-photo-dropzone");
  if (!(fileInput instanceof HTMLInputElement) || !(dropzone instanceof HTMLElement)) {
    return;
  }

  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  fileInput.files = dataTransfer.files;
  renderMemberPhotoPreview(file);
  dropzone.classList.remove("is-active");
};

const initMemberPhotoUpload = () => {
  const dropzone = document.getElementById("member-photo-dropzone");
  const picker = document.getElementById("member-photo-picker");
  const fileInput = document.getElementById("member-photo-file");
  if (
    !(dropzone instanceof HTMLElement) ||
    !(picker instanceof HTMLElement) ||
    !(fileInput instanceof HTMLInputElement)
  ) {
    return;
  }

  const isImageFile = (file) => file.type.startsWith("image/");
  const handleIncomingFiles = (files) => {
    const firstImageFile = Array.from(files).find(isImageFile);
    if (!(firstImageFile instanceof File)) {
      renderMemberPhotoPreview(null);
      return;
    }
    applyMemberPhotoFile(firstImageFile);
  };

  const openPicker = () => {
    if (typeof fileInput.showPicker === "function") {
      try {
        fileInput.showPicker();
        return;
      } catch {
        // showPicker can throw when a browser blocks programmatic invocation.
      }
    }
    fileInput.click();
  };

  if (!(picker instanceof HTMLLabelElement)) {
    picker.addEventListener("click", (event) => {
      event.preventDefault();
      openPicker();
    });
  }

  fileInput.addEventListener("change", () => {
    handleIncomingFiles(fileInput.files || []);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.add("is-active");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("is-active");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    if (!(event.dataTransfer instanceof DataTransfer)) {
      return;
    }
    handleIncomingFiles(event.dataTransfer.files);
  });
};

const initHeroImageDeleteSummary = () => {
  const summary = document.getElementById("hero-image-delete-summary");
  if (!(summary instanceof HTMLElement)) {
    return;
  }

  const checkboxes = Array.from(
    document.querySelectorAll('#hero-image-preview input[name="hero_image_remove_urls"]')
  ).filter((checkbox) => checkbox instanceof HTMLInputElement && !checkbox.disabled);

  const updateSummary = () => {
    const selectedCount = checkboxes.filter(
      (checkbox) => checkbox.checked
    ).length;
    summary.textContent = `삭제 대상: ${selectedCount}개`;
  };

  if (checkboxes.length === 0) {
    summary.textContent = "삭제 대상: 0개";
    return;
  }

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateSummary);
  });
  updateSummary();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAdminFormHelpers);
  document.addEventListener("DOMContentLoaded", initHeroImageUpload);
  document.addEventListener("DOMContentLoaded", initMemberPhotoUpload);
  document.addEventListener("DOMContentLoaded", initHeroImageDeleteSummary);
} else {
  initAdminFormHelpers();
  initHeroImageUpload();
  initMemberPhotoUpload();
  initHeroImageDeleteSummary();
}
