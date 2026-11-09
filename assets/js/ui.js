import { createCharts } from "./charts.js";
import { escapeHTML, formatPercent, formatDateTime } from "./format.js";

const PLATFORM_LOGOS = {
  racional: "assets/img/racional.png",
  racional_107_lir: "assets/img/racional.png",
  fintual: "assets/img/fintual.png",
};

const PLATFORM_OPTION_LABELS = {
  racional: "Racional Pack ETF",
  racional_107_lir: "Racional Pack 107 LIR",
  fintual: "Fintual Risky Norris",
};

const PLATFORM_SUBTITLES = {
  racional: "Pack ETF",
  racional_107_lir: "Pack 107 LIR",
};

const trendClass = (value) => {
  if (value === null || value === undefined) {
    return "value-neutral";
  }
  if (value > 0) {
    return "value-positive";
  }
  if (value < 0) {
    return "value-negative";
  }
  return "value-neutral";
};

let renderedPlatforms = null;

const renderLoading = ({ metricsGrid, tablesContainer, lastUpdate }) => {
  if (metricsGrid) {
    metricsGrid.innerHTML = `
      <div class="metrics-row">
        <article class="metrics-card">
          <span class="metric-label">Cargando datos...</span>
          <strong class="metric-value">⏳</strong>
          <span class="metric-footnote">Consultando portafolio</span>
        </article>
      </div>
    `;
  }

  if (tablesContainer) {
    tablesContainer.innerHTML = `
      <div class="table-placeholder">Cargando holdings...</div>
    `;
  }

  if (lastUpdate) {
    lastUpdate.textContent = "Última actualización: --";
  }
};

const renderError = ({ metricsGrid, tablesContainer }) => {
  if (metricsGrid) {
    metricsGrid.innerHTML = `
      <div class="metrics-row">
        <article class="metrics-card">
          <span class="metric-label">Error</span>
          <strong class="metric-value">⚠️</strong>
          <span class="metric-footnote">No se pudo cargar el portafolio. Consulta Datos y metodología.</span>
        </article>
      </div>
    `;
  }

  if (tablesContainer) {
    tablesContainer.innerHTML = `
      <div class="table-placeholder">No se pudieron cargar los holdings. Intenta refrescar la página.</div>
    `;
  }
};

const buildMetricCard = (card) => `
  <article class="metrics-card">
    <span class="metric-label">${card.label}</span>
    <strong class="metric-value ${card.className ?? ""}">${card.value}</strong>
  </article>
`;

const buildPlatformMetricRow = (platform) => {
  if (!platform) {
    return "";
  }

  const summary = platform.summary ?? {};
  const dailyChange = summary.avg_daily_change ?? null;
  const monthlyChange = summary.avg_monthly_change ?? null;
  const return1Y = summary.avg_return_1y ?? null;
  const return5Y = summary.avg_return_5y ?? null;
  const platformId = platform.id ?? "";
  const logoSrc = PLATFORM_LOGOS[platformId] ?? null;
  const platformSubtitle = PLATFORM_SUBTITLES[platformId] ?? null;

  const cards = [
    {
      label: "Variación diaria",
      value: formatPercent(dailyChange),
      className: trendClass(dailyChange ?? 0),
    },
    {
      label: "Variación mensual",
      value: formatPercent(monthlyChange),
      className: trendClass(monthlyChange ?? 0),
    },
    {
      label: "Retorno 1 año",
      value: formatPercent(return1Y),
      className: trendClass(return1Y ?? 0),
    },
    {
      label: "Retorno 5 años",
      value: formatPercent(return5Y),
      className: trendClass(return5Y ?? 0),
    },
  ];

  const metricsCards = cards.map((card) => buildMetricCard(card)).join("\n");
  const platformClass = platformId
    ? ` metrics-card--${escapeHTML(platformId)}`
    : "";
  const platformCard = `
    <article
      class="metrics-card metrics-card--platform${platformClass}"
      data-platform="${escapeHTML(platformId)}"
    >
      ${
        logoSrc
          ? `<div class="platform-identity">
               <img src="${logoSrc}" alt="" aria-hidden="true" class="platform-logo" />
               ${platformSubtitle ? `<span class="platform-subtitle">${platformSubtitle}</span>` : ""}
             </div>
             <span class="sr-only">${escapeHTML(platform.name)}</span>`
          : `<strong class="metric-value">${escapeHTML(platform.name)}</strong>`
      }
    </article>
  `;

  return `
    <div class="metrics-row">
      ${platformCard}
      ${metricsCards}
    </div>
  `;
};

