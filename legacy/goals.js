// Select the important HTML elements.

const goalCards =
  document.querySelectorAll(".goal-card");

const selectedCount =
  document.getElementById("selectedCount");

const continueButton =
  document.getElementById("continueButton");

const goalError =
  document.getElementById("goalError");

const exitButton =
  document.getElementById("exitButton");

const roleName =
  document.getElementById("roleName");


// The user can choose no more than three goals.

const maximumGoals = 3;


// This array stores all selected goals.

let selectedGoals = [];


// Display the role selected on the previous page.

const savedRole =
  localStorage.getItem("soundbridgeRole");

if (savedRole) {
  roleName.textContent = savedRole;
}


// This function updates the page after a goal changes.

function updateGoalDisplay() {
  selectedCount.textContent = selectedGoals.length;

  // The user needs to select at least one goal.
  continueButton.disabled = selectedGoals.length === 0;

  /*
    When three goals are selected, fade the other cards.
  */

  goalCards.forEach(function (card) {
    const cardGoal = card.dataset.goal;

    const cardIsSelected =
      selectedGoals.includes(cardGoal);

    if (
      selectedGoals.length === maximumGoals &&
      !cardIsSelected
    ) {
      card.classList.add("limit-reached");
    } else {
      card.classList.remove("limit-reached");
    }
  });
}


// Add click behaviour to every goal card.

goalCards.forEach(function (card) {
  card.addEventListener("click", function () {
    const selectedGoal = card.dataset.goal;

    const goalAlreadySelected =
      selectedGoals.includes(selectedGoal);

    /*
      If the goal is selected already, remove it.
    */

    if (goalAlreadySelected) {
      selectedGoals = selectedGoals.filter(
        function (goal) {
          return goal !== selectedGoal;
        }
      );

      card.classList.remove("selected");
      goalError.textContent = "";

      updateGoalDisplay();

      return;
    }

    /*
      Stop the user from selecting more than three.
    */

    if (selectedGoals.length >= maximumGoals) {
      goalError.textContent =
        "You can select a maximum of three goals.";

      return;
    }

    /*
      Add the new goal.
    */

    selectedGoals.push(selectedGoal);

    card.classList.add("selected");

    goalError.textContent = "";

    updateGoalDisplay();
  });
});


// Continue to the next onboarding stage.

continueButton.addEventListener("click", function () {
  if (selectedGoals.length === 0) {
    goalError.textContent =
      "Select at least one career goal.";

    return;
  }

  /*
    Arrays cannot be saved directly in localStorage.

    JSON.stringify converts the array into text.
  */

  localStorage.setItem(
    "soundbridgeGoals",
    JSON.stringify(selectedGoals)
  );

  window.location.href = "profile-setup.html";
});


// Save the selected goals and return to the landing page.

exitButton.addEventListener("click", function () {
  localStorage.setItem(
    "soundbridgeGoals",
    JSON.stringify(selectedGoals)
  );

  window.location.href = "index.html";
});


// Restore goals if the user previously selected them.

const savedGoals =
  localStorage.getItem("soundbridgeGoals");

if (savedGoals) {
  /*
    JSON.parse converts the stored text back into an array.
  */

  selectedGoals = JSON.parse(savedGoals);

  goalCards.forEach(function (card) {
    if (selectedGoals.includes(card.dataset.goal)) {
      card.classList.add("selected");
    }
  });

  updateGoalDisplay();
}