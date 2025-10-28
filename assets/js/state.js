const DATA_URL = new URL("../../data/latest.json", import.meta.url);
const STORAGE_KEY = "portfolioTracker:lastGeneratedAt";

const readMetaContent = (name) => {
  if (typeof document === "undefined") {
    return null;
  }
  const element = document.querySelector(`meta[name="${name}"]`);
  const content = element?.getAttribute("content") ?? "";
  const trimmed = content.trim();
  return trimmed.length ? trimmed : null;
};

const buildCandidateEndpoints = () => {
  const endpoints = [DATA_URL.href];

  const repo = readMetaContent("data-source:repo");
  if (repo) {
    const branch = readMetaContent("data-source:branch") ?? "main";
    const githubRawUrl = `https://raw.githubusercontent.com/${repo}/${branch}/data/latest.json`;
    endpoints.push(githubRawUrl);
  }

  return Array.from(new Set(endpoints));
};

const buildDataRequestUrl = (baseUrl) => {
  const requestUrl = new URL(baseUrl);
  const cacheBuster = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  requestUrl.searchParams.set("cacheBust", cacheBuster);
  return requestUrl.toString();
};

const fetchFromEndpoint = async (endpoint) => {
  const response = await fetch(buildDataRequestUrl(endpoint), {
    cache: "reload",
    headers: {
      "Cache-Control": "no-store",
      Pragma: "no-cache",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
};

const fetchPortfolioData = async () => {
  const endpoints = buildCandidateEndpoints();
  const errors = [];

  for (const endpoint of endpoints) {
    try {
      const data = await fetchFromEndpoint(endpoint);
      console.info(`Datos de portafolio cargados desde ${endpoint}`);
      return { data, endpoint };
    } catch (error) {
      console.warn(`No se pudo cargar ${endpoint}`, error);
      errors.push({ endpoint, error });
    }
  }

  const reasons = errors
    .map(({ endpoint, error }) => {
      const message = error instanceof Error ? error.message : String(error);
      return `${endpoint}: ${message}`;
    })
    .join("; ");

  throw new Error(
    reasons
      ? `No se pudo cargar data/latest.json desde ninguno de los endpoints. Motivos: ${reasons}`
      : "No se pudo determinar un endpoint para data/latest.json.",
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

const buildStateFromData = (data, preferredPlatformId = null, sourceEndpoint = null) => {
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
