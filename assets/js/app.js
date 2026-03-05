import { loadInitialState, reloadState, setActivePlatform } from "./state.js";
import { renderUI } from "./ui.js";
import { initTheme } from "./theme.js";
import { initFintualBanner } from "./fintual-banner.js";

initTheme();
void initFintualBanner();

let appState = {
  status: "loading",
  chartMode: "return_1y",
};

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

  const isBusy = appState.status === "loading" || appState.status === "refreshing";
  banner.disabled = isBusy;
  banner.onclick = () => {
    if (!isBusy) {
      void handleRefresh();
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
  appState = { ...appState, status: "refreshing" };
  render();

  try {
    const refreshedState = await reloadState(appState);
    const fallbackId = refreshedState.platformIndex[preferredPlatformId]
      ? preferredPlatformId
      : refreshedState.activePlatformId;
    appState = {
      ...refreshedState,
      activePlatformId: fallbackId,
      chartMode: currentMode,
    };
    await initFintualBanner();
  } catch (error) {
    console.error("Error al refrescar los datos", error);
    appState = {
      status: "error",
      chartMode: currentMode,
      error: error instanceof Error ? error.message : "Error desconocido al refrescar los datos.",
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

bootstrap();