const buildMetricsGrid = (state) => {
  const platforms = state?.platforms ?? [];
  if (!platforms.length) {
    return `
      <div class="metrics-row">
        <article class="metrics-card">
          <span class="metric-label">Sin datos</span>
          <strong class="metric-value">--</strong>
          <span class="metric-footnote">Ejecuta una actualización para ver las métricas.</span>
        </article>
      </div>
    `;
  }

  return platforms
    .map((platform) => buildPlatformMetricRow(platform))
    .join("\n");
};

const buildHoldingsRows = (platform) => {
  if (!platform || !platform.holdings?.length) {
    return `
      <tr>
        <td colspan="6">No hay datos disponibles para esta plataforma.</td>
      </tr>
    `;
  }

  return platform.holdings
    .map((holding) => {
      const weight = holding.weight ?? 0;
      const metrics = holding.metrics ?? {};
      const monthlyChange = metrics.monthly_change_pct ?? null;
      const return1Y = metrics.return_1y ?? null;
      const return5Y = metrics.return_5y ?? null;

      const ticker = holding.ticker ?? "--";
      const quoteSymbol = holding.quote_symbol ?? ticker;
      const tickerLink =
        ticker && ticker !== "--"
          ? `https://finance.yahoo.com/quote/${encodeURIComponent(quoteSymbol)}/`
          : null;
      const displayName = holding.display_name ?? "--";

      return `
        <tr>
          <td>
            <strong>
              ${
                tickerLink
                  ? `<a href="${tickerLink}" target="_blank" rel="noopener noreferrer">${escapeHTML(ticker)}</a>`
                  : escapeHTML(ticker)
              }
            </strong>
          </td>
          <td>${escapeHTML(displayName)}</td>
          <td class="numeric">${formatPercent(weight, { signed: false })}</td>
          <td class="numeric ${trendClass(monthlyChange)}">${formatPercent(monthlyChange)}</td>
          <td class="numeric ${trendClass(return1Y)}">${formatPercent(return1Y)}</td>
          <td class="numeric ${trendClass(return5Y)}">${formatPercent(return5Y)}</td>
        </tr>
      `;
    })
    .join("\n");
};

const buildHoldingsTable = (platform) => {
  if (!platform) {
    return "";
  }

  let platformTitle = escapeHTML(platform.name);
  if (platform.id === "fintual") {
    platformTitle = `Fintual - <a href="https://fintual.cl/risky-norris" target="_blank" rel="noopener noreferrer">Risky Norris</a>`;
  } else if (platform.id === "racional") {
    platformTitle = "Racional - Pack ETF";
  }

  return `
    <div class="holdings-block">
      <h3 class="holdings-title">${platformTitle}</h3>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th scope="col">Ticker</th>
              <th scope="col">Nombre</th>
              <th scope="col">% Portafolio</th>
              <th scope="col">Variación mensual</th>
              <th scope="col">Retorno 1Y</th>
              <th scope="col">Retorno 5Y</th>
            </tr>
          </thead>
          <tbody>
            ${buildHoldingsRows(platform)}
          </tbody>
        </table>
      </div>
    </div>
  `;
};

const buildHoldingsTables = (state) => {
  const platforms = state?.platforms ?? [];
  if (!platforms.length) {
    return `<div class="table-placeholder">No hay plataformas para mostrar.</div>`;
  }

  const preferredOrder = ["racional", "racional_107_lir", "fintual"];
  const ordered = [...platforms].sort((a, b) => {
    const indexA = preferredOrder.indexOf(a.id);
    const indexB = preferredOrder.indexOf(b.id);
    const safeA = indexA === -1 ? preferredOrder.length : indexA;
    const safeB = indexB === -1 ? preferredOrder.length : indexB;
    if (safeA !== safeB) {
      return safeA - safeB;
    }
    return (a.name ?? "").localeCompare(b.name ?? "");
  });

  return ordered.map((platform) => buildHoldingsTable(platform)).join("\n");
};

