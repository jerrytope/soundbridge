const creators = [
  {
    id: 1,
    name: "Kairo Ade",
    initials: "KA",
    role: "Producer",
    genres: ["Afrobeats", "Amapiano"],
    country: "Nigeria",
    city: "Lagos",
    match: 96,
    bio:
      "Producer focused on rhythm-led African pop, artist development and collaborative recording sessions."
  },
  {
    id: 2,
    name: "Ama Serwaa",
    initials: "AS",
    role: "Songwriter",
    genres: ["R&B", "Afrobeats"],
    country: "Ghana",
    city: "Accra",
    match: 93,
    bio:
      "Melody-first songwriter creating emotional records for independent artists and global audiences."
  },
  {
    id: 3,
    name: "Thabo Mokoena",
    initials: "TM",
    role: "Audio Engineer",
    genres: ["Amapiano", "Hip-Hop"],
    country: "South Africa",
    city: "Johannesburg",
    match: 91,
    bio:
      "Mix and mastering engineer helping artists achieve clean, energetic and commercially competitive records."
  },
  {
    id: 4,
    name: "Jordan Blake",
    initials: "JB",
    role: "Artist",
    genres: ["Alternative", "R&B"],
    country: "United Kingdom",
    city: "London",
    match: 89,
    bio:
      "Independent recording artist exploring alternative R&B, electronic textures and cross-cultural collaborations."
  },
  {
    id: 5,
    name: "Nneka Okoro",
    initials: "NO",
    role: "Music Manager",
    genres: ["Afrobeats", "Pop"],
    country: "Nigeria",
    city: "Abuja",
    match: 87,
    bio:
      "Artist manager supporting release strategy, partnerships, career planning and sustainable audience growth."
  },
  {
    id: 6,
    name: "Maya Robinson",
    initials: "MR",
    role: "Videographer",
    genres: ["Hip-Hop", "Pop"],
    country: "United States",
    city: "Atlanta",
    match: 85,
    bio:
      "Music filmmaker and visual director creating performance videos, campaign content and artist documentaries."
  },
  {
    id: 7,
    name: "David Mensah",
    initials: "DM",
    role: "Producer",
    genres: ["Gospel", "Afrobeats"],
    country: "Ghana",
    city: "Kumasi",
    match: 83,
    bio:
      "Producer and instrumentalist creating uplifting contemporary gospel and Afrobeats records."
  },
  {
    id: 8,
    name: "Zara Bello",
    initials: "ZB",
    role: "Artist",
    genres: ["Pop", "Afrobeats"],
    country: "Nigeria",
    city: "Lagos",
    match: 81,
    bio:
      "Pop artist interested in international collaborations, live performance and fresh African sounds."
  },
  {
    id: 9,
    name: "Lerato Khumalo",
    initials: "LK",
    role: "Songwriter",
    genres: ["Amapiano", "Pop"],
    country: "South Africa",
    city: "Pretoria",
    match: 79,
    bio:
      "Topline songwriter developing memorable hooks and vocal ideas for dance and pop releases."
  }
];

const creatorGrid = document.getElementById("creatorGrid");
const searchInput = document.getElementById("searchInput");
const roleFilter = document.getElementById("roleFilter");
const genreFilter = document.getElementById("genreFilter");
const locationFilter = document.getElementById("locationFilter");
const resultCount = document.getElementById("resultCount");
const emptyState = document.getElementById("emptyState");
const clearFiltersButton = document.getElementById("clearFilters");
const emptyClearButton = document.getElementById("emptyClearButton");

const profileModal = document.getElementById("profileModal");
const closeModal = document.getElementById("closeModal");
const connectButton = document.getElementById("connectButton");
const messageButton = document.getElementById("messageButton");
const toast = document.getElementById("toast");

let activeCreator = null;

loadUserAvatar();
renderCreators(creators);

searchInput.addEventListener("input", filterCreators);
roleFilter.addEventListener("change", filterCreators);
genreFilter.addEventListener("change", filterCreators);
locationFilter.addEventListener("change", filterCreators);

clearFiltersButton.addEventListener("click", clearFilters);
emptyClearButton.addEventListener("click", clearFilters);

closeModal.addEventListener("click", closeProfileModal);

profileModal.addEventListener("click", (event) => {
  if (event.target === profileModal) {
    closeProfileModal();
  }
});

connectButton.addEventListener("click", () => {
  if (!activeCreator) {
    return;
  }

  const savedConnections =
    JSON.parse(
      localStorage.getItem("soundbridgeConnections")
    ) || [];

  const alreadyConnected = savedConnections.some(
    (connection) => connection.id === activeCreator.id
  );

  if (alreadyConnected) {
    showToast(
      `You already sent a request to ${activeCreator.name}.`
    );

    return;
  }

  savedConnections.push({
    id: activeCreator.id,
    name: activeCreator.name,
    role: activeCreator.role,
    status: "Pending",
    requestedAt: new Date().toISOString()
  });

  localStorage.setItem(
    "soundbridgeConnections",
    JSON.stringify(savedConnections)
  );

  connectButton.textContent = "Request sent";
  connectButton.disabled = true;

  showToast(`Connection request sent to ${activeCreator.name}.`);
});

