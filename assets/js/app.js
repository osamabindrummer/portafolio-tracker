import { rememberUpdate } from "./update-status.js";
import {
  loadInitialState,
  reloadState,
  setActivePlatform,
  triggerPortfolioRefresh,
} from "./state.js";
import { renderUI } from "./ui.js";
import { initTheme } from "./theme.js";
import {
  initIndicatorsBanner,
  refreshIndicatorsBanner,
} from "./indicators-banner.js";
import { initMarketWidget } from "./market-widget.js";

initTheme();
initMarketWidget();
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

  const isBusy =
    appState.status === "loading" ||
    appState.status === "refreshing" ||
    isBannerRefreshing;
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
    rememberUpdate({
      scope: "load",
      failed: true,
      message:
        error instanceof Error
          ? error.message
          : "No se pudo cargar el portafolio.",
    });
    appState = {
      status: "error",
      chartMode: currentMode,
      statusMessage: null,
      error:
        error instanceof Error
          ? error.message
          : "Error desconocido al cargar los datos.",
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

  const previousState = appState;
  const preferredPlatformId = appState.activePlatformId ?? null;
  const currentMode = appState.chartMode ?? "return_1y";
  appState = {
    ...appState,
    status: "refreshing",
    statusMessage: "Actualizando cotizaciones...",
    refreshFailed: false,
  };
  render();

  try {
    const refreshResult = await triggerPortfolioRefresh();
    rememberUpdate({
      scope: "portfolio",
      message: buildRefreshMessage(refreshResult),
      failed: Boolean(
        refreshResult.errors && Object.keys(refreshResult.errors).length,
      ),
      results: refreshResult.results ?? {},
      errors: refreshResult.errors ?? {},
    });
    const refreshedState = await reloadState(appState);
    const fallbackId = refreshedState.platformIndex[preferredPlatformId]
      ? preferredPlatformId
      : refreshedState.activePlatformId;
    appState = {
      ...refreshedState,
      activePlatformId: fallbackId,
      chartMode: currentMode,
      statusMessage: buildRefreshMessage(refreshResult),
      refreshFailed: Boolean(
        refreshResult.errors && Object.keys(refreshResult.errors).length,
      ),
    };
    await initIndicatorsBanner();
  } catch (error) {
    console.error("Error al refrescar los datos", error);
    rememberUpdate({
      scope: "portfolio",
      failed: true,
      message:
        error instanceof Error
          ? error.message
          : "No se pudo actualizar el portafolio.",
    });
    appState = {
      ...previousState,
      status: previousState.platforms?.length ? "ready" : "error",
      error: error instanceof Error ? error.message : "No se pudo actualizar.",
      statusMessage:
        "No se pudo actualizar. Se conservan los últimos datos disponibles.",
      refreshFailed: true,
    };
  }

  render();
};

const handleIndicatorsRefresh = async () => {
  if (
    isBannerRefreshing ||
    appState.status === "loading" ||
    appState.status === "refreshing"
  ) {
    return;
  }

  isBannerRefreshing = true;
  appState = {
    ...appState,
    statusMessage: "Actualizando indicadores...",
    refreshFailed: false,
  };
  render();

  try {
    const result = await refreshIndicatorsBanner();
    rememberUpdate({
      scope: "indicators",
      failed: false,
      message: buildBannerRefreshMessage(result),
    });
    appState = {
      ...appState,
      statusMessage: buildBannerRefreshMessage(result),
    };
  } catch (error) {
    console.error("Error al refrescar el banner de indicadores", error);
    rememberUpdate({
      scope: "indicators",
      failed: true,
      message:
        error instanceof Error
          ? error.message
          : "No se pudieron actualizar los indicadores.",
    });
    appState = {
      ...appState,
      refreshFailed: true,
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
    return `Actualización parcial: ${Object.entries(result.errors)
      .map(
        ([key, message]) =>
          `${key === "latest" ? "Portafolio" : "Indicadores"}: ${message}`,
      )
      .join(" · ")}`;
  }

  const latestStatus = result?.results?.latest?.status ?? null;
  const indicatorsStatus = result?.results?.indicators?.status ?? null;

  if (latestStatus === "updated" || indicatorsStatus === "updated") {
    return "Datos actualizados.";
  }

  if (latestStatus === "skipped" && indicatorsStatus === "skipped") {
    return "Los datos ya estaban actualizados.";
  }

  return "La consulta finalizó sin detalles adicionales.";
};

const buildBannerRefreshMessage = (result) => {
  if (result?.status === "updated") {
    return "Indicadores actualizados.";
  }
  if (result?.status === "skipped") {
    return "Los indicadores ya estaban actualizados.";
  }
  return "La consulta de indicadores finalizó.";
};

bootstrap();
