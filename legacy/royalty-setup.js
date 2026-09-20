const royaltyForm = document.getElementById("royaltyForm");
const royaltyOptions = document.querySelectorAll(".royalty-option");
const platformOptions = document.querySelectorAll(".platform-option");
const royaltyError = document.getElementById("royaltyError");
const backButton = document.getElementById("backButton");
const exitButton = document.getElementById("exitButton");

const selectedRoyaltyNeeds = new Set();
const selectedPlatforms = new Set();

loadSavedSetup();

royaltyOptions.forEach((option) => {
  option.addEventListener("click", () => {
    const value = option.dataset.value;

    if (selectedRoyaltyNeeds.has(value)) {
      selectedRoyaltyNeeds.delete(value);
      option.classList.remove("selected");
    } else {
      selectedRoyaltyNeeds.add(value);
      option.classList.add("selected");
    }

    royaltyError.textContent = "";
  });
});

platformOptions.forEach((option) => {
  option.addEventListener("click", () => {
    const platform = option.dataset.platform;

    if (selectedPlatforms.has(platform)) {
      selectedPlatforms.delete(platform);
      option.classList.remove("selected");
    } else {
      selectedPlatforms.add(platform);
      option.classList.add("selected");
    }
  });
});

royaltyForm.addEventListener("submit", (event) => {
  event.preventDefault();

  if (selectedRoyaltyNeeds.size === 0) {
    royaltyError.textContent =
      "Please select at least one royalty service.";

    document
      .querySelector(".setup-section")
      .scrollIntoView({ behavior: "smooth" });

    return;
  }

  saveRoyaltySetup();

  window.location.href = getNextPage();
});

backButton.addEventListener("click", () => {
  window.history.back();
});

exitButton.addEventListener("click", () => {
  saveRoyaltySetup();
  window.location.href = "index.html";
});

function saveRoyaltySetup() {
  const selectedIncomeSource = document.querySelector(
    'input[name="incomeSource"]:checked'
  );

  const royaltySetup = {
    services: Array.from(selectedRoyaltyNeeds),
    platforms: Array.from(selectedPlatforms),
    incomeSource: selectedIncomeSource
      ? selectedIncomeSource.value
      : "",
    completed: selectedRoyaltyNeeds.size > 0
  };

  localStorage.setItem(
    "soundbridgeRoyaltySetup",
    JSON.stringify(royaltySetup)
  );
}

function loadSavedSetup() {
  const savedSetup = JSON.parse(
    localStorage.getItem("soundbridgeRoyaltySetup")
  );

  if (!savedSetup) {
    return;
  }

  savedSetup.services?.forEach((service) => {
    selectedRoyaltyNeeds.add(service);

    const matchingOption = document.querySelector(
      `.royalty-option[data-value="${service}"]`
    );

    matchingOption?.classList.add("selected");
  });

  savedSetup.platforms?.forEach((platform) => {
    selectedPlatforms.add(platform);

    const matchingPlatform = document.querySelector(
      `.platform-option[data-platform="${platform}"]`
    );

    matchingPlatform?.classList.add("selected");
  });

  if (savedSetup.incomeSource) {
    const savedIncomeOption = document.querySelector(
      `input[name="incomeSource"][value="${savedSetup.incomeSource}"]`
    );

    if (savedIncomeOption) {
      savedIncomeOption.checked = true;
    }
  }
}

function getNextPage() {
  const goals =
    JSON.parse(localStorage.getItem("soundbridgeGoals")) || [];

  if (goals.includes("Plan a release")) {
    return "release-setup.html";
  }

  return "portal.html";
}