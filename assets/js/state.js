const DATA_ENDPOINT = "/api/data/latest";
const REFRESH_ENDPOINT = "/api/refresh-all";
const STORAGE_KEY = "portfolioTracker:lastGeneratedAt";

const safeReadLocalStorage = (key) => {
  if (typeof window === "undefined" || !window.localStorage) {
    return null;
  }
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    console.warn("No se pudo leer localStorage:", error);
    return null;
  }
};

const safeWriteLocalStorage = (key, value) => {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn("No se pudo escribir en localStorage:", error);
  }
};

const buildDataRequestUrl = (baseUrl) => {
  const requestUrl = new URL(baseUrl, window.location.origin);
  const cacheBuster = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  requestUrl.searchParams.set("cacheBust", cacheBuster);
  return requestUrl.toString();
};

const fetchFromEndpoint = async (endpoint) => {
  const response = await fetch(buildDataRequestUrl(endpoint), {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
};

const fetchPortfolioData = async () => {
  const data = await fetchFromEndpoint(DATA_ENDPOINT);
  console.info(`Datos de portafolio cargados desde ${DATA_ENDPOINT}`);
  return { data, endpoint: DATA_ENDPOINT };
};

const buildPlatformIndex = (platforms) =>
  platforms.reduce((acc, platform) => {
    acc[platform.id] = platform;
    return acc;
  }, {});

const pickActivePlatform = (platforms, preferredId) => {
  if (!platforms.length) {
    return null;
  }

  if (preferredId && platforms.some((platform) => platform.id === preferredId)) {
    return preferredId;
  }

  return platforms[0].id;
};

const readPreviousGeneratedAt = () => {
  if (typeof window === "undefined" || !window.localStorage) {
    return null;
  }
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch (error) {
    console.warn("No se pudo leer localStorage:", error);
    return null;
  }
};

const storeGeneratedAt = (value) => {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  if (!value) {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch (error) {
    console.warn("No se pudo escribir en localStorage:", error);
  }
};

const buildStateFromData = (data, preferredPlatformId = null, sourceEndpoint = null) => {
  const platforms = data.platforms ?? [];
  const platformIndex = buildPlatformIndex(platforms);
  const activePlatformId = pickActivePlatform(platforms, preferredPlatformId);
  const previousGeneratedAt = readPreviousGeneratedAt();

  storeGeneratedAt(data.generated_at);

  return {
    status: "ready",
    error: null,
    statusMessage: null,
    generatedAt: data.generated_at ?? null,
    previousGeneratedAt,
    currency: data.currency ?? "USD",
    source: data.source ?? {},
    dataEndpoint: sourceEndpoint,
    platforms,
    platformIndex,
    charts: data.charts ?? {},
    activePlatformId,
  };
};

export const loadInitialState = async () => {
  const { data, endpoint } = await fetchPortfolioData();
  return buildStateFromData(data, null, endpoint);
};

export const reloadState = async (currentState) => {
  const { data, endpoint } = await fetchPortfolioData();
  const preferredId = currentState?.activePlatformId ?? null;
  return buildStateFromData(data, preferredId, endpoint);
};

export const triggerPortfolioRefresh = async ({ force = false, mode = "online" } = {}) => {
  const response = await fetch(REFRESH_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ force, mode }),
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

  return payload ?? {
    status: "updated",
    message: "La actualización terminó sin detalles adicionales.",
  };
};

export const setActivePlatform = (state, platformId) => {
  if (!state || state.status !== "ready") {
    return state;
  }
  if (!platformId || !state.platformIndex[platformId]) {
    return state;
  }
  if (platformId === state.activePlatformId) {
    return state;
  }
  return { ...state, activePlatformId: platformId };
};

export const getActivePlatform = (state) => {
  if (!state || state.status !== "ready") {
    return null;
  }
  if (!state.activePlatformId) {
    return null;
  }
  return state.platformIndex[state.activePlatformId] ?? null;
};
