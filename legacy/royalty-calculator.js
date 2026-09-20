const calculatorForm = document.getElementById("calculatorForm");
const platformInput = document.getElementById("platform");
const streamsInput = document.getElementById("streams");
const territoryInput = document.getElementById("territory");
const currencyInput = document.getElementById("currency");
const ownershipInput = document.getElementById("ownership");
const ownershipValue = document.getElementById("ownershipValue");
const formError = document.getElementById("formError");
const saveButton = document.getElementById("saveCalculation");
const toast = document.getElementById("toast");

let latestCalculation = null;

const platformRates = {
  spotify: {
    name: "Spotify",
    low: 0.003,
    high: 0.005
  },

  apple: {
    name: "Apple Music",
    low: 0.006,
    high: 0.01
  },

  boomplay: {
    name: "Boomplay",
    low: 0.001,
    high: 0.003
  },

  audiomack: {
    name: "Audiomack",
    low: 0.001,
    high: 0.004
  },

  youtube: {
    name: "YouTube Music",
    low: 0.0007,
    high: 0.002
  },

  amazon: {
    name: "Amazon Music",
    low: 0.004,
    high: 0.008
  },

  tidal: {
    name: "Tidal",
    low: 0.008,
    high: 0.013
  }
};

const territoryMultipliers = {
  global: 1,
  nigeria: 0.55,
  africa: 0.65,
  usa: 1.15,
  uk: 1.1,
  europe: 1.05,
  other: 0.85
};

const currencyInformation = {
  NGN: {
    symbol: "₦",
    usdRate: 1600,
    locale: "en-NG"
  },

  USD: {
    symbol: "$",
    usdRate: 1,
    locale: "en-US"
  },

  GBP: {
    symbol: "£",
    usdRate: 0.79,
    locale: "en-GB"
  },

  EUR: {
    symbol: "€",
    usdRate: 0.92,
    locale: "de-DE"
  }
};

ownershipInput.addEventListener("input", () => {
  ownershipValue.textContent = `${ownershipInput.value}%`;
});

document.querySelectorAll("[data-streams]").forEach((button) => {
  button.addEventListener("click", () => {
    streamsInput.value = button.dataset.streams;
    formError.textContent = "";
  });
});

calculatorForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const platformKey = platformInput.value;
  const streams = Number(streamsInput.value);
  const ownership = Number(ownershipInput.value);

  if (!platformKey) {
    formError.textContent = "Please select a streaming platform.";
    return;
  }

  if (!streams || streams < 1) {
    formError.textContent =
      "Please enter a valid number of streams.";

    return;
  }

  formError.textContent = "";

  const platform = platformRates[platformKey];
  const territoryMultiplier =
    territoryMultipliers[territoryInput.value];

  const currency =
    currencyInformation[currencyInput.value];

  const adjustedLowRate =
    platform.low * territoryMultiplier;

  const adjustedHighRate =
    platform.high * territoryMultiplier;

  const grossLowUSD = streams * adjustedLowRate;
  const grossHighUSD = streams * adjustedHighRate;

  const ownershipDecimal = ownership / 100;

  const artistLowUSD = grossLowUSD * ownershipDecimal;
  const artistHighUSD = grossHighUSD * ownershipDecimal;

  const grossAverageUSD =
    (grossLowUSD + grossHighUSD) / 2;

  const artistAverageUSD =
    (artistLowUSD + artistHighUSD) / 2;

  latestCalculation = {
    platform: platform.name,
    streams: streams,
    territory: territoryInput.value,
    currency: currencyInput.value,
    ownership: ownership,
    estimatedLow: convertCurrency(artistLowUSD, currency),
    estimatedHigh: convertCurrency(artistHighUSD, currency),
    estimatedAverage: convertCurrency(
      artistAverageUSD,
      currency
    ),
    calculatedAt: new Date().toISOString()
  };

  displayResults({
    platform,
    streams,
    ownership,
    currency,
    grossAverageUSD,
    artistAverageUSD,
    artistLowUSD,
    artistHighUSD,
    adjustedLowRate,
    adjustedHighRate
   });
});

currencyInput.addEventListener("change", () =>   {
  if (latestCalculation) {
    calculatorForm.requestSubmit();
  }
});

saveButton.addEventListener("click", () => {
  if (!latestCalculation) {
    return;
  }

  const savedCalculations =
    JSON.parse(
      localStorage.getItem("soundbridgeRoyaltyCalculations")
    ) || [];

  savedCalculations.unshift(latestCalculation);

  localStorage.setItem(
    "soundbridgeRoyaltyCalculations",
    JSON.stringify(savedCalculations)
  );

  toast.classList.add("show");

  setTimeout(() => {
    toast.classList.remove("show");
  }, 2600);
});

function displayResults(data) {
  const {
    platform,
    streams,
    ownership,
    currency,
    grossAverageUSD,
    artistAverageUSD,
    artistLowUSD,
    artistHighUSD,
    adjustedLowRate,
    adjustedHighRate
  } = data;

  const grossConverted =
    convertCurrency(grossAverageUSD, currency);

  const artistConverted =
    convertCurrency(artistAverageUSD, currency);

  const lowConverted =
    convertCurrency(artistLowUSD, currency);

  const highConverted =
    convertCurrency(artistHighUSD, currency);

  document.getElementById("resultPlatform").textContent =
    `${formatNumber(streams)} streams on ${platform.name}`;

  document.getElementById("resultCurrency").textContent =
    currency.symbol;

  document.getElementById("estimatedAmount").textContent =
    formatMoney(artistConverted, currency);

  document.getElementById("resultRange").textContent =
    `Possible range: ${currency.symbol}${formatMoney(
      lowConverted,
      currency
    )} – ${currency.symbol}${formatMoney(
      highConverted,
      currency
    )}`;

  document.getElementById("grossRevenue").textContent =
    `${currency.symbol}${formatMoney(grossConverted, currency)}`;

  document.getElementById("ownershipResult").textContent =
    `${ownership}%`;

  document.getElementById("artistShare").textContent =
    `${currency.symbol}${formatMoney(artistConverted, currency)}`;

  const averageRate =
    (adjustedLowRate + adjustedHighRate) / 2;

  const convertedStreamRate =
    convertCurrency(averageRate, currency);

  document.getElementById("streamRate").textContent =
    `Approximately ${currency.symbol}${convertedStreamRate.toFixed(4)}`;

  saveButton.disabled = false;
}

function convertCurrency(usdAmount, currency) {
  return usdAmount * currency.usdRate;
}

function formatMoney(amount, currency) {
  return new Intl.NumberFormat(currency.locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount);
}

function formatNumber(number) {
  return new Intl.NumberFormat("en-US").format(number);
}