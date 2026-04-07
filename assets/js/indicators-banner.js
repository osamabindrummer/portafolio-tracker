const INDICATORS_ENDPOINT = "/api/indicators";
const REFRESH_ENDPOINT = "/api/refresh-indicators";
const CACHE_BUSTER_PARAM = "cb";
const BANNER_OFFSET_VAR = "--macro-banner-offset";
let resizeHandlerAttached = false;

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

const formatNumber = (value, decimals) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }

  return new Intl.NumberFormat("es-CL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(value));
};

const formatIndicatorValue = (item) => {
  if (!item) {
    return "--";
  }

  if (item.unit === "CLP") {
    return `$${formatNumber(item.value, item.decimals ?? 0)}`;
  }

  if (item.unit === "PERCENT") {
    return `${formatNumber(item.value, item.decimals ?? 1)}%`;
  }

  return formatNumber(item.value, item.decimals ?? 0);
};

const buildMessage = (items) =>
  items.map((item) => `${item.label}: ${formatIndicatorValue(item)}`).join(" · ");

const populateMarquee = (trackEl, message) => {
  if (!trackEl) {
    return;
  }

  trackEl.innerHTML = "";
  for (let index = 0; index < 2; index += 1) {
    const item = document.createElement("span");
    item.className = "macro-banner__item";
    item.textContent = message;
    trackEl.appendChild(item);
  }
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

const fetchIndicators = async () => {
  const url = resolveEndpoint(INDICATORS_ENDPOINT);
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

const readIndicators = (payload) => {
  if (!Array.isArray(payload?.items)) {
    return [];
  }

  return payload.items.filter((item) => item && typeof item.label === "string");
};

const renderBanner = (data) => {
  const container = document.getElementById("macro-banner");
  if (!container) {
    return;
  }

  const marqueeTrack = container.querySelector("[data-banner-track]");
  const liveRegion = container.querySelector("[data-banner-live]");
  const items = readIndicators(data);

  if (!items.length) {
    console.warn("El JSON de indicadores no tiene elementos reconocibles.");
    setBannerVisibility(container, false);
    return;
  }

  setBannerVisibility(container, true);

  const message = buildMessage(items);
  populateMarquee(marqueeTrack, message);
  syncBannerOffsetVar(container);
  attachResizeHandler(container);

  if (liveRegion) {
    liveRegion.textContent = message;
  }
};

export const initIndicatorsBanner = async () => {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return;
  }

  const container = document.getElementById("macro-banner");
  if (!container) {
    return;
  }

  setBannerVisibility(container, false);

  try {
    const data = await fetchIndicators();
    renderBanner(data);
  } catch (error) {
    console.warn("No se pudo cargar el banner de indicadores:", error);
    setBannerVisibility(container, false);
  }
};

export const refreshIndicatorsBanner = async ({ force = false } = {}) => {
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

  await initIndicatorsBanner();
  return payload ?? {
    status: "updated",
    message: "El banner fue actualizado.",
  };
};
