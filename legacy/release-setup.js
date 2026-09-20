const releaseForm = document.getElementById("releaseForm");
const supportOptions = document.querySelectorAll(".support-option");
const releaseTypeError = document.getElementById("releaseTypeError");
const backButton = document.getElementById("backButton");
const exitButton = document.getElementById("exitButton");

const selectedSupport = new Set();

loadReleaseSetup();

supportOptions.forEach((option) => {
  option.addEventListener("click", () => {
    const supportType = option.dataset.support;

    if (selectedSupport.has(supportType)) {
      selectedSupport.delete(supportType);
      option.classList.remove("selected");
    } else {
      selectedSupport.add(supportType);
      option.classList.add("selected");
    }
  });
});

document.querySelectorAll('input[name="releaseType"]').forEach((input) => {
  input.addEventListener("change", () => {
    releaseTypeError.textContent = "";
  });
});

releaseForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const releaseType = document.querySelector(
    'input[name="releaseType"]:checked'
  );

  if (!releaseType) {
    releaseTypeError.textContent =
      "Please choose what you are releasing.";

    window.scrollTo({
      top: 500,
      behavior: "smooth"
    });

    return;
  }

  saveReleaseSetup(true);

  window.location.href = "portal.html";
});

backButton.addEventListener("click", () => {
  window.history.back();
});

exitButton.addEventListener("click", () => {
  saveReleaseSetup(false);
  window.location.href = "index.html";
});

function saveReleaseSetup(completed) {
  const releaseType = document.querySelector(
    'input[name="releaseType"]:checked'
  );

  const releaseStage = document.querySelector(
    'input[name="releaseStage"]:checked'
  );

  const releaseData = {
    releaseType: releaseType ? releaseType.value : "",
    releaseTitle: document.getElementById("releaseTitle").value.trim(),
    releaseDate: document.getElementById("releaseDate").value,
    releaseStage: releaseStage ? releaseStage.value : "",
    supportNeeded: Array.from(selectedSupport),
    completed: completed
  };

  localStorage.setItem(
    "soundbridgeReleaseSetup",
    JSON.stringify(releaseData)
  );
}

function loadReleaseSetup() {
  const savedData = JSON.parse(
    localStorage.getItem("soundbridgeReleaseSetup")
  );

  if (!savedData) {
    return;
  }

  document.getElementById("releaseTitle").value =
    savedData.releaseTitle || "";

  document.getElementById("releaseDate").value =
    savedData.releaseDate || "";

  if (savedData.releaseType) {
    const releaseTypeInput = document.querySelector(
      `input[name="releaseType"][value="${savedData.releaseType}"]`
    );

    if (releaseTypeInput) {
      releaseTypeInput.checked = true;
    }
  }

  if (savedData.releaseStage) {
    const releaseStageInput = document.querySelector(
      `input[name="releaseStage"][value="${savedData.releaseStage}"]`
    );

    if (releaseStageInput) {
      releaseStageInput.checked = true;
    }
  }

  savedData.supportNeeded?.forEach((supportType) => {
    selectedSupport.add(supportType);

    const matchingOption = document.querySelector(
      `.support-option[data-support="${supportType}"]`
    );

    matchingOption?.classList.add("selected");
  });
}