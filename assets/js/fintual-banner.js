const GOALS_ENDPOINTS = [
  "/fintual/goals.json",
  "../../fintual/goals.json",
  "/public/fintual/goals.json",
  "../../public/fintual/goals.json",
];
const CACHE_BUSTER_PARAM = "cb";

const formatClp = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  const formatter = new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  });
  return formatter.format(Number(value));
};

const formatTimestamp = (isoString) => {
  if (!isoString) {
    return "--";
  }
  try {
    const date = new Date(isoString);
    const formatter = new Intl.DateTimeFormat("es-CL", {
      dateStyle: "medium",
      timeStyle: "short",
    });
    return formatter.format(date);
  } catch (error) {
    console.warn("No se pudo formatear la fecha del banner:", error);
    return isoString;
  }
};

const buildMessage = (nav, deposited, profit, updatedAt) => {
  const parts = [
    `Fintual LimnoTec: Saldo (${formatClp(nav)})`,
    `Depositado (${formatClp(deposited)})`,
    `Ganancia (${formatClp(profit)})`,
    `Actualizado ${formatTimestamp(updatedAt)}`,
  ];
  return parts.join(" · ");
};

const shouldReduceMotion = () => {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
};

const populateMarquee = (trackEl, message) => {
  if (!trackEl) {
    return;
  }

  trackEl.innerHTML = "";
  const createItem = () => {
    const item = document.createElement("span");
    item.className = "fintual-banner__item";
    item.textContent = message;
    trackEl.appendChild(item);
    return item;
  };

  createItem();

  const marquee = trackEl.closest(".fintual-banner__marquee");
  const marqueeWidth = marquee?.offsetWidth ?? window.innerWidth ?? 0;
  let iterations = 1;
  while (trackEl.scrollWidth < marqueeWidth * 2 && iterations < 10) {
    createItem();
    iterations += 1;
  }
  if (iterations === 1) {
    createItem();
  }

  if (shouldReduceMotion()) {
    trackEl.dataset.reduceMotion = "true";
  } else {
    trackEl.dataset.reduceMotion = "false";
  }
};

const readGoalAttributes = (payload) => {
  const goal = Array.isArray(payload?.data) ? payload.data[0] : null;
  if (!goal || !goal.attributes) {
    return null;
  }

  const attributes = goal.attributes;
  return {
    nav: attributes.nav ?? null,
    deposited: attributes.deposited ?? null,
    profit: attributes.profit ?? null,
    updatedAt: payload?.fetched_at ?? attributes.updated_at ?? null,
  };
};

const resolveEndpoint = (endpoint) => {
  if (!endpoint) {
    throw new Error("Endpoint inválido");
  }
  if (/^https?:\/\//i.test(endpoint)) {
    return new URL(endpoint);
  }
  if (endpoint.startsWith("/")) {
    return new URL(endpoint, window.location.origin);
  }
  return new URL(endpoint, import.meta.url);
};

const fetchWithFallback = async () => {
  const errors = [];
  for (const endpoint of GOALS_ENDPOINTS) {
    try {
      const url = resolveEndpoint(endpoint);
      const cacheBuster = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      url.searchParams.set(CACHE_BUSTER_PARAM, cacheBuster);
      const response = await fetch(url.toString(), { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      return data;
    } catch (error) {
      errors.push({ endpoint, error });
    }
  }

  const messages = errors
    .map(({ endpoint, error }) => `${endpoint}: ${error instanceof Error ? error.message : String(error)}`)
    .join(" · ");

  throw new Error(messages || "No se pudo consultar goals.json");
};

const setBannerVisibility = (element, visible) => {
  if (!element) {
    return;
  }
  element.hidden = !visible;
};

const renderBanner = (data) => {
  const container = document.getElementById("fintual-banner");
  if (!container) {
    return;
  }

  const marqueeTrack = container.querySelector("[data-banner-track]");
  const liveRegion = container.querySelector("[data-banner-live]");

  const attributes = readGoalAttributes(data);
  if (!attributes) {
    console.warn("El JSON de goals no tiene atributos reconocibles.");
    setBannerVisibility(container, false);
    return;
  }

  setBannerVisibility(container, true);

  const message = buildMessage(attributes.nav, attributes.deposited, attributes.profit, attributes.updatedAt);
  populateMarquee(marqueeTrack, message);

  if (liveRegion) {
    liveRegion.textContent = message;
  }
};

export const initFintualBanner = async () => {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return;
  }

  const container = document.getElementById("fintual-banner");
  if (!container) {
    return;
  }

  setBannerVisibility(container, false);

  try {
    const data = await fetchWithFallback();
    renderBanner(data);
  } catch (error) {
    console.warn("No se pudo cargar el banner de Fintual:", error);
    setBannerVisibility(container, false);
  }
};
