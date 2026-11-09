import { requestJSON } from "./http.js";

const INDICATORS_ENDPOINT = "/api/indicators";
const REFRESH_ENDPOINT = "/api/refresh-indicators";
const BANNER_OFFSET_VAR = "--macro-banner-offset";
let resizeHandlerAttached = false;
// Los espacios inseparables mantienen la misma separación también al repetir la cinta.
const INDICATOR_SEPARATOR = "\u00a0\u00a0·\u00a0\u00a0";

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
  items
    .map((item) => `${item.label}: ${formatIndicatorValue(item)}`)
    .join(INDICATOR_SEPARATOR);

const createMarqueeItem = (message) => {
  const item = document.createElement("span");
  item.className = "macro-banner__item";
  item.textContent = `${message}${INDICATOR_SEPARATOR}`;
  return item;
};

const populateMarquee = (trackEl, message) => {
  if (!trackEl) {
    return;
  }

  trackEl.innerHTML = "";
  const sequence = document.createElement("div");
  sequence.className = "macro-banner__sequence";
  sequence.appendChild(createMarqueeItem(message));
  trackEl.appendChild(sequence);

  const viewportWidth = trackEl.parentElement?.clientWidth ?? 0;
  const itemWidth =
    sequence.firstElementChild?.getBoundingClientRect().width ?? 0;
  const repetitions =
    itemWidth > 0 ? Math.max(2, Math.ceil(viewportWidth / itemWidth) + 1) : 2;

  for (let index = 1; index < repetitions; index += 1) {
    sequence.appendChild(createMarqueeItem(message));
  }

  trackEl.appendChild(sequence.cloneNode(true));
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

const fetchIndicators = async () =>
  (await requestJSON(INDICATORS_ENDPOINT)).payload;

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

  try {
    const data = await fetchIndicators();
    renderBanner(data);
    return true;
  } catch (error) {
    console.warn("No se pudo cargar el banner de indicadores:", error);
    if (!container.querySelector("[data-banner-track]")?.childElementCount)
      setBannerVisibility(container, false);
    return false;
  }
};

export const refreshIndicatorsBanner = async () => {
  const { payload } = await requestJSON(REFRESH_ENDPOINT, {
    body: {},
    timeout: 30000,
  });
  if (!(await initIndicatorsBanner()))
    throw new Error(
      "Los indicadores se actualizaron, pero no se pudieron recargar. Se conserva la vista anterior.",
    );
  return payload;
};
