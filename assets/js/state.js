const DATA_URL = new URL("../../data/latest.json", import.meta.url);
const STORAGE_KEY = "portfolioTracker:lastGeneratedAt";

const buildDataRequestUrl = () => {
  const requestUrl = new URL(DATA_URL.href);
  const cacheBuster = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  requestUrl.searchParams.set("cacheBust", cacheBuster);
  return requestUrl.toString();
};

const fetchPortfolioData = async () => {
  const response = await fetch(buildDataRequestUrl(), {
    cache: "reload",
    headers: {
      "Cache-Control": "no-store",
      Pragma: "no-cache",
    },
  });
  if (!response.ok) {
    throw new Error(`No se pudo cargar ${DATA_URL} (HTTP ${response.status}).`);
  }
  return response.json();
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

const buildStateFromData = (data, preferredPlatformId = null) => {
  const platforms = data.platforms ?? [];
  const platformIndex = buildPlatformIndex(platforms);
  const activePlatformId = pickActivePlatform(platforms, preferredPlatformId);
  const previousGeneratedAt = readPreviousGeneratedAt();

  storeGeneratedAt(data.generated_at);

  return {
    status: "ready",
    error: null,
    generatedAt: data.generated_at ?? null,
    previousGeneratedAt,
    currency: data.currency ?? "USD",
    source: data.source ?? {},
    platforms,
    platformIndex,
    charts: data.charts ?? {},
    activePlatformId,
  };
};

export const loadInitialState = async () => {
  const data = await fetchPortfolioData();
  return buildStateFromData(data);
};

export const reloadState = async (currentState) => {
  const data = await fetchPortfolioData();
  const preferredId = currentState?.activePlatformId ?? null;
  return buildStateFromData(data, preferredId);
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