const setupChartPlatformSelect = (state, callback) => {
  const chartPlatformSelect = document.getElementById("chart-platform");
  if (!chartPlatformSelect) {
    return;
  }

  const platforms = state?.platforms ?? [];
  if (!platforms.length) {
    chartPlatformSelect.innerHTML = `<option value="">Sin plataformas disponibles</option>`;
    chartPlatformSelect.disabled = true;
    return;
  }

  chartPlatformSelect.innerHTML = platforms
    .map(
      (platform) => `
        <option value="${escapeHTML(platform.id)}">${escapeHTML(PLATFORM_OPTION_LABELS[platform.id] ?? platform.name)}</option>
      `,
    )
    .join("\n");

  chartPlatformSelect.value = state?.activePlatformId ?? platforms[0].id;
  chartPlatformSelect.disabled = state?.status !== "ready";

  if (callback) {
    chartPlatformSelect.onchange = (event) => {
      callback(event.target.value);
    };
  }
};

const setupRefreshButton = (state, callback) => {
  const refreshButton = document.getElementById("refresh-button");
  if (!refreshButton) {
    return;
  }

  const isRefreshing = state.status === "refreshing";
  const isLoading = state.status === "loading";

  const shouldDisable = isLoading || isRefreshing;

  refreshButton.textContent = isRefreshing
    ? "Actualizando..."
    : "Actualizar datos";
  refreshButton.disabled = shouldDisable;
  refreshButton.classList.toggle("is-loading", isRefreshing);
  refreshButton.dataset.state = state.status ?? "loading";

  if (callback) {
    refreshButton.onclick = () => callback();
  }
};

const setupChartModeSelect = (state, callback) => {
  const chartModeSelect = document.getElementById("chart-mode");
  if (!chartModeSelect) {
    return;
  }

  const isReady = state.status === "ready";
  const currentMode = state.chartMode ?? "return_1y";

  chartModeSelect.value = currentMode;
  chartModeSelect.disabled = !isReady;

  if (callback) {
    chartModeSelect.onchange = (event) => {
      callback(event.target.value);
    };
  }
};

export const renderUI = (state, callbacks = {}) => {
  const metricsGrid = document.getElementById("metrics-cards");
  const tablesContainer = document.getElementById("holdings-tables");
  const lastUpdate = document.getElementById("last-update");
  const refreshStatus = document.getElementById("refresh-status");

  setupChartPlatformSelect(state, callbacks.onPlatformChange);
  setupRefreshButton(state, callbacks.onRefresh);
  setupChartModeSelect(state, callbacks.onChartModeChange);

  if (lastUpdate) {
    const hasGeneratedAt = Boolean(state.generatedAt);
    const currentLabel = hasGeneratedAt
      ? formatDateTime(state.generatedAt)
      : "--";
    lastUpdate.textContent = `Última actualización: ${currentLabel}`;
  }

  if (refreshStatus) {
    refreshStatus.textContent =
      state.status === "refreshing"
        ? "Actualizando datos..."
        : state.statusMessage
          ? "Consulta Datos y metodología para ver el resultado de la actualización."
          : "";
  }

  if (state.status === "loading") {
    renderedPlatforms = null;
    renderLoading({ metricsGrid, tablesContainer, lastUpdate });
    createCharts(state);
    return;
  }

  if (state.status === "error") {
    renderedPlatforms = null;
    renderError({ metricsGrid, tablesContainer });
    createCharts(state);
    return;
  }

  if (renderedPlatforms !== state.platforms) {
    if (metricsGrid) metricsGrid.innerHTML = buildMetricsGrid(state);
    if (tablesContainer) tablesContainer.innerHTML = buildHoldingsTables(state);
    renderedPlatforms = state.platforms;
  }

  createCharts(state);
};
