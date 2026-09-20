const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");
const menuButton = document.getElementById("menuButton");
const closeSidebar = document.getElementById("closeSidebar");

const modalOverlay = document.getElementById("modalOverlay");
const modalClose = document.getElementById("modalClose");
const modalLater = document.getElementById("modalLater");
const modalTitle = document.getElementById("modalTitle");
const modalMessage = document.getElementById("modalMessage");

const toast = document.getElementById("toast");

const savedProfile =
  JSON.parse(localStorage.getItem("soundbridgeProfile")) || {};

const savedGoals =
  JSON.parse(localStorage.getItem("soundbridgeGoals")) || [];

const savedRoyalties =
  JSON.parse(localStorage.getItem("soundbridgeRoyaltySetup")) || {};

const savedRelease =
  JSON.parse(localStorage.getItem("soundbridgeReleaseSetup")) || {};

const savedRole =
  localStorage.getItem("soundbridgeRole") || "SoundBridge member";

loadDashboard();
createGoalChips();
createNextActions();
personalizeSections();
loadReleaseInformation();

menuButton.addEventListener("click", openSidebar);
closeSidebar.addEventListener("click", closeSidebarMenu);
sidebarOverlay.addEventListener("click", closeSidebarMenu);

document
  .getElementById("upgradeButton")
  .addEventListener("click", () => {
    openProModal();
  });

document
  .getElementById("sidebarUpgradeButton")
  .addEventListener("click", () => {
    openProModal();
  });

document.querySelectorAll(".assistant-card").forEach((assistant) => {
  assistant.addEventListener("click", () => {
    const assistantName = assistant.dataset.assistant;

    modalTitle.textContent = `Unlock your ${assistantName}`;

    modalMessage.textContent =
      `${assistantName} is part of SoundBridge Pro. ` +
      "Upgrade to access personalised AI guidance.";

    modalOverlay.classList.add("open");
  });
});

document.querySelectorAll("[data-demo]").forEach((button) => {
  button.addEventListener("click", () => {
    const feature = button.dataset.demo;

    showToast(
      `${feature} is ready for its next frontend page.`
    );
  });
});

document.querySelectorAll(".navigation-link").forEach((link) => {
  link.addEventListener("click", (event) => {
    const destination = link.getAttribute("href");
    const linkText = link.textContent
      .replace("PRO", "")
      .trim();

    if (destination === "#") {
      event.preventDefault();

      showToast(`${linkText} page will be built next.`);
    }

    closeSidebarMenu();
  });
});

modalClose.addEventListener("click", closeProModal);
modalLater.addEventListener("click", closeProModal);

modalOverlay.addEventListener("click", (event) => {
  if (event.target === modalOverlay) {
    closeProModal();
  }
});

document
  .querySelector(".modal-upgrade-button")
  .addEventListener("click", () => {
    closeProModal();

    showToast(
      "The Pro subscription checkout will be connected later."
    );
  });

function loadDashboard() {
  const displayName =
    savedProfile.displayName ||
    savedProfile.name ||
    "Creator";

  const firstName = displayName.split(" ")[0];

  document.getElementById("welcomeName").textContent = firstName;
  document.getElementById("headerName").textContent = displayName;
  document.getElementById("headerRole").textContent = savedRole;

  document.getElementById("profileAvatar").textContent =
    getInitials(displayName);

  document.getElementById("currentDate").textContent =
    new Date().toLocaleDateString("en-NG", {
      weekday: "long",
      day: "numeric",
      month: "long"
    });

  const completion = calculateProfileCompletion();

  document.getElementById("profileCompletion").textContent =
    `${completion}%`;

  document.getElementById("profileProgressBar").style.width =
    `${completion}%`;

  document.getElementById("profileRingValue").textContent =
    `${completion}%`;

  document.querySelector(".profile-ring").style.background =
    `conic-gradient(
      var(--purple) ${completion}%,
      #26232c 0
    )`;
}

