const DATA_URL = new URL("../../data/latest.json", import.meta.url);
const STORAGE_KEY = "portfolioTracker:lastGeneratedAt";
const ENDPOINT_STORAGE_KEY = "portfolioTracker:lastDataEndpoint";
const BRANCH_STORAGE_KEY = "portfolioTracker:lastKnownBranches";
const RAW_GITHUB_HOSTNAME = "raw.githubusercontent.com";

const defaultBranchCache = new Map();

const readMetaContent = (name) => {
  if (typeof document === "undefined") {
    return null;
  }
  const element = document.querySelector(`meta[name="${name}"]`);
  const content = element?.getAttribute("content") ?? "";
  const trimmed = content.trim();
  return trimmed.length ? trimmed : null;
};

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

const readStoredJson = (key) => {
  const rawValue = safeReadLocalStorage(key);
  if (!rawValue) {
    return null;
  }
  try {
    return JSON.parse(rawValue);
  } catch (error) {
    console.warn(`No se pudo parsear ${key} desde localStorage:`, error);
    return null;
  }
};

const writeStoredJson = (key, value) => {
  if (!value) {
    safeWriteLocalStorage(key, "{}");
    return;
  }
  try {
    safeWriteLocalStorage(key, JSON.stringify(value));
  } catch (error) {
    console.warn(`No se pudo serializar ${key} en localStorage:`, error);
  }
};

const readLastKnownBranches = () => readStoredJson(BRANCH_STORAGE_KEY) ?? {};

const storeLastKnownBranch = (repo, branch) => {
  if (!repo || !branch) {
    return;
  }
  const branchMap = readLastKnownBranches();
  branchMap[repo] = branch;
  writeStoredJson(BRANCH_STORAGE_KEY, branchMap);
};

const readLastKnownBranch = (repo) => {
  if (!repo) {
    return null;
  }
  const branchMap = readLastKnownBranches();
  const branch = branchMap[repo];
  return typeof branch === "string" && branch.trim().length ? branch : null;
};

const readLastSuccessfulEndpoint = (repo) => {
  const endpoint = safeReadLocalStorage(ENDPOINT_STORAGE_KEY);
  if (!endpoint) {
    return null;
  }
  try {
    const url = new URL(endpoint);
    if (repo) {
      const parsed = parseGitHubRawEndpoint(url);
      if (parsed?.repo && parsed.repo !== repo) {
        return null;
      }
    }
    return url.toString();
  } catch (error) {
    console.warn("Endpoint almacenado no es una URL válida:", error);
    return null;
  }
};

const storeLastSuccessfulEndpoint = (endpoint) => {
  if (!endpoint) {
    return;
  }
  safeWriteLocalStorage(ENDPOINT_STORAGE_KEY, endpoint);
};

const parseGitHubRawEndpoint = (url) => {
  if (!url || url.hostname !== RAW_GITHUB_HOSTNAME) {
    return null;
  }
  const segments = url.pathname.split("/").filter(Boolean);
  if (segments.length < 3) {
    return null;
  }
  const [owner, repo, branch] = segments;
  const repoName = `${owner}/${repo}`;
  return {
    repo: repoName,
    branch,
  };
};

const rememberSuccessfulEndpoint = (endpoint) => {
  if (!endpoint) {
    return;
  }
  try {
    const baseHref = typeof window !== "undefined" && window.location ? window.location.href : undefined;
    const parsedUrl = new URL(endpoint, baseHref);
    storeLastSuccessfulEndpoint(parsedUrl.toString());
    const rawInfo = parseGitHubRawEndpoint(parsedUrl);
    if (rawInfo?.repo && rawInfo.branch) {
      storeLastKnownBranch(rawInfo.repo, rawInfo.branch);
    }
  } catch (error) {
    console.warn("No se pudo registrar el endpoint exitoso:", error);
  }
};

const buildGitHubRawUrl = (repo, branch) =>
  `https://${RAW_GITHUB_HOSTNAME}/${repo}/${branch}/data/latest.json`;

const fetchDefaultBranch = async (repo) => {
  if (!repo) {
    return null;
  }

  if (defaultBranchCache.has(repo)) {
    return defaultBranchCache.get(repo);
  }

  const apiUrl = `https://api.github.com/repos/${repo}`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        Accept: "application/vnd.github+json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const branch = typeof data.default_branch === "string" ? data.default_branch : null;
    defaultBranchCache.set(repo, branch);
    if (branch) {
      storeLastKnownBranch(repo, branch);
    }
    return branch;
  } catch (error) {
    console.warn(`No se pudo consultar la rama por defecto para ${repo}:`, error);
    defaultBranchCache.set(repo, null);
    return null;
  }
};

const buildCandidateEndpoints = async () => {
  const endpoints = [];

  const repo = readMetaContent("data-source:repo");
  const preferredEndpoint = readLastSuccessfulEndpoint(repo ?? undefined);
  if (preferredEndpoint) {
    endpoints.push(preferredEndpoint);
  }

  if (repo) {
    const branchCandidates = [];
    const storedBranch = readLastKnownBranch(repo);
    const metaBranch = readMetaContent("data-source:branch");
    if (storedBranch) {
      branchCandidates.push(storedBranch);
    }
    if (metaBranch) {
      branchCandidates.push(metaBranch);
    }
    const defaultBranch = await fetchDefaultBranch(repo);
    if (defaultBranch) {
      branchCandidates.push(defaultBranch);
    }
    branchCandidates.push("main", "master");

    const uniqueBranches = branchCandidates.filter((branch, index, arr) => {
      if (!branch || typeof branch !== "string") {
        return false;
      }
      const trimmed = branch.trim();
      if (!trimmed.length) {
        return false;
      }
      return arr.indexOf(branch) === index;
    });

    uniqueBranches.forEach((branch) => {
      endpoints.push(buildGitHubRawUrl(repo, branch));
    });
  }

  endpoints.push(DATA_URL.href);

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
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
};

const fetchPortfolioData = async () => {
  const endpoints = await buildCandidateEndpoints();
  const errors = [];

  for (const endpoint of endpoints) {
    try {
      const data = await fetchFromEndpoint(endpoint);
      console.info(`Datos de portafolio cargados desde ${endpoint}`);
      rememberSuccessfulEndpoint(endpoint);
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
  rememberSuccessfulEndpoint(sourceEndpoint);

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
