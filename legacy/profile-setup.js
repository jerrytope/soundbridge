// Select the form elements.

const profileForm =
  document.getElementById("profileForm");

const displayNameInput =
  document.getElementById("displayName");

const usernameInput =
  document.getElementById("username");

const headlineInput =
  document.getElementById("headline");

const countryInput =
  document.getElementById("country");

const cityInput =
  document.getElementById("city");

const experienceInput =
  document.getElementById("experience");

const biographyInput =
  document.getElementById("biography");

const biographyCount =
  document.getElementById("biographyCount");

const formError =
  document.getElementById("formError");

const exitButton =
  document.getElementById("exitButton");


// Select the profile preview elements.

const previewName =
  document.getElementById("previewName");

const previewHeadline =
  document.getElementById("previewHeadline");

const previewRole =
  document.getElementById("previewRole");

const previewLocation =
  document.getElementById("previewLocation");

const previewExperience =
  document.getElementById("previewExperience");

const profileInitials =
  document.getElementById("profileInitials");

const previewInitials =
  document.getElementById("previewInitials");


// Select the photo elements.

const photoInput =
  document.getElementById("photoInput");

const profileImage =
  document.getElementById("profileImage");

const previewImage =
  document.getElementById("previewImage");

const removePhotoButton =
  document.getElementById("removePhotoButton");


// Select the next-step information.

const nextStepTitle =
  document.getElementById("nextStepTitle");

const nextStepDescription =
  document.getElementById("nextStepDescription");


// Load the role selected earlier.

const savedRole =
  localStorage.getItem("soundbridgeRole");

if (savedRole) {
  previewRole.textContent = savedRole;
}


// Load the selected goals.

const savedGoals =
  JSON.parse(
    localStorage.getItem("soundbridgeGoals")
  ) || [];


// Decide what should happen after the profile page.

function getNextDestination() {
  const needsGenreSetup =
    savedGoals.includes("Find collaborators") ||
    savedGoals.includes("Discover opportunities") ||
    savedGoals.includes("Grow my audience") ||
    savedGoals.includes("Plan a release");

  const needsRoyaltySetup =
    savedGoals.includes("Understand royalties") ||
    savedGoals.includes("Track music income");

  if (needsGenreSetup) {
    return "genres.html";
  }

  if (needsRoyaltySetup) {
    return "royalty-setup.html";
  }

  return "portal.html";
}


// Explain the next step in the preview.

function updateNextStepMessage() {
  const destination = getNextDestination();

  if (destination === "genres.html") {
    nextStepTitle.textContent =
      "Music preferences";

    nextStepDescription.textContent =
      "Next, choose genres so we can personalise collaborators and opportunities.";
  } else if (destination === "royalty-setup.html") {
    nextStepTitle.textContent =
      "Royalty setup";

    nextStepDescription.textContent =
      "Next, choose the royalty information you want to calculate or track.";
  } else {
    nextStepTitle.textContent =
      "Your SoundBridge portal";

    nextStepDescription.textContent =
      "Next, enter your personalised professional dashboard.";
  }
}

updateNextStepMessage();


// Create initials from a name.

function createInitials(name) {
  const words = name
    .trim()
    .split(" ")
    .filter(function (word) {
      return word !== "";
    });

  if (words.length === 0) {
    return "SB";
  }

  const firstInitial =
    words[0].charAt(0);

  const secondInitial =
    words.length > 1
      ? words[words.length - 1].charAt(0)
      : "";

  return (
    firstInitial + secondInitial
  ).toUpperCase();
}


// Update the name preview.

displayNameInput.addEventListener("input", function () {
  const name = displayNameInput.value.trim();

  previewName.textContent =
    name || "Your stage name";

  const initials = createInitials(name);

  profileInitials.textContent = initials;
  previewInitials.textContent = initials;
});


// Update the headline preview.

headlineInput.addEventListener("input", function () {
  previewHeadline.textContent =
    headlineInput.value.trim() ||
    "Your professional headline will appear here.";
});


// Update the location preview.

function updateLocation() {
  const country = countryInput.value;
  const city = cityInput.value.trim();

  if (city && country) {
    previewLocation.textContent =
      city + ", " + country;
  } else if (city) {
    previewLocation.textContent = city;
  } else if (country) {
    previewLocation.textContent = country;
  } else {
    previewLocation.textContent =
      "Not added";
  }
}