function getInitials(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function calculateProfileCompletion() {
  const profileFields = [
    savedProfile.displayName || savedProfile.name,
    savedProfile.username,
    savedProfile.headline,
    savedProfile.country,
    savedProfile.city,
    savedProfile.experience,
    savedProfile.bio
  ];

  const completedFields = profileFields.filter(Boolean).length;
  const totalFields = profileFields.length;

  return Math.round((completedFields / totalFields) * 100);
}

function createGoalChips() {
  const goalList = document.getElementById("goalList");

  goalList.innerHTML = "";

  if (savedGoals.length === 0) {
    goalList.innerHTML =
      '<span class="goal-chip">No goal selected</span>';

    return;
  }

  savedGoals.forEach((goal) => {
    const chip = document.createElement("span");

    chip.className = "goal-chip";
    chip.textContent = goal;

    goalList.appendChild(chip);
  });
}

function createNextActions() {
  const actionList = document.getElementById("actionList");

  const actions = [];

  if (
    savedGoals.includes("Find collaborators") ||
    savedGoals.includes("Grow my audience")
  ) {
    actions.push({
      title: "Discover creators who match your sound",
      description:
        "Explore artists, producers and music professionals."
    });
  }

  if (savedGoals.includes("Discover opportunities")) {
    actions.push({
      title: "Review recommended opportunities",
      description:
        "Find grants, showcases, jobs and industry programmes."
    });
  }

  if (
    savedGoals.includes("Understand royalties") ||
    savedGoals.includes("Track music income")
  ) {
    actions.push({
      title: "Set up your royalty calculator",
      description:
        "Enter streams or upload a statement to estimate earnings."
    });
  }

  if (savedGoals.includes("Plan a release")) {
    actions.push({
      title: "Continue your release campaign",
      description:
        "Review your timeline, tasks and campaign strategy."
    });
  }

  actions.push({
    title: "Complete your professional profile",
    description:
      "Add credits, music, skills and career highlights."
  });

  actions.slice(0, 4).forEach((action, index) => {
    const actionItem = document.createElement("div");

    actionItem.className = "action-item";

    actionItem.innerHTML = `
      <span class="action-number">
        ${String(index + 1).padStart(2, "0")}
      </span>

      <span class="action-copy">
        <strong>${action.title}</strong>
        <small>${action.description}</small>
      </span>

      <span class="action-arrow">→</span>
    `;

    actionItem.addEventListener("click", () => {
      showToast(`${action.title} page will be connected next.`);
    });

    actionList.appendChild(actionItem);
  });
}

function personalizeSections() {
  const royaltyGoals = [
    "Understand royalties",
    "Track music income"
  ];

  const hasRoyaltyGoal = royaltyGoals.some((goal) =>
    savedGoals.includes(goal)
  );

  const hasReleaseGoal =
    savedGoals.includes("Plan a release");

  if (!hasRoyaltyGoal && !savedRoyalties.completed) {
    document
      .getElementById("royaltySection")
      .classList.add("hidden");
  }

  if (!hasReleaseGoal && !savedRelease.completed) {
    document
      .getElementById("releaseSection")
      .classList.add("hidden");
  }

  const message = document.getElementById("welcomeMessage");

  if (hasRoyaltyGoal) {
    message.textContent =
      "Let’s organise your music income and understand your rights.";
  } else if (hasReleaseGoal) {
    message.textContent =
      "Your personalised release workspace is ready.";
  } else if (savedGoals.includes("Find collaborators")) {
    message.textContent =
      "Let’s find creators who match your sound and direction.";
  }
}

function loadReleaseInformation() {
  if (!savedRelease.releaseTitle) {
    return;
  }

  document.getElementById("dashboardReleaseTitle").textContent =
    savedRelease.releaseTitle;

  const type = savedRelease.releaseType || "Release";
  const stage = savedRelease.releaseStage || "Planning";

  let releaseText = `${type} • ${stage}`;

  if (savedRelease.releaseDate) {
    const formattedDate = new Date(
      `${savedRelease.releaseDate}T00:00:00`
    ).toLocaleDateString("en-NG", {
      day: "numeric",
      month: "short",
      year: "numeric"
    });

    releaseText += ` • ${formattedDate}`;
  }

  document.getElementById(
    "dashboardReleaseInformation"
  ).textContent = releaseText;

  document.getElementById("releaseStatus").textContent =
    stage.toUpperCase();
}

function openSidebar() {
  sidebar.classList.add("open");
  sidebarOverlay.classList.add("open");
}

function closeSidebarMenu() {
  sidebar.classList.remove("open");
  sidebarOverlay.classList.remove("open");
}

function openProModal() {
  modalTitle.textContent = "Unlock your AI creative team";

  modalMessage.textContent =
    "Upgrade to access advanced AI guidance, royalty " +
    "intelligence and unlimited release planning.";

  modalOverlay.classList.add("open");
}

function closeProModal() {
  modalOverlay.classList.remove("open");
}

let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");

  clearTimeout(toastTimer);

  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 3000);
}