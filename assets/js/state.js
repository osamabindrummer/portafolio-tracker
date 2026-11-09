import { requestJSON, readPreference, writePreference } from "./http.js";

const DATA_ENDPOINT = "/api/data/latest";
const REFRESH_ENDPOINT = "/api/refresh-all";
const STORAGE_KEY = "portfolioTracker:lastGeneratedAt";

const fetchPortfolioData = async () => {
  const { payload: data, warning } = await requestJSON(DATA_ENDPOINT);
  if (!Array.isArray(data.platforms) || !data.platforms.length) {
    throw new Error("El portafolio no contiene plataformas válidas.");
  }
  return { data, endpoint: DATA_ENDPOINT, warning };
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

  if (
    preferredId &&
    platforms.some((platform) => platform.id === preferredId)
  ) {
    return preferredId;
  }

  return platforms[0].id;
};

const buildStateFromData = (
  data,
  preferredPlatformId = null,
  sourceEndpoint = null,
  storageWarning = null,
) => {
  const platforms = data.platforms ?? [];
  const platformIndex = buildPlatformIndex(platforms);
  const activePlatformId = pickActivePlatform(platforms, preferredPlatformId);
  const previousGeneratedAt = readPreference(STORAGE_KEY);

  if (data.generated_at) writePreference(STORAGE_KEY, data.generated_at);

  return {
    status: "ready",
    error: null,
    statusMessage: null,
    storageWarning,
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
  const { data, endpoint, warning } = await fetchPortfolioData();
  return buildStateFromData(data, null, endpoint, warning);
};

export const reloadState = async (currentState) => {
  const { data, endpoint, warning } = await fetchPortfolioData();
  const preferredId = currentState?.activePlatformId ?? null;
  return buildStateFromData(data, preferredId, endpoint, warning);
};

export const triggerPortfolioRefresh = async () => {
  const { payload } = await requestJSON(REFRESH_ENDPOINT, {
    body: {},
    timeout: 55000,
  });
  return payload;
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
