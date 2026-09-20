const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const browseButton = document.getElementById("browseButton");
const filePreview = document.getElementById("filePreview");
const fileName = document.getElementById("fileName");
const fileDetails = document.getElementById("fileDetails");
const fileTypeIcon = document.getElementById("fileTypeIcon");
const removeFileButton = document.getElementById("removeFile");
const analyseButton = document.getElementById("analyseButton");
const errorMessage = document.getElementById("errorMessage");

const statementSource =
  document.getElementById("statementSource");

const statementPeriod =
  document.getElementById("statementPeriod");

const statementCurrency =
  document.getElementById("statementCurrency");

const analysisEmpty =
  document.getElementById("analysisEmpty");

const analysisResults =
  document.getElementById("analysisResults");

const saveStatement =
  document.getElementById("saveStatement");

const toast = document.getElementById("toast");

let selectedFile = null;
let currentStatementRecord = null;

browseButton.addEventListener("click", (event) => {
  event.stopPropagation();
  fileInput.click();
});

dropZone.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];

  if (file) {
    handleFile(file);
  }
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragging");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");

  const file = event.dataTransfer.files[0];

  if (file) {
    handleFile(file);
  }
});

removeFileButton.addEventListener("click", () => {
  selectedFile = null;
  currentStatementRecord = null;
  fileInput.value = "";

  filePreview.classList.remove("visible");
  analyseButton.disabled = true;
  errorMessage.textContent = "";

  analysisResults.classList.remove("visible");
  analysisEmpty.style.display = "flex";
});

analyseButton.addEventListener("click", () => {
  if (!selectedFile) {
    errorMessage.textContent =
      "Please select a royalty statement.";

    return;
  }

  errorMessage.textContent = "";

  const extension = getFileExtension(selectedFile.name);

  currentStatementRecord = {
    fileName: selectedFile.name,
    fileType: extension.toUpperCase(),
    fileSize: selectedFile.size,
    source: statementSource.value || "Not provided",
    period: statementPeriod.value || "Not provided",
    currency: statementCurrency.value,
    addedAt: new Date().toISOString()
  };

  document.getElementById("resultFileName").textContent =
    currentStatementRecord.fileName;

  document.getElementById("resultFileType").textContent =
    currentStatementRecord.fileType;

  document.getElementById("resultSource").textContent =
    currentStatementRecord.source;

  document.getElementById("resultPeriod").textContent =
    formatPeriod(currentStatementRecord.period);

  document.getElementById("resultCurrency").textContent =
    currentStatementRecord.currency;

  analysisEmpty.style.display = "none";
  analysisResults.classList.add("visible");
});

saveStatement.addEventListener("click", () => {
  if (!currentStatementRecord) {
    return;
  }

  const existingRecords =
    JSON.parse(
      localStorage.getItem("soundbridgeRoyaltyStatements")
    ) || [];

  existingRecords.unshift(currentStatementRecord);

  localStorage.setItem(
    "soundbridgeRoyaltyStatements",
    JSON.stringify(existingRecords)
  );

  toast.classList.add("visible");

  setTimeout(() => {
    toast.classList.remove("visible");
  }, 2500);
});

function handleFile(file) {
  const allowedExtensions = ["csv", "xlsx", "xls", "pdf"];
  const extension = getFileExtension(file.name);
  const maximumSize = 10 * 1024 * 1024;

  if (!allowedExtensions.includes(extension)) {
    errorMessage.textContent =
      "Please choose a CSV, XLSX, XLS or PDF file.";

    return;
  }

  if (file.size > maximumSize) {
    errorMessage.textContent =
      "The selected file must be smaller than 10MB.";

    return;
  }

  selectedFile = file;
  currentStatementRecord = null;

  fileName.textContent = file.name;
  fileDetails.textContent = formatFileSize(file.size);
  fileTypeIcon.textContent = extension.toUpperCase();

  filePreview.classList.add("visible");
  analyseButton.disabled = false;
  errorMessage.textContent = "";

  analysisResults.classList.remove("visible");
  analysisEmpty.style.display = "flex";
}

function getFileExtension(name) {
  return name.split(".").pop().toLowerCase();
}

function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} bytes`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatPeriod(period) {
  if (!period || period === "Not provided") {
    return "Not provided";
  }

  const [year, month] = period.split("-");

  const date = new Date(Number(year), Number(month) - 1);

  return date.toLocaleDateString("en-NG", {
    month: "long",
    year: "numeric"
  });
}