// Get the elements from the HTML page.

const signupForm = document.getElementById("signupForm");
const signinForm = document.getElementById("signinForm");

const showSignInButton = document.getElementById("showSignIn");
const showSignUpButton = document.getElementById("showSignUp");

const passwordInput = document.getElementById("password");
const passwordButton = document.getElementById("passwordButton");

const formError = document.getElementById("formError");
const signinError = document.getElementById("signinError");

const currentYear = document.getElementById("currentYear");


// Display the current year in the footer.

currentYear.textContent = new Date().getFullYear();


// Show the sign-in form.

showSignInButton.addEventListener("click", function () {
  signupForm.classList.add("hidden");
  signinForm.classList.remove("hidden");

  document.querySelector(".step-label").textContent =
    "Access your account";

  document.querySelector(".form-heading h2").textContent =
    "Welcome back";

  document.querySelector(".form-heading > p:last-child").classList.add(
    "hidden"
  );
});


// Return to the sign-up form.

showSignUpButton.addEventListener("click", function () {
  signinForm.classList.add("hidden");
  signupForm.classList.remove("hidden");

  document.querySelector(".step-label").textContent =
    "Create your account";

  document.querySelector(".form-heading h2").textContent =
    "Welcome to SoundBridge";

  document.querySelector(".form-heading > p:last-child").classList.remove(
    "hidden"
  );
});


// Show or hide the sign-up password.

passwordButton.addEventListener("click", function () {
  const passwordIsHidden = passwordInput.type === "password";

  if (passwordIsHidden) {
    passwordInput.type = "text";
    passwordButton.textContent = "Hide";
  } else {
    passwordInput.type = "password";
    passwordButton.textContent = "Show";
  }
});


// Handle the sign-up form.

signupForm.addEventListener("submit", function (event) {
  // Stop the browser from refreshing the page.
  event.preventDefault();

  const firstName = document
    .getElementById("firstName")
    .value
    .trim();

  const lastName = document
    .getElementById("lastName")
    .value
    .trim();

  const email = document
    .getElementById("email")
    .value
    .trim();

  const password = passwordInput.value;

  const agreementAccepted =
    document.getElementById("agreement").checked;

  formError.textContent = "";

  if (
    firstName === "" ||
    lastName === "" ||
    email === "" ||
    password === ""
  ) {
    formError.textContent =
      "Please complete all the required fields.";

    return;
  }

  if (password.length < 8) {
    formError.textContent =
      "Your password must contain at least eight characters.";

    return;
  }

  if (!agreementAccepted) {
    formError.textContent =
      "You must accept the Terms and Privacy Policy.";

    return;
  }

  // Save temporary frontend information in the browser.
  localStorage.setItem("soundbridgeFirstName", firstName);
  localStorage.setItem("soundbridgeLastName", lastName);
  localStorage.setItem("soundbridgeEmail", email);

  // Send the user to onboarding.
  window.location.href = "onboarding.html";
});


// Handle the sign-in form.

signinForm.addEventListener("submit", function (event) {
  event.preventDefault();

  const email = document
    .getElementById("signinEmail")
    .value
    .trim();

  const password = document
    .getElementById("signinPassword")
    .value;

  signinError.textContent = "";

  if (email === "" || password === "") {
    signinError.textContent =
      "Enter your email address and password.";

    return;
  }

  /*
    This is a frontend demonstration.

    When the backend is ready, this section will send the
    email and password securely to the server.
  */

  window.location.href = "portal.html";
});
const pageParameters = new URLSearchParams(window.location.search);
const pageMode = pageParameters.get("mode");

if (pageMode === "signin") {
  showSignInForm();
}

if (pageMode === "signup") {
  showSignUpForm();
}