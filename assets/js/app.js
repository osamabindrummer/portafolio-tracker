import { loadInitialState, reloadState, setActivePlatform } from "./state.js";
import { renderUI } from "./ui.js";

let appState = {
  status: "loading",
  chartMode: "return_1y",
  fetchJob: { status: "idle", message: "" },
};

const render = () => {
  renderUI(appState, {
    onPlatformChange: handlePlatformChange,
    onRefresh: handleRefresh,
    onChartModeChange: handleChartModeChange,
    onFetchData: handleFetchData,
  });
};

const bootstrap = async () => {
  const currentMode = appState.chartMode ?? "return_1y";
  const currentFetchJob = appState.fetchJob ?? { status: "idle", message: "" };
  appState = { ...appState, status: "loading", chartMode: currentMode, fetchJob: currentFetchJob };
  render();

  try {
    const loadedState = await loadInitialState();
    appState = { ...loadedState, chartMode: currentMode, fetchJob: currentFetchJob };
  } catch (error) {
    console.error("Error inicializando la aplicación", error);
    appState = {
      status: "error",
      chartMode: currentMode,
      error: error instanceof Error ? error.message : "Error desconocido al cargar los datos.",
      fetchJob: currentFetchJob,
    };
  }

  render();
};

const handlePlatformChange = (platformId) => {
  const nextState = setActivePlatform(appState, platformId);
  if (nextState !== appState) {
    appState = nextState;
    render();
  }
};

const handleRefresh = async () => {
  if (appState.status !== "ready") {
    return;
  }

  const preferredPlatformId = appState.activePlatformId;
  const currentMode = appState.chartMode ?? "return_1y";
  const currentFetchJob = appState.fetchJob ?? { status: "idle", message: "" };
  appState = { ...appState, status: "refreshing", fetchJob: currentFetchJob };
  render();

  try {
    const refreshedState = await reloadState(appState);
    const fallbackId = refreshedState.platformIndex[preferredPlatformId]
      ? preferredPlatformId
      : refreshedState.activePlatformId;
    const nextFetchJob = currentFetchJob.status === "success" ? { status: "idle", message: "" } : currentFetchJob;
    appState = {
      ...refreshedState,
      activePlatformId: fallbackId,
      chartMode: currentMode,
      fetchJob: nextFetchJob,
    };
  } catch (error) {
    console.error("Error al refrescar los datos", error);
    appState = {
      status: "error",
      chartMode: currentMode,
      error: error instanceof Error ? error.message : "Error desconocido al refrescar los datos.",
      fetchJob: currentFetchJob,
    };
  }

  render();
};

const handleChartModeChange = (mode) => {
  if (!mode || mode === appState.chartMode) {
    return;
  }
  appState = { ...appState, chartMode: mode };
  render();
};

const handleFetchData = async () => {
  const previousJob = appState.fetchJob ?? { status: "idle", message: "" };
  if (previousJob.status === "running") {
    return;
  }

  appState = { ...appState, fetchJob: { status: "running", message: "Ejecutando script..." } };
  render();

  try {
    const result = await requestFetchData();
    const generatedAt = typeof result.generated_at === "string" ? result.generated_at : null;
    const message =
      result.message ??
      (generatedAt
        ? 'Datos obtenidos. Presiona "Actualizar página".'
        : "Datos obtenidos correctamente.");
    appState = {
      ...appState,
      fetchJob: { status: "success", message, generatedAt },
    };
  } catch (error) {
    console.error("No se pudo ejecutar fetch_data.py", error);
    const message =
      error instanceof Error && error.message
        ? error.message
        : "No se pudo ejecutar fetch_data.py. Asegúrate de que el servidor local esté activo.";
    appState = {
      ...appState,
      fetchJob: { status: "error", message },
    };
  }

  render();
};

const requestFetchData = async () => {
  const candidates = [
    { url: "/api/fetch-data", method: "POST" },
    { url: "/api/fetch-data", method: "GET" },
    { url: "http://127.0.0.1:8000/api/fetch-data", method: "POST" },
    { url: "http://127.0.0.1:8000/api/fetch-data", method: "GET" },
    { url: "http://localhost:8000/api/fetch-data", method: "POST" },
    { url: "http://localhost:8000/api/fetch-data", method: "GET" },
  ];

  let lastStatus = null;
  let lastException = null;

  for (const candidate of candidates) {
    try {
      const response = await fetch(candidate.url, {
        method: candidate.method,
      });
      if (!response.ok) {
        lastStatus = response.status;
        if ([404, 405, 501].includes(response.status)) {
          continue;
        }
        const text = await response.text().catch(() => "");
        throw new Error(text || `Error HTTP ${response.status}`);
      }
      return response.json().catch(() => ({}));
    } catch (error) {
      lastException = error instanceof Error ? error : new Error(String(error));
    }
  }

  if (lastStatus === 501) {
    throw new Error(
      "No se pudo contactar al servidor local. Ejecuta `python scripts/dev_server.py` y vuelve a intentarlo."
    );
  }

  if (lastStatus === 404 || lastStatus === 405) {
    throw new Error(
      "El endpoint /api/fetch-data no está disponible en este servidor. Levanta el servidor local con `python scripts/dev_server.py`."
    );
  }

  if (lastException instanceof TypeError) {
    throw new Error(
      "No se pudo contactar al servidor local. Ejecuta `python scripts/dev_server.py` y vuelve a intentarlo."
    );
  }

  if (lastException) {
    throw lastException;
  }

  throw new Error("No se pudo ejecutar fetch_data.py.");
};

bootstrap();
