import { createCharts } from "./charts.js";

const PLATFORM_LOGOS = {
  racional: "assets/img/racional.png",
  fintual: "assets/img/fintual.png",
};

const RACIONAL_DISPLAY_NAMES = {
  "CFIETFGE.SN": "Singular Global Equities",
  "IYWCL.SN": "iShares U.S. Technology",
  "EEMCL.SN": "iShares MSCI Emerging Markets",
  "CFMITNIPSA.SN": "IT NOW S&P IPSA",
  "CFIETFCC.SN": "Singular Chile Corporativo",
  "CFMDIVO.SN": "It Now S&P/CLX Chile Dividend Index",
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

const formatPercent = (value, { signed = true, decimals = 2 } = {}) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }

  const percentValue = value * 100;
  const formatter = new Intl.NumberFormat("es-CL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  const formatted = formatter.format(Math.abs(percentValue));
  if (!signed) {
    return `${formatted}%`;
  }

  const sign = percentValue > 0 ? "+" : percentValue < 0 ? "-" : "";
  return `${sign}${formatted}%`;
};

const formatDateTime = (isoString) => {
  if (!isoString) {
    return "--";
  }
  try {
    const date = new Date(isoString);
    const formatter = new Intl.DateTimeFormat("es-CL", {
      dateStyle: "medium",
      timeStyle: "short",
    });
    return formatter.format(date);
  } catch (error) {
    console.warn("No se pudo formatear la fecha", error);
    return isoString;
  }
};

const computeWeightedMetric = (platform, metricKey) => {
  if (!platform || !platform.holdings?.length) {
    return null;
  }
  let weightedSum = 0;
  let appliedWeight = 0;
  platform.holdings.forEach((holding) => {
    const value = holding.metrics?.[metricKey];
    const weight = holding.weight ?? 0;
    if (value === null || value === undefined || !weight) {
      return;
    }
    weightedSum += value * weight;
    appliedWeight += weight;
  });
  if (!appliedWeight) {
    return null;
  }
  return weightedSum / appliedWeight;
};

const computeWeightedDailyChange = (platform) => computeWeightedMetric(platform, "daily_change_pct");
const computeWeightedMonthlyChange = (platform) => computeWeightedMetric(platform, "monthly_change_pct");
const computeWeightedReturn1Y = (platform) => computeWeightedMetric(platform, "return_1y");
const computeWeightedReturn5Y = (platform) => computeWeightedMetric(platform, "return_5y");

