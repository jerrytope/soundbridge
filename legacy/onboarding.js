// Get the role cards from the HTML page.
const roleCards = document.querySelectorAll(".role-card");

// Get the Continue button.
const continueButton =
  document.getElementById("continueButton");

// Get the area that displays the selected role.
const selectedRoleText =
  document.getElementById("selectedRoleText");

// Get the error message area.
const roleError =
  document.getElementById("roleError");

// Get the Save and Exit button.
const exitButton =
  document.getElementById("exitButton");


// This variable stores the role selected by the user.
let selectedRole = "";


// Run this code when a role card is clicked.
roleCards.forEach(function (card) {
  card.addEventListener("click", function () {
    // Remove selected styling from every role.
    roleCards.forEach(function (otherCard) {
      otherCard.classList.remove("selected");
    });

    // Add selected styling to the clicked role.
    card.classList.add("selected");

    // Read the role from the data-role attribute.
    selectedRole = card.dataset.role;

    // Show the selected role at the bottom.
    selectedRoleText.textContent = selectedRole;

    // Enable the Continue button.
    continueButton.disabled = false;

    // Remove any previous error message.
    roleError.textContent = "";
  });
});


// Run this when the user clicks Continue.
continueButton.addEventListener("click", function () {
  if (selectedRole === "") {
    roleError.textContent =
      "Please select your main music role.";

    return;
  }

  /*
    Save the selected role in the browser.

    localStorage allows another page to access the information.
  */
  localStorage.setItem(
    "soundbridgeRole",
    selectedRole
  );

  /*
    We will create this page in the next step.
  */
  window.location.href = "goals.html";
});


// Run this when the user clicks Save and Exit.
exitButton.addEventListener("click", function () {
  if (selectedRole !== "") {
    localStorage.setItem(
      "soundbridgeRole",
      selectedRole
    );
  }

  window.location.href = "index.html";
});


// Restore a previously selected role.
const savedRole =
  localStorage.getItem("soundbridgeRole");

if (savedRole) {
  selectedRole = savedRole;

  selectedRoleText.textContent = savedRole;
  continueButton.disabled = false;

  roleCards.forEach(function (card) {
    if (card.dataset.role === savedRole) {
      card.classList.add("selected");
    }
  });
}