messageButton.addEventListener("click", () => {
  if (!activeCreator) {
    return;
  }

  showToast(
    `Messaging with ${activeCreator.name} will be built next.`
  );
});

function filterCreators() {
  const searchTerm = searchInput.value.trim().toLowerCase();
  const selectedRole = roleFilter.value;
  const selectedGenre = genreFilter.value;
  const selectedLocation = locationFilter.value;

  const filteredCreators = creators.filter((creator) => {
    const searchableInformation = [
      creator.name,
      creator.role,
      creator.country,
      creator.city,
      creator.genres.join(" ")
    ]
      .join(" ")
      .toLowerCase();

    const matchesSearch =
      searchableInformation.includes(searchTerm);

    const matchesRole =
      selectedRole === "all" ||
      creator.role === selectedRole;

    const matchesGenre =
      selectedGenre === "all" ||
      creator.genres.includes(selectedGenre);

    const matchesLocation =
      selectedLocation === "all" ||
      creator.country === selectedLocation;

    return (
      matchesSearch &&
      matchesRole &&
      matchesGenre &&
      matchesLocation
    );
  });

  renderCreators(filteredCreators);
}

function renderCreators(creatorList) {
  creatorGrid.innerHTML = "";

  resultCount.textContent =
    `${creatorList.length} ` +
    `${creatorList.length === 1 ? "creator" : "creators"} found`;

  if (creatorList.length === 0) {
    emptyState.classList.add("visible");
    return;
  }

  emptyState.classList.remove("visible");

  creatorList.forEach((creator) => {
    const card = document.createElement("article");

    card.className = "creator-card";

    const genreTags = creator.genres
      .map((genre) => {
        return `<span class="genre-tag">${genre}</span>`;
      })
      .join("");

    card.innerHTML = `
      <div class="creator-cover"></div>

      <div class="creator-content">

        <div class="creator-avatar">
          ${creator.initials}
        </div>

        <div class="creator-name-row">
          <h3>${creator.name}</h3>
          <span class="match-badge">${creator.match}% match</span>
        </div>

        <p class="creator-role">${creator.role}</p>

        <p class="creator-location">
          ${creator.city}, ${creator.country}
        </p>

        <div class="creator-genres">
          ${genreTags}
        </div>

        <button
          class="view-profile-button"
          data-creator-id="${creator.id}"
        >
          View profile
        </button>

      </div>
    `;

    creatorGrid.appendChild(card);
  });

  document
    .querySelectorAll(".view-profile-button")
    .forEach((button) => {
      button.addEventListener("click", () => {
        const creatorId = Number(button.dataset.creatorId);

        const creator = creators.find(
          (item) => item.id === creatorId
        );

        openProfileModal(creator);
      });
    });
}

function openProfileModal(creator) {
  activeCreator = creator;

  document.getElementById("modalAvatar").textContent =
    creator.initials;

  document.getElementById("modalName").textContent =
    creator.name;

  document.getElementById("modalRole").textContent =
    creator.role;

  document.getElementById("modalLocation").textContent =
    `${creator.city}, ${creator.country}`;

  document.getElementById("modalBio").textContent =
    creator.bio;

  document.getElementById("modalGenres").innerHTML =
    creator.genres
      .map((genre) => {
        return `<span class="genre-tag">${genre}</span>`;
      })
      .join("");

  const savedConnections =
    JSON.parse(
      localStorage.getItem("soundbridgeConnections")
    ) || [];

  const alreadyConnected = savedConnections.some(
    (connection) => connection.id === creator.id
  );

  connectButton.textContent = alreadyConnected
    ? "Request sent"
    : "Send connection request";

  connectButton.disabled = alreadyConnected;

  profileModal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeProfileModal() {
  profileModal.classList.remove("open");
  document.body.style.overflow = "";
}

function clearFilters() {
  searchInput.value = "";
  roleFilter.value = "all";
  genreFilter.value = "all";
  locationFilter.value = "all";

  renderCreators(creators);
}

function loadUserAvatar() {
  const savedProfile =
    JSON.parse(
      localStorage.getItem("soundbridgeProfile")
    ) || {};

  const displayName =
    savedProfile.displayName ||
    savedProfile.name ||
    "SoundBridge Creator";

  const initials = displayName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  document.getElementById("userAvatar").textContent =
    initials || "SB";
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");

  setTimeout(() => {
    toast.classList.remove("visible");
  }, 2600);
}