const GOALS_ENDPOINT = "/api/fintual/goals";
const REFRESH_ENDPOINT = "/api/refresh-fintual";
const CACHE_BUSTER_PARAM = "cb";
const BANNER_OFFSET_VAR = "--fintual-banner-offset";
let resizeHandlerAttached = false;

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

const buildMessage = (profit) => `Ganancias Fintual LimnoTec: ${formatClp(profit)}`;

const populateMarquee = (trackEl, message) => {
  if (!trackEl) {
    return;
  }

  trackEl.innerHTML = "";
  const item = document.createElement("span");
  item.className = "fintual-banner__item";
  item.textContent = message;
  trackEl.appendChild(item);
};

const syncBannerOffsetVar = (element) => {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  if (!root) {
    return;
  }
  const height = !element || element.hidden ? 0 : element.offsetHeight;
  root.style.setProperty(BANNER_OFFSET_VAR, `${height}px`);
};

const attachResizeHandler = (element) => {
  if (resizeHandlerAttached || typeof window === "undefined") {
    return;
  }
  const handler = () => syncBannerOffsetVar(element);
  window.addEventListener("resize", handler);
  resizeHandlerAttached = true;
};

const readGoalAttributes = (payload) => {
  const goal = Array.isArray(payload?.data) ? payload.data[0] : null;
  if (!goal || !goal.attributes) {
    return null;
  }

  const attributes = goal.attributes;
  return {
    profit: attributes.profit ?? null,
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

const fetchGoals = async () => {
  const url = resolveEndpoint(GOALS_ENDPOINT);
  const cacheBuster = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  url.searchParams.set(CACHE_BUSTER_PARAM, cacheBuster);
  const response = await fetch(url.toString(), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
};

const setBannerVisibility = (element, visible) => {
  if (!element) {
    return;
  }
  element.hidden = !visible;
  syncBannerOffsetVar(element);
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

  const message = buildMessage(attributes.profit);
  populateMarquee(marqueeTrack, message);
  syncBannerOffsetVar(container);
  attachResizeHandler(container);

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
    const data = await fetchGoals();
    renderBanner(data);
  } catch (error) {
    console.warn("No se pudo cargar el banner de Fintual:", error);
    setBannerVisibility(container, false);
  }
};

export const refreshFintualBanner = async ({ force = false } = {}) => {
  const response = await fetch(REFRESH_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ force }),
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }

  if (!response.ok) {
    const message =
      typeof payload?.message === "string" && payload.message.trim().length
        ? payload.message
        : `HTTP ${response.status}`;
    throw new Error(message);
  }

  await initFintualBanner();
  return payload ?? {
    status: "updated",
    message: "El banner fue actualizado.",
  };
};