const renderLoading = ({ metricsGrid, tablesContainer, lastUpdate }) => {
  if (metricsGrid) {
    metricsGrid.innerHTML = `
      <div class="metrics-row">
        <article class="metrics-card">
          <span class="metric-label">Cargando datos...</span>
          <strong class="metric-value">⏳</strong>
          <span class="metric-footnote">Leyendo data/latest.json</span>
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

const renderError = ({ metricsGrid, tablesContainer }, message) => {
  if (metricsGrid) {
    metricsGrid.innerHTML = `
      <div class="metrics-row">
        <article class="metrics-card">
          <span class="metric-label">Error</span>
          <strong class="metric-value">⚠️</strong>
          <span class="metric-footnote">${message}</span>
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
    <span class="metric-footnote">${card.footnote}</span>
  </article>
`;

const buildPlatformMetricRow = (platform, currency) => {
  if (!platform) {
    return "";
  }

  const summary = platform.summary ?? {};
  const dailyChange = computeWeightedDailyChange(platform);
  const monthlyChange = summary.avg_monthly_change ?? computeWeightedMonthlyChange(platform);
  const return1Y = summary.avg_return_1y ?? computeWeightedReturn1Y(platform);
  const return5Y = summary.avg_return_5y ?? computeWeightedReturn5Y(platform);
  const platformId = platform.id ?? "";
  const logoSrc = PLATFORM_LOGOS[platformId] ?? null;
  const platformMeta = `${platform.holdings?.length ?? 0} activos · Moneda ${currency}`;

  const cards = [
    {
      label: "Variación diaria",
      value: formatPercent(dailyChange),
      footnote: "Media ponderada del día",
      className: trendClass(dailyChange ?? 0),
    },
    {
      label: "Variación mensual",
      value: formatPercent(monthlyChange),
      footnote: "Últimos 30 días",
      className: trendClass(monthlyChange ?? 0),
    },
    {
      label: "Retorno 1 año",
      value: formatPercent(return1Y),
      footnote: "Horizonte 1Y",
      className: trendClass(return1Y ?? 0),
    },
    {
      label: "Retorno 5 años",
      value: formatPercent(return5Y),
      footnote: "Horizonte 5Y",
      className: trendClass(return5Y ?? 0),
    },
  ];

  const metricsCards = cards.map((card) => buildMetricCard(card)).join("\n");
  const platformClass = platformId ? ` metrics-card--${platformId}` : "";
  const platformCard = `
    <article
      class="metrics-card metrics-card--platform${platformClass}"
      title="${platformMeta}"
      data-platform="${platformId}"
    >
      ${
        logoSrc
          ? `<img src="${logoSrc}" alt="" aria-hidden="true" class="platform-logo" />
             <span class="sr-only">${platform.name}</span>`
          : `<strong class="metric-value">${platform.name}</strong>`
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
    .map((platform) => buildPlatformMetricRow(platform, state?.currency ?? "USD"))
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
      const tickerLink = ticker && ticker !== "--" ? `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}/` : null;
      const racionalDisplayName = platform.id === "racional" ? RACIONAL_DISPLAY_NAMES[ticker] : null;
      const displayName = racionalDisplayName ?? holding.display_name ?? "--";

      return `
        <tr>
          <td>
            <strong>
              ${
                tickerLink
                  ? `<a href="${tickerLink}" target="_blank" rel="noopener noreferrer">${ticker}</a>`
                  : ticker
              }
            </strong>
          </td>
          <td>${displayName}</td>
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

  let platformTitle = platform.name;
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

  const preferredOrder = ["racional", "fintual"];
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
        <option value="${platform.id}">${platform.name}</option>
      `
    )
    .join("\n");

  chartPlatformSelect.value = state?.activePlatformId ?? platforms[0].id;
  chartPlatformSelect.disabled = state?.status !== "ready" && state?.status !== "refreshing";

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

  const isReady = state.status === "ready";
  const isRefreshing = state.status === "refreshing";

  const shouldDisable = !isReady || isRefreshing;

  refreshButton.disabled = shouldDisable;
  refreshButton.textContent = isRefreshing ? "Actualizando..." : "Actualizar datos";
  refreshButton.classList.toggle("is-loading", isRefreshing);

  if (callback) {
    refreshButton.onclick = () => callback();
  }
};

const setupChartModeSelect = (state, callback) => {
  const chartModeSelect = document.getElementById("chart-mode");
  if (!chartModeSelect) {
    return;
  }

  const isReady = state.status === "ready" || state.status === "refreshing";
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

  setupChartPlatformSelect(state, callbacks.onPlatformChange);
  setupRefreshButton(state, callbacks.onRefresh);
  setupChartModeSelect(state, callbacks.onChartModeChange);

  if (lastUpdate) {
    const hasGeneratedAt = Boolean(state.generatedAt);
    const currentLabel = hasGeneratedAt ? formatDateTime(state.generatedAt) : "--";
    const previousTimestamp = state.previousGeneratedAt;
    const hasPrevious =
      Boolean(previousTimestamp) && previousTimestamp !== state.generatedAt;
    const previousLabel = hasPrevious ? formatDateTime(previousTimestamp) : null;

    lastUpdate.textContent = hasPrevious
      ? `Última actualización: ${currentLabel} · Anterior: ${previousLabel}`
      : `Última actualización: ${currentLabel}`;
  }

  if (state.status === "loading") {
    renderLoading({ metricsGrid, tablesContainer, lastUpdate });
    createCharts(state);
    return;
  }

  if (state.status === "error") {
    renderError({ metricsGrid, tablesContainer }, state.error ?? "No se pudo cargar la información.");
    createCharts(state);
    return;
  }

  if (metricsGrid) {
    metricsGrid.innerHTML = buildMetricsGrid(state);
  }

  if (tablesContainer) {
    tablesContainer.innerHTML = buildHoldingsTables(state);
  }

  createCharts(state);
};
