const form = document.getElementById("upload-form");
const fileInput = document.getElementById("statement-file");
const fileName = document.getElementById("file-name");
const dropzone = document.getElementById("dropzone");
const convertButton = document.getElementById("convert-button");
const statusBadge = document.getElementById("status-badge");
const statusMessage = document.getElementById("status-message");
const downloadLink = document.getElementById("download-link");

let currentDownloadUrl = null;

function setStatus(mode, message) {
  statusBadge.className = `status-badge ${mode}`;
  statusBadge.textContent = mode;
  statusMessage.textContent = message;
}

function updateSelectedFile() {
  const file = fileInput.files?.[0];
  fileName.textContent = file ? file.name : "No file selected";
  downloadLink.classList.add("hidden");
  if (currentDownloadUrl) {
    URL.revokeObjectURL(currentDownloadUrl);
    currentDownloadUrl = null;
  }
  setStatus("idle", file ? "Ready to convert." : "Waiting for a file.");
}

fileInput.addEventListener("change", updateSelectedFile);

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("active");
  });
});

dropzone.addEventListener("drop", (event) => {
  const files = event.dataTransfer?.files;
  if (!files || files.length === 0) {
    return;
  }
  fileInput.files = files;
  updateSelectedFile();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("error", "Select a statement file first.");
    return;
  }

  convertButton.disabled = true;
  setStatus("working", "Uploading and converting statement...");

  const payload = new FormData();
  payload.append("file", file);

  try {
    const response = await fetch("/api/convert", {
      method: "POST",
      body: payload,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const message = errorBody.detail || "Conversion failed.";
      throw new Error(message);
    }

    const blob = await response.blob();
    currentDownloadUrl = URL.createObjectURL(blob);
    downloadLink.href = currentDownloadUrl;
    downloadLink.classList.remove("hidden");
    setStatus("success", "Conversion complete. Your normalized CSV is ready.");
  } catch (error) {
    setStatus("error", error instanceof Error ? error.message : "Conversion failed.");
  } finally {
    convertButton.disabled = false;
  }
});