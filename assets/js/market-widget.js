const WIDGET_SRC = "https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js";

const SYMBOLS = [
  "NASDAQ:NVDA|1D|USD",
  "NASDAQ:AAPL|1D|USD",
  "NASDAQ:SOXX|1D|USD",
  "NASDAQ:SMH|1D|USD",
  "NASDAQ:INTC|1D|USD",
  "NASDAQ:ARM|1D|USD",
  "AMEX:VTI|1D|USD",
  "NASDAQ:AMD|1D|USD",
  "CBOE:ESGV|1D|USD",
  "AMEX:BLOK|1D|USD",
  "NYSE:KO|1D|USD",
  "NYSE:PHO|1D|USD",
  "NASDAQ:HERO|1D|USD",
  "NASDAQ:RIOT|1D|USD",
  "NYSEARCA:BITO|1D|USD",
  "NASDAQ:MARA|1D|USD",
];

const buildConfig = (theme) => {
  const isDark = theme === "dark";
  return {
    lineWidth: 2,
    lineType: 0,
    chartType: "area",
    fontColor: isDark ? "rgb(177, 182, 190)" : "rgb(106, 109, 120)",
    gridLineColor: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(46, 46, 46, 0.06)",
    volumeUpColor: "rgba(34, 171, 148, 0.5)",
    volumeDownColor: "rgba(247, 82, 95, 0.5)",
    backgroundColor: isDark ? "#131722" : "#ffffff",
    widgetFontColor: isDark ? "#D1D4DC" : "#0F0F0F",
    upColor: "#22ab94",
    downColor: "#f7525f",
    borderUpColor: "#22ab94",
    borderDownColor: "#f7525f",
    wickUpColor: "#22ab94",
    wickDownColor: "#f7525f",
    colorTheme: isDark ? "dark" : "light",
    isTransparent: false,
    locale: "es",
    chartOnly: false,
    scalePosition: "right",
    scaleMode: "Normal",
    fontFamily: "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
    valuesTracking: "1",
    changeMode: "price-and-percent",
    symbols: SYMBOLS.map((symbol) => [symbol]),
    dateRanges: ["1d|1", "1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"],
    fontSize: "10",
    headerFontSize: "medium",
    autosize: true,
    width: "100%",
    height: "100%",
    noTimeScale: false,
    hideDateRanges: false,
    hideMarketStatus: false,
    hideSymbolLogo: false,
  };
};

const renderMarketWidget = (theme) => {
  const host = document.getElementById("tradingview-widget");
  if (!host) {
    return;
  }

  const container = document.createElement("div");
  container.className = "tradingview-widget-container";
  container.innerHTML = `
    <div class="tradingview-widget-container__widget"></div>
    <div class="tradingview-widget-copyright">
      <a href="https://es.tradingview.com/" rel="noopener nofollow" target="_blank">
        <span class="blue-text">Sigue todos los mercados en TradingView</span>
      </a>
    </div>
  `;

  const script = document.createElement("script");
  script.type = "text/javascript";
  script.src = WIDGET_SRC;
  script.async = true;
  script.textContent = JSON.stringify(buildConfig(theme));
  container.appendChild(script);
  host.replaceChildren(container);
};

export const initMarketWidget = () => {
  const currentTheme = document.documentElement.dataset.theme ?? "light";
  renderMarketWidget(currentTheme);
  window.addEventListener("themechange", (event) => {
    renderMarketWidget(event.detail?.theme ?? "light");
  });
};
