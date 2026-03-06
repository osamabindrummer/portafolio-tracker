import { loadInitialState, reloadState, setActivePlatform, triggerPortfolioRefresh } from "./state.js";
import { renderUI } from "./ui.js";
import { initTheme } from "./theme.js";
import { initFintualBanner, refreshFintualBanner } from "./fintual-banner.js";

initTheme();
void initFintualBanner();

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
  syncFintualBannerRefresh();
};

const syncFintualBannerRefresh = () => {
  const banner = document.getElementById("fintual-banner");
  if (!banner) {
    return;
  }

  const isBusy = appState.status === "loading" || appState.status === "refreshing" || isBannerRefreshing;
  banner.disabled = isBusy;
  banner.setAttribute("aria-busy", isBusy ? "true" : "false");
  banner.onclick = () => {
    if (!isBusy) {
      void handleFintualRefresh();
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
    await initFintualBanner();
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

const handleFintualRefresh = async () => {
  if (isBannerRefreshing || appState.status === "loading" || appState.status === "refreshing") {
    return;
  }

  isBannerRefreshing = true;
  appState = {
    ...appState,
    statusMessage: "Actualizando las metas de Fintual desde el backend...",
  };
  render();

  try {
    const result = await refreshFintualBanner();
    appState = {
      ...appState,
      statusMessage: buildBannerRefreshMessage(result),
    };
  } catch (error) {
    console.error("Error al refrescar el banner de Fintual", error);
    appState = {
      ...appState,
      statusMessage:
        error instanceof Error
          ? `No se pudo actualizar Fintual: ${error.message}`
          : "No se pudo actualizar Fintual.",
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
  const goalsStatus = result?.results?.goals?.status ?? null;

  if (latestStatus === "updated" || goalsStatus === "updated") {
    return "La web pidió una actualización real y ya está mostrando la versión más reciente.";
  }

  if (latestStatus === "skipped" && goalsStatus === "skipped") {
    return "El backend respondió que ambos datasets ya estaban frescos, por eso no regeneró nada.";
  }

  return "La actualización terminó, pero el backend no devolvió un detalle completo.";
};

const buildBannerRefreshMessage = (result) => {
  if (result?.status === "updated") {
    return "El banner de Fintual se actualizó con un refresh real del backend.";
  }
  if (result?.status === "skipped") {
    return "Fintual ya había sido actualizado hace poco, así que el backend evitó repetir la consulta.";
  }
  return "El banner terminó su refresh, pero sin un detalle adicional.";
};

bootstrap();
