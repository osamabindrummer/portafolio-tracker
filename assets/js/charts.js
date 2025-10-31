const ChartGlobal = window.Chart;

if (!ChartGlobal) {
  throw new Error("Chart.js no se cargó correctamente desde la CDN.");
}

ChartGlobal.defaults.font.family =
  '"Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

const MAIN_CANVAS_ID = "main-chart";
let currentChart = null;
let lastState = null;

const DEFAULT_CHART_THEME = {
  axisColor: "#1a1a1a",
  gridColor: "rgba(11, 87, 208, 0.08)",
  gridStrong: "rgba(100, 116, 139, 0.18)",
  tooltipBg: "rgba(255, 255, 255, 0.95)",
  tooltipColor: "#0f172a",
  tooltipBorder: "rgba(15, 23, 42, 0.08)",
};

const readCssVariable = (styles, name, fallback) => {
  if (!styles) {
    return fallback;
  }
  const value = styles.getPropertyValue(name);
  if (!value) {
    return fallback;
  }
  const trimmed = value.trim();
  return trimmed || fallback;
};

const getChartTheme = () => {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return DEFAULT_CHART_THEME;
  }

  const styles = window.getComputedStyle(document.documentElement);
  return {
    axisColor: readCssVariable(styles, "--chart-axis-color", DEFAULT_CHART_THEME.axisColor),
    gridColor: readCssVariable(styles, "--chart-grid-color", DEFAULT_CHART_THEME.gridColor),
    gridStrong: readCssVariable(styles, "--chart-grid-strong", DEFAULT_CHART_THEME.gridStrong),
    tooltipBg: readCssVariable(styles, "--chart-tooltip-bg", DEFAULT_CHART_THEME.tooltipBg),
    tooltipColor: readCssVariable(styles, "--chart-tooltip-color", DEFAULT_CHART_THEME.tooltipColor),
    tooltipBorder: readCssVariable(styles, "--chart-tooltip-border", DEFAULT_CHART_THEME.tooltipBorder),
  };
};

const COLOR_PALETTE = [
  "#3366CC",
  "#DC3912",
  "#FF9900",
  "#109618",
  "#990099",
  "#0099C6",
  "#DD4477",
  "#66AA00",
  "#B82E2E",
  "#316395",
  "#994499",
  "#22AA99",
  "#AAAA11",
  "#6633CC",
  "#E67300",
  "#8B0707",
  "#651067",
  "#329262",
  "#5574A6",
  "#3B3EAC",
];

const datasetColorCache = new Map();

const getColorForKey = (key) => {
  if (!key) {
    const fallbackIndex = datasetColorCache.size % COLOR_PALETTE.length;
    return COLOR_PALETTE[fallbackIndex];
  }
  if (!datasetColorCache.has(key)) {
    const nextIndex = datasetColorCache.size % COLOR_PALETTE.length;
    datasetColorCache.set(key, COLOR_PALETTE[nextIndex]);
  }
  return datasetColorCache.get(key);
};

const destroyCurrentChart = () => {
  if (currentChart) {
    currentChart.destroy();
    currentChart = null;
  }
};

const applyChartConfig = (chart, config) => {
  chart.config.options = config.options;
  chart.options = config.options;
  const nextData = {
    labels: [...(config.data.labels ?? [])],
    datasets: (config.data.datasets ?? []).map((dataset) => ({
      ...dataset,
      data: Array.isArray(dataset.data) ? [...dataset.data] : dataset.data,
    })),
  };
  chart.config.data = nextData;
  chart.data = nextData;
  chart.update("none");
};

