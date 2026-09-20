// Select the important HTML elements.

const genreList =
  document.getElementById("genreList");

const selectedCount =
  document.getElementById("selectedCount");

const selectedPreview =
  document.getElementById("selectedPreview");

const continueButton =
  document.getElementById("continueButton");

const exitButton =
  document.getElementById("exitButton");

const roleName =
  document.getElementById("roleName");

const genreError =
  document.getElementById("genreError");

const customGenreInput =
  document.getElementById("customGenre");

const addGenreButton =
  document.getElementById("addGenreButton");


// Users can select no more than five genres.

const maximumGenres = 5;


// This array stores the selected genres.

let selectedGenres = [];


// Display the role selected earlier.

const savedRole =
  localStorage.getItem("soundbridgeRole");

if (savedRole) {
  roleName.textContent = savedRole;
}


// Get all current genre buttons.

function getGenreButtons() {
  return document.querySelectorAll(".genre-button");
}


// Update the visual state of the page.

function updateGenreDisplay() {
  selectedCount.textContent = selectedGenres.length;

  continueButton.disabled =
    selectedGenres.length === 0;

  if (selectedGenres.length === 0) {
    selectedPreview.textContent =
      "No genres selected";
  } else {
    selectedPreview.textContent =
      selectedGenres.join(" · ");
  }

  getGenreButtons().forEach(function (button) {
    const genre = button.dataset.genre;

    const isSelected =
      selectedGenres.includes(genre);

    if (
      selectedGenres.length === maximumGenres &&
      !isSelected
    ) {
      button.classList.add("limit-reached");
    } else {
      button.classList.remove("limit-reached");
    }
  });
}


// Select or remove a genre.

function handleGenreSelection(button) {
  const genre = button.dataset.genre;

  const genreIsSelected =
    selectedGenres.includes(genre);

  if (genreIsSelected) {
    selectedGenres =
      selectedGenres.filter(function (item) {
        return item !== genre;
      });

    button.classList.remove("selected");

    genreError.textContent = "";

    updateGenreDisplay();

    return;
  }

  if (selectedGenres.length >= maximumGenres) {
    genreError.textContent =
      "You can select a maximum of five genres.";

    return;
  }

  selectedGenres.push(genre);

  button.classList.add("selected");

  genreError.textContent = "";

  updateGenreDisplay();
}


// Add click events to the original buttons.

getGenreButtons().forEach(function (button) {
  button.addEventListener("click", function () {
    handleGenreSelection(button);
  });
});


// Add a custom genre.

addGenreButton.addEventListener("click", function () {
  const customGenre =
    customGenreInput.value.trim();

  if (customGenre === "") {
    genreError.textContent =
      "Enter a genre before adding it.";

    return;
  }

  if (selectedGenres.length >= maximumGenres) {
    genreError.textContent =
      "You can select a maximum of five genres.";

    return;
  }

  const genreAlreadyExists =
    selectedGenres.some(function (genre) {
      return (
        genre.toLowerCase() ===
        customGenre.toLowerCase()
      );
    });

  if (genreAlreadyExists) {
    genreError.textContent =
      "You already selected that genre.";

    return;
  }

  const newButton =
    document.createElement("button");

  newButton.type = "button";

  newButton.className =
    "genre-button selected";

  newButton.dataset.genre =
    customGenre;

  newButton.textContent =
    customGenre;

  genreList.appendChild(newButton);

  selectedGenres.push(customGenre);

  newButton.addEventListener("click", function () {
    handleGenreSelection(newButton);
  });

  customGenreInput.value = "";

  genreError.textContent = "";

  updateGenreDisplay();
});


// Allow the Enter key to add a custom genre.

customGenreInput.addEventListener(
  "keydown",
  function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      addGenreButton.click();
    }
  }
);


// Continue to the profile details page.

continueButton.addEventListener("click", function () {
  if (selectedGenres.length === 0) {
    genreError.textContent =
      "Select at least one genre.";

    return;
  }

  localStorage.setItem(
    "soundbridgeGenres",
    JSON.stringify(selectedGenres)
  );

  window.location.href = getNextPage();
});


// Save and return to the landing page.

exitButton.addEventListener("click", function () {
  localStorage.setItem(
    "soundbridgeGenres",
    JSON.stringify(selectedGenres)
  );

  window.location.href = "index.html";
});


// Restore previously saved genres.

const savedGenres =
  localStorage.getItem("soundbridgeGenres");

if (savedGenres) {
  selectedGenres =
    JSON.parse(savedGenres);

  selectedGenres.forEach(function (savedGenre) {
    let matchingButton = null;

    getGenreButtons().forEach(function (button) {
      if (button.dataset.genre === savedGenre) {
        matchingButton = button;
      }
    });

    /*
      If the saved genre is custom, recreate its button.
    */

    if (!matchingButton) {
      const customButton =
        document.createElement("button");

      customButton.type = "button";

      customButton.className =
        "genre-button";

      customButton.dataset.genre =
        savedGenre;

      customButton.textContent =
        savedGenre;

      genreList.appendChild(customButton);

      customButton.addEventListener(
        "click",
        function () {
          handleGenreSelection(customButton);
        }
      );

      matchingButton = customButton;
    }

    matchingButton.classList.add("selected");
  });

  updateGenreDisplay();

  function getNextPage() {
  const goals =
    JSON.parse(localStorage.getItem("soundbridgeGoals")) || [];

  const wantsRoyaltyTools =
    goals.includes("Understand royalties") ||
    goals.includes("Track music income");

  const wantsReleasePlanning =
    goals.includes("Plan a release");

  if (wantsRoyaltyTools) {
    return "royalty-setup.html";
  }

  if (wantsReleasePlanning) {
    return "release-setup.html";
  }

  return "portal.html";
}
}