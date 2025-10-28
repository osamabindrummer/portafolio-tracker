const DEFAULT_DATA_URL = new URL("../../data/latest.json", import.meta.url);
const STORAGE_KEY = "portfolioTracker:lastGeneratedAt";

const readMetaContent = (metaName) => {
  if (typeof document === "undefined") {
    return null;
  }
  const meta = document.querySelector(`meta[name="${metaName}"]`);
  return meta?.content?.trim() || null;
};

const resolveGithubRawUrl = () => {
  const repositoryMeta = readMetaContent("portfolio-tracker:repository");
  const branchMeta = readMetaContent("portfolio-tracker:branch") || "main";

  if (repositoryMeta) {
    const [owner, repo] = repositoryMeta
      .split("/")
      .map((segment) => segment.trim())
      .filter(Boolean);
    if (owner && repo) {
      return `https://raw.githubusercontent.com/${owner}/${repo}/${branchMeta}/data/latest.json`;
    }
  }

  if (typeof window === "undefined") {
    return null;
  }

  const { hostname, pathname } = window.location;
  if (!hostname.endsWith(".github.io")) {
    return null;
  }

  const owner = hostname.replace(/\.github\.io$/i, "");
  const segments = pathname.split("/").filter(Boolean);
  const repo = segments.length ? segments[0] : owner;
  if (!owner || !repo) {
    return null;
  }

  return `https://raw.githubusercontent.com/${owner}/${repo}/${branchMeta}/data/latest.json`;
};

const DATA_ENDPOINTS = (() => {
  const endpoints = new Set();
  endpoints.add(DEFAULT_DATA_URL.href);
  const rawUrl = resolveGithubRawUrl();
  if (rawUrl) {
    endpoints.add(rawUrl);
  }
  return Array.from(endpoints);
})();

const buildDataRequestUrl = (baseUrl) => {
  const requestUrl = new URL(baseUrl);
  requestUrl.searchParams.set("_", Date.now().toString());
  return requestUrl.toString();
};

const fetchPortfolioData = async () => {
  let lastError = null;

  for (const endpoint of DATA_ENDPOINTS) {
    try {
      const response = await fetch(buildDataRequestUrl(endpoint), { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      lastError = error;
      console.warn(`No se pudo cargar ${endpoint}:`, error);
    }
  }

  const defaultEndpoint = DATA_ENDPOINTS[0] ?? DEFAULT_DATA_URL.href;
  throw new Error(
    lastError?.message
      ? `No se pudo cargar ${defaultEndpoint}: ${lastError.message}`
      : `No se pudo cargar ${defaultEndpoint}.`
  );
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