const hexToRgba = (hex, alpha = 1) => {
  const sanitized = hex.replace("#", "");
  const bigint = parseInt(sanitized, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const getCanvas = (canvasId) => document.getElementById(canvasId);

const ensurePlaceholder = (message, canvasId = MAIN_CANVAS_ID) => {
  const canvas = getCanvas(canvasId);
  if (!canvas) {
    return;
  }
  const container = canvas.parentElement;
  if (!container) {
    return;
  }
  let placeholder = container.querySelector(".chart-placeholder");
  if (!placeholder) {
    placeholder = document.createElement("p");
    placeholder.className = "chart-placeholder";
    container.appendChild(placeholder);
  }
  placeholder.textContent = message;
  canvas.classList.add("is-hidden");
};

const clearPlaceholder = (canvasId = MAIN_CANVAS_ID) => {
  const canvas = getCanvas(canvasId);
  if (!canvas) {
    return;
  }
  canvas.classList.remove("is-hidden");
  const container = canvas.parentElement;
  if (!container) {
    return;
  }
  const placeholder = container.querySelector(".chart-placeholder");
  if (placeholder) {
    placeholder.remove();
  }
};

const buildTimeseriesDataset = (state) => {
  const timeseries = state?.charts?.timeseries_5y;
  if (!timeseries) {
    return { labels: [], datasets: [] };
  }

  let datasets = (timeseries.datasets ?? []).filter((dataset) => {
    if (!state.activePlatformId) {
      return true;
    }
    return dataset.platform_id === state.activePlatformId;
  });

  if (!datasets.length) {
    datasets = timeseries.datasets ?? [];
  }

  const labels = timeseries.labels ?? [];
  datasetColorCache.clear();
  const chartDatasets = datasets.map((dataset) => {
    const ticker = dataset.id ?? (dataset.label ? dataset.label.split("·")[0].trim() : dataset.platform_id);
    const colorKey = dataset.id ?? `${ticker}-${dataset.platform_id ?? "default"}`;
    const color = getColorForKey(colorKey);
    return {
      label: ticker ?? dataset.label,
      fullLabel: dataset.label ?? ticker ?? "",
      data: (dataset.data ?? []).map((value) => (value === null || value === undefined ? null : Number(value))),
      borderColor: color,
      backgroundColor: dataset.backgroundColor ?? hexToRgba(color, 0.12),
      borderWidth: 2.25,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.25,
      fill: false,
      spanGaps: true,
    };
  });

  return { labels, datasets: chartDatasets };
};

const buildHistogramDataset = (state, histogramKey) => {
  const histograms = state?.charts?.histograms ?? {};
  const entries = histograms[histogramKey] ?? [];
  if (!entries.length) {
    return { labels: [], data: [], colors: [] };
  }

  let filtered = entries.filter((entry) => {
    if (!state.activePlatformId) {
      return true;
    }
    return entry.platform_id === state.activePlatformId;
  });

  if (!filtered.length) {
    filtered = entries;
  }

  const labels = filtered
    .map((entry) => entry.label ?? entry.ticker ?? "--")
    .map((label) => label.replace(/\s+/g, " "));
  const data = filtered.map((entry) => Number(entry.value ?? 0));
  const colors = filtered.map((entry) => {
    const colorKey = entry.ticker ?? entry.label ?? entry.platform_id;
    const base = getColorForKey(colorKey);
    return hexToRgba(base, 0.85);
  });

  return { labels, data, colors };
};

const buildTimeseriesConfig = (state) => {
  const { labels, datasets } = buildTimeseriesDataset(state);
  if (!labels.length || !datasets.length) {
    return null;
  }

  const viewportWidth = typeof window !== "undefined" ? window.innerWidth || 1280 : 1280;
  const maxTicks = Math.max(4, Math.floor(viewportWidth / 140));
  const rotation = viewportWidth < 640 ? 30 : 0;
  const chartTheme = getChartTheme();
  ChartGlobal.defaults.color = chartTheme.axisColor;

  return {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: { usePointStyle: true, color: chartTheme.axisColor },
        },
        tooltip: {
          backgroundColor: chartTheme.tooltipBg,
          titleColor: chartTheme.tooltipColor,
          bodyColor: chartTheme.tooltipColor,
          borderColor: chartTheme.tooltipBorder,
          borderWidth: 1,
          callbacks: {
            label(context) {
              const value = context.parsed.y;
              if (value === null || value === undefined) {
                return `${context.dataset.fullLabel || context.dataset.label}: sin datos`;
              }
              return `${context.dataset.fullLabel || context.dataset.label}: ${value.toFixed(2)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            autoSkip: true,
            maxTicksLimit: maxTicks,
            maxRotation: rotation,
            minRotation: rotation,
            color: chartTheme.axisColor,
            callback(value, index) {
              const raw = labels[index] ?? value ?? "";
              const text = raw.toString();
              return text.length > 10 ? text.slice(0, 10) : text;
            },
          },
        },
        y: {
          grid: { color: chartTheme.gridColor },
          ticks: { color: chartTheme.axisColor, callback: (value) => `${value}` },
        },
      },
    },
  };
};

const buildHistogramConfig = (state, histogramKey, datasetLabel) => {
  const { labels, data, colors } = buildHistogramDataset(state, histogramKey);
  if (!labels.length || !data.length) {
    return null;
  }

  const chartTheme = getChartTheme();
  ChartGlobal.defaults.color = chartTheme.axisColor;

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: datasetLabel,
          data,
          backgroundColor: colors,
          hoverBackgroundColor: colors,
          borderColor: colors,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: chartTheme.tooltipBg,
          titleColor: chartTheme.tooltipColor,
          bodyColor: chartTheme.tooltipColor,
          borderColor: chartTheme.tooltipBorder,
          borderWidth: 1,
          callbacks: {
            label(context) {
              const value = context.parsed.y ?? 0;
              return `${context.label}: ${(value * 100).toFixed(2)}%`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxRotation: 60, minRotation: 0, color: chartTheme.axisColor },
        },
        y: {
          beginAtZero: true,
          ticks: {
            callback: (value) => `${(value * 100).toFixed(0)}%`,
            color: chartTheme.axisColor,
            maxTicksLimit: 6,
          },
          grid: { color: chartTheme.gridColor },
        },
      },
    },
  };
};

const buildChartConfig = (state) => {
  const mode = state.chartMode ?? "return_1y";
  switch (mode) {
    case "monthly_change":
      return {
        config: buildHistogramConfig(state, "monthly_change", "Variación mensual"),
        placeholder: "No hay datos de variación mensual para esta selección.",
      };
    case "return_1y":
      return {
        config: buildHistogramConfig(state, "return_1y", "Retorno 1 año"),
        placeholder: "No hay datos de retorno a 1 año para esta selección.",
      };
    case "return_5y":
      return {
        config: buildHistogramConfig(state, "return_5y", "Retorno 5 años"),
        placeholder: "No hay datos de retorno a 5 años para esta selección.",
      };
    case "timeseries":
    default:
      return {
        config: buildTimeseriesConfig(state),
        placeholder: "No hay series disponibles para la plataforma seleccionada.",
      };
  }
};

export const createCharts = (state) => {
  lastState = state;
  const canvas = getCanvas(MAIN_CANVAS_ID);
  if (!canvas) {
    return;
  }

  if (!state || (state.status !== "ready" && state.status !== "refreshing")) {
    destroyCurrentChart();
    ensurePlaceholder("Los gráficos aparecerán cuando los datos estén listos.");
    return;
  }

  const { config, placeholder } = buildChartConfig(state);

  if (!config) {
    destroyCurrentChart();
    ensurePlaceholder(placeholder ?? "Sin datos para graficar.");
    return;
  }

  clearPlaceholder();
  if (currentChart && currentChart.config.type === config.type) {
    applyChartConfig(currentChart, config);
    return;
  }

  destroyCurrentChart();
  currentChart = new ChartGlobal(canvas.getContext("2d"), config);
};

if (typeof window !== "undefined") {
  window.addEventListener("themechange", () => {
    if (!lastState) {
      return;
    }
    createCharts(lastState);
  });
}
