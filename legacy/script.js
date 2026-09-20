// --------------------------------
// SELECT HTML ELEMENTS
// --------------------------------

const openMenuButton =
  document.getElementById("openMenuButton");

const closeMenuButton =
  document.getElementById("closeMenuButton");

const mobileNavigation =
  document.getElementById("mobileNavigation");

const mobileLinks =
  mobileNavigation.querySelectorAll("a");

const heroPlayButton =
  document.getElementById("heroPlayButton");

const heroPlayIcon =
  document.getElementById("heroPlayIcon");

const heroPlayText =
  document.getElementById("heroPlayText");

const playerButton =
  document.getElementById("playerButton");

const playerIcon =
  document.getElementById("playerIcon");

const playerWave =
  document.getElementById("playerWave");

const record =
  document.getElementById("record");

const scrollProgress =
  document.getElementById("scrollProgress");

const currentYear =
  document.getElementById("currentYear");


// --------------------------------
// MOBILE MENU
// --------------------------------

function openMobileMenu() {
  mobileNavigation.classList.add("active");
  mobileNavigation.setAttribute("aria-hidden", "false");
  openMenuButton.setAttribute("aria-expanded", "true");
  document.body.classList.add("menu-open");
  closeMenuButton.focus();
}

function closeMobileMenu() {
  mobileNavigation.classList.remove("active");
  mobileNavigation.setAttribute("aria-hidden", "true");
  openMenuButton.setAttribute("aria-expanded", "false");
  document.body.classList.remove("menu-open");
  openMenuButton.focus();
}

openMenuButton.addEventListener(
  "click",
  openMobileMenu
);

closeMenuButton.addEventListener(
  "click",
  closeMobileMenu
);

mobileLinks.forEach(function (link) {
  link.addEventListener(
    "click",
    closeMobileMenu
  );
});

document.addEventListener(
  "keydown",
  function (event) {
    if (
      event.key === "Escape" &&
      mobileNavigation.classList.contains("active")
    ) {
      closeMobileMenu();
    }
  }
);


// --------------------------------
// MUSIC PLAYER
// --------------------------------

let isPlaying = false;

function updateMusicPlayer() {
  if (isPlaying) {
    playerIcon.textContent = "❚❚";
    heroPlayIcon.textContent = "❚❚";
    heroPlayText.textContent = "Pause the network";

    playerWave.classList.add("playing");
    record.classList.add("playing");
  } else {
    playerIcon.textContent = "▶";
    heroPlayIcon.textContent = "▶";
    heroPlayText.textContent = "Hear the network";

    playerWave.classList.remove("playing");
    record.classList.remove("playing");
  }
}

function toggleMusic() {
  isPlaying = !isPlaying;
  updateMusicPlayer();
}

playerButton.addEventListener(
  "click",
  toggleMusic
);

heroPlayButton.addEventListener(
  "click",
  toggleMusic
);


// --------------------------------
// SCROLL PROGRESS BAR
// --------------------------------

function updateScrollProgress() {
  const distanceFromTop =
    document.documentElement.scrollTop;

  const totalScrollableDistance =
    document.documentElement.scrollHeight -
    document.documentElement.clientHeight;

  const progress =
    distanceFromTop / totalScrollableDistance;

  scrollProgress.style.width =
    progress * 100 + "%";
}

window.addEventListener(
  "scroll",
  updateScrollProgress
);


// --------------------------------
// REVEAL SECTIONS WHILE SCROLLING
// --------------------------------

const revealElements =
  document.querySelectorAll(".reveal");

const revealObserver =
  new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
        }
      });
    },
    {
      threshold: 0.12
    }
  );

revealElements.forEach(function (element) {
  revealObserver.observe(element);
});

// --------------------------------
// CURRENT YEAR
// --------------------------------

currentYear.textContent =
  new Date().getFullYear();


// --------------------------------
// CONFIRM JAVASCRIPT CONNECTION
// --------------------------------

console.log(
  "SoundBridge JavaScript is connected."
);