countryInput.addEventListener(
  "change",
  updateLocation
);

cityInput.addEventListener(
  "input",
  updateLocation
);


// Update experience preview.

experienceInput.addEventListener(
  "change",
  function () {
    previewExperience.textContent =
      experienceInput.value ||
      "Not added";
  }
);


// Count biography characters.

biographyInput.addEventListener(
  "input",
  function () {
    biographyCount.textContent =
      biographyInput.value.length;
  }
);


// Preview the selected photograph.

photoInput.addEventListener(
  "change",
  function () {
    const selectedFile =
      photoInput.files[0];

    if (!selectedFile) {
      return;
    }

    const reader = new FileReader();

    reader.addEventListener(
      "load",
      function () {
        const imageData = reader.result;

        profileImage.src = imageData;
        previewImage.src = imageData;

        profileImage.style.display = "block";
        previewImage.style.display = "block";

        profileInitials.style.display = "none";
        previewInitials.style.display = "none";

        /*
          This is only stored temporarily in the browser.

          Large images may be too big for localStorage, so the final
          backend will store profile images properly.
        */
      }
    );

    reader.readAsDataURL(selectedFile);
  }
);


// Remove the profile photograph.

removePhotoButton.addEventListener(
  "click",
  function () {
    photoInput.value = "";

    profileImage.src = "";
    previewImage.src = "";

    profileImage.style.display = "none";
    previewImage.style.display = "none";

    profileInitials.style.display = "block";
    previewInitials.style.display = "block";
  }
);


// Clean the username while the user types.

usernameInput.addEventListener(
  "input",
  function () {
    usernameInput.value =
      usernameInput.value
        .toLowerCase()
        .replace(/\s+/g, "")
        .replace(/[^a-z0-9_.]/g, "");
  }
);


// Save the form information.

function saveProfile() {
  const profile = {
    displayName: displayNameInput.value.trim(),
    username: usernameInput.value.trim(),
    headline: headlineInput.value.trim(),
    country: countryInput.value,
    city: cityInput.value.trim(),
    experience: experienceInput.value,
    biography: biographyInput.value.trim()
  };

  localStorage.setItem(
    "soundbridgeProfile",
    JSON.stringify(profile)
  );
}


// Submit the profile form.

profileForm.addEventListener(
  "submit",
  function (event) {
    event.preventDefault();

    formError.textContent = "";

    if (
      displayNameInput.value.trim() === "" ||
      usernameInput.value.trim() === "" ||
      headlineInput.value.trim() === "" ||
      countryInput.value === "" ||
      cityInput.value.trim() === "" ||
      experienceInput.value === "" ||
      biographyInput.value.trim() === ""
    ) {
      formError.textContent =
        "Please complete all required profile information.";

      return;
    }

    saveProfile();

    window.location.href =
      getNextDestination();
  }
);


// Save and exit.

exitButton.addEventListener(
  "click",
  function () {
    saveProfile();

    window.location.href =
      "index.html";
  }
);


// Restore an unfinished profile.

const savedProfileText =
  localStorage.getItem("soundbridgeProfile");

if (savedProfileText) {
  const savedProfile =
    JSON.parse(savedProfileText);

  displayNameInput.value =
    savedProfile.displayName || "";

  usernameInput.value =
    savedProfile.username || "";

  headlineInput.value =
    savedProfile.headline || "";

  countryInput.value =
    savedProfile.country || "";

  cityInput.value =
    savedProfile.city || "";

  experienceInput.value =
    savedProfile.experience || "";

  biographyInput.value =
    savedProfile.biography || "";

  previewName.textContent =
    savedProfile.displayName ||
    "Your stage name";

  previewHeadline.textContent =
    savedProfile.headline ||
    "Your professional headline will appear here.";

  previewExperience.textContent =
    savedProfile.experience ||
    "Not added";

  const initials =
    createInitials(savedProfile.displayName || "");

  profileInitials.textContent =
    initials;

  previewInitials.textContent =
    initials;

  biographyCount.textContent =
    biographyInput.value.length;

  updateLocation();
}