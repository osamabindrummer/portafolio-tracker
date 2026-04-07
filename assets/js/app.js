import { loadInitialState, reloadState, setActivePlatform, triggerPortfolioRefresh } from "./state.js";
import { renderUI } from "./ui.js";
import { initTheme } from "./theme.js";
import { initIndicatorsBanner, refreshIndicatorsBanner } from "./indicators-banner.js";

initTheme();
void initIndicatorsBanner();

let appState = {
  status: "loading",
  chartMode: "return_1y",
};
let isBannerRefreshing = false;

const render = () => {
  renderUI(appState, {
    onPlatformChange: handlePlatformChange,
    onRefresh: handleRefresh,
    onChartModeChange: handleChartModeChange,
  });
  syncIndicatorsBannerRefresh();
};

const syncIndicatorsBannerRefresh = () => {
  const banner = document.getElementById("macro-banner");
  if (!banner) {
    return;
  }

  const isBusy = appState.status === "loading" || appState.status === "refreshing" || isBannerRefreshing;
  banner.disabled = isBusy;
  banner.setAttribute("aria-busy", isBusy ? "true" : "false");
  banner.onclick = () => {
    if (!isBusy) {
      void handleIndicatorsRefresh();
    }
  };
};

const bootstrap = async () => {
  const currentMode = appState.chartMode ?? "return_1y";
  appState = { ...appState, status: "loading", chartMode: currentMode };
  render();

  try {
    const loadedState = await loadInitialState();
    appState = { ...loadedState, chartMode: currentMode };
  } catch (error) {
    console.error("Error inicializando la aplicación", error);
    appState = {
      status: "error",
      chartMode: currentMode,
      statusMessage: null,
      error: error instanceof Error ? error.message : "Error desconocido al cargar los datos.",
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
  if (appState.status === "loading" || appState.status === "refreshing") {
    return;
  }

  const preferredPlatformId = appState.activePlatformId ?? null;
  const currentMode = appState.chartMode ?? "return_1y";
  appState = {
    ...appState,
    status: "refreshing",
    statusMessage: "Solicitando una actualización real al backend de Vercel...",
  };
  render();

  try {
    const refreshResult = await triggerPortfolioRefresh();
    const refreshedState = await reloadState(appState);
    const fallbackId = refreshedState.platformIndex[preferredPlatformId]
      ? preferredPlatformId
      : refreshedState.activePlatformId;
    appState = {
      ...refreshedState,
      activePlatformId: fallbackId,
      chartMode: currentMode,
      statusMessage: buildRefreshMessage(refreshResult),
    };
    await initIndicatorsBanner();
  } catch (error) {
    console.error("Error al refrescar los datos", error);
    appState = {
      status: "error",
      chartMode: currentMode,
      statusMessage: null,
      error: error instanceof Error ? error.message : "Error desconocido al refrescar los datos.",
    };
  }

  render();
};

const handleIndicatorsRefresh = async () => {
  if (isBannerRefreshing || appState.status === "loading" || appState.status === "refreshing") {
    return;
  }

  isBannerRefreshing = true;
  appState = {
    ...appState,
    statusMessage: "Actualizando indicadores públicos desde el backend...",
  };
  render();

  try {
    const result = await refreshIndicatorsBanner();
    appState = {
      ...appState,
      statusMessage: buildBannerRefreshMessage(result),
    };
  } catch (error) {
    console.error("Error al refrescar el banner de indicadores", error);
    appState = {
      ...appState,
      statusMessage:
        error instanceof Error
          ? `No se pudo actualizar el banner: ${error.message}`
          : "No se pudo actualizar el banner.",
    };
  } finally {
    isBannerRefreshing = false;
    render();
  }
};

const handleChartModeChange = (mode) => {
  if (!mode || mode === appState.chartMode) {
    return;
  }
  appState = { ...appState, chartMode: mode };
  render();
};

const buildRefreshMessage = (result) => {
  if (result?.errors && Object.keys(result.errors).length) {
    return "La actualización terminó de forma parcial. Revisa qué dataset no pudo refrescarse.";
  }

  const latestStatus = result?.results?.latest?.status ?? null;
  const indicatorsStatus = result?.results?.indicators?.status ?? null;

  if (latestStatus === "updated" || indicatorsStatus === "updated") {
    return "La web pidió una actualización real y ya está mostrando la versión más reciente.";
  }

  if (latestStatus === "skipped" && indicatorsStatus === "skipped") {
    return "El backend respondió que ambos datasets ya estaban frescos, por eso no regeneró nada.";
  }

  return "La actualización terminó, pero el backend no devolvió un detalle completo.";
};

const buildBannerRefreshMessage = (result) => {
  if (result?.status === "updated") {
    return "El banner de indicadores se actualizó con un refresh real del backend.";
  }
  if (result?.status === "skipped") {
    return "Los indicadores ya estaban frescos, así que el backend evitó repetir la consulta.";
  }
  return "El banner terminó su refresh, pero sin un detalle adicional.";
};

bootstrap();
