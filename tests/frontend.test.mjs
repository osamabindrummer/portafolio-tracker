import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { rememberUpdate, readUpdate } from "../assets/js/update-status.js";
import {
  requestJSON,
  readPreference,
  writePreference,
} from "../assets/js/http.js";

const elements = new Map();
const makeElement = () => ({
  innerHTML: "",
  textContent: "",
  dataset: {},
  classList: { add() {}, remove() {}, toggle() {} },
});
const chartConfigs = [];
class ChartStub {
  static defaults = { font: {} };
  constructor(context, config) {
    this.config = config;
    chartConfigs.push(config);
  }
  destroy() {}
  update() {}
}
const session = new Map();
globalThis.window = {
  sessionStorage: {
    getItem: (key) => session.get(key) ?? null,
    setItem: (key, value) => session.set(key, value),
  },
  Chart: ChartStub,
  addEventListener() {},
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
};
globalThis.document = {
  getElementById: (id) => elements.get(id) ?? null,
  documentElement: {},
};
const { createCharts } = await import("../assets/js/charts.js");
const { renderUI } = await import("../assets/js/ui.js");

// Los escenarios son secuenciales porque comparten el DOM simulado.
test("los mensajes útiles de HTTP se conservan y un JSON vacío se rechaza", async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 500,
    json: async () => ({ message: "Se conserva el snapshot anterior" }),
  });
  await assert.rejects(requestJSON("/api/test"), /Se conserva/);
  globalThis.fetch = async () => ({ ok: true, json: async () => null });
  await assert.rejects(requestJSON("/api/test"), /JSON válido/);
});

test("una solicitud atascada termina con un mensaje recuperable", async () => {
  globalThis.fetch = (url, { signal }) =>
    new Promise((resolve, reject) => {
      signal.addEventListener("abort", () =>
        reject(Object.assign(new Error(), { name: "AbortError" })),
      );
    });
  await assert.rejects(
    requestJSON("/api/test", { timeout: 5 }),
    /tardó demasiado/,
  );
});

test("bloquear localStorage no impide utilizar la vista", () => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    get() {
      throw new Error("Bloqueado");
    },
  });
  assert.equal(readPreference("theme"), null);
  assert.doesNotThrow(() => writePreference("theme", "dark"));
});

test("un gráfico sin datos de la plataforma seleccionada no usa los de otra", () => {
  let placeholder = null;
  const canvas = {
    ...makeElement(),
    getContext() {},
    parentElement: {
      querySelector: () => placeholder,
      appendChild(p) {
        placeholder = p;
      },
    },
  };
  elements.set("main-chart", canvas);
  document.createElement = () => makeElement();
  createCharts({
    status: "ready",
    activePlatformId: "fintual",
    chartMode: "return_1y",
    charts: {
      histograms: {
        return_1y: [{ platform_id: "racional", ticker: "OTRO", value: 0.1 }],
      },
    },
  });
  assert.equal(chartConfigs.length, 0);
  assert.match(placeholder.textContent, /No hay datos/);
  elements.delete("main-chart");
});

test("la vista principal conserva las tablas y omite las explicaciones adicionales", () => {
  for (const id of [
    "metrics-cards",
    "holdings-tables",
    "last-update",
    "refresh-status",
  ])
    elements.set(id, makeElement());
  const platforms = [
    {
      id: "racional",
      name: "Racional",
      currency: "CLP",
      summary: {
        configured_weight: 1,
        coverage: { return_1y: 0.8 },
        quote_range: { start: "2026-11-01", end: "2026-11-06" },
      },
      holdings: [
        {
          ticker: "TEST",
          display_name: '<img src=x onerror="alert(1)">',
          currency: "CLP",
          observed_at: "2026-11-06",
          status: {
            stale: true,
            warnings: ["Se conservó el histórico anterior"],
          },
          metrics: {},
          weight: 1,
        },
      ],
    },
  ];
  const state = {
    status: "ready",
    platforms,
    charts: {},
    activePlatformId: "racional",
  };
  renderUI(state);
  assert.match(elements.get("holdings-tables").innerHTML, /&lt;img/);
  assert.doesNotMatch(
    elements.get("holdings-tables").innerHTML,
    /2026-11-06|Peso configurado|Advertencias de datos|Desactualizada/,
  );
  assert.doesNotMatch(
    elements.get("metrics-cards").innerHTML,
    /Peso con datos|80,0%/,
  );
  elements.get("holdings-tables").innerHTML = "tabla conservada";
  renderUI({
    ...state,
    chartMode: "timeseries",
    refreshFailed: true,
    statusMessage: "No se pudo actualizar",
  });
  assert.equal(elements.get("holdings-tables").innerHTML, "tabla conservada");
  assert.match(
    elements.get("refresh-status").textContent,
    /Datos y metodología/,
  );
  assert.doesNotMatch(
    elements.get("refresh-status").textContent,
    /parcial|No se pudo/,
  );
});

test("un fallo de actualización mantiene las tablas cargadas y permite reintentar", async () => {
  document.documentElement.dataset = { theme: "light" };
  elements.set("refresh-button", makeElement());
  elements.get("refresh-button").setAttribute = () => {};
  const payload = {
    generated_at: "2026-11-09T12:00:00Z",
    platforms: [{ id: "fintual", name: "Fintual", holdings: [], summary: {} }],
    charts: {},
  };
  globalThis.fetch = async (url, options) => ({
    ok: options.method !== "POST",
    status: options.method === "POST" ? 500 : 200,
    json: async () =>
      options.method === "POST" ? { message: "Fuente caída" } : payload,
    headers: { get: () => null },
  });
  await import("../assets/js/app.js");
  // La carga inicial es asíncrona y termina en el siguiente turno del bucle.
  await new Promise((resolve) => setImmediate(resolve));
  const previous = elements.get("holdings-tables").innerHTML;
  assert.match(previous, /Fintual/);
  const originalError = console.error;
  console.error = () => {};
  try {
    await elements.get("refresh-button").onclick();
  } finally {
    console.error = originalError;
  }
  assert.equal(elements.get("holdings-tables").innerHTML, previous);
  assert.match(
    elements.get("refresh-status").textContent,
    /Datos y metodología/,
  );
  assert.equal(readUpdate().message, "Fuente caída");
  assert.equal(elements.get("refresh-button").disabled, false);
});

test("el resultado de actualización se conserva al navegar a la página de datos", () => {
  rememberUpdate({
    failed: true,
    message: "Actualización parcial: se conserva el portafolio.",
  });
  assert.match(readUpdate().message, /Actualización parcial/);
  assert.equal(readUpdate().failed, true);
  assert.ok(readUpdate().recordedAt);
});

test("la página de datos reúne cobertura, fechas y advertencias y escapa sus textos", async () => {
  const { buildPortfolioDetails, buildUpdateDetails } = await import(
    "../assets/js/data-page.js"
  );
  const details = buildPortfolioDetails([
    {
      id: "fintual",
      name: "Fintual",
      currency: "USD",
      portfolio_as_of: "2026-10-29",
      summary: {
        configured_weight: 0.933,
        fresh_weight: 0,
        coverage: { return_1y: 0.8 },
        quote_range: { start: "2026-09-08", end: "2026-10-30" },
      },
      holdings: [
        {
          ticker: "TEST",
          currency: "USD",
          observed_at: "2026-10-30",
          status: { stale: true, warnings: ['<img src=x onerror="alert(1)">'] },
        },
      ],
    },
  ]);
  assert.match(details, /Peso configurado|Peso con datos/);
  assert.match(details, /93,3%/);
  assert.match(details, /80,0%/);
  assert.match(details, /2026/);
  assert.match(details, /Cotización desactualizada/);
  assert.match(details, /&lt;img/);
  assert.doesNotMatch(details, /<img/);
  const result = buildUpdateDetails({
    failed: true,
    message: "Actualización parcial <script>",
    recordedAt: new Date().toISOString(),
  });
  assert.match(result, /Actualización parcial &lt;script&gt;/);
  assert.match(result, /data-update--warning/);
});

test("ambas páginas enlazan entre sí y la principal no contiene la explicación de métricas", () => {
  const main = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const details = readFileSync(
    new URL("../datos.html", import.meta.url),
    "utf8",
  );
  assert.match(main, /<footer[^>]*>[\s\S]*href="\/datos.html">Datos y metodología[\s\S]*<\/footer>/);
  assert.doesNotMatch(main.match(/<header[\s\S]*?<\/header>/)[0], /Datos y metodología/);
  assert.match(main, /id="refresh-status" class="sr-only"/);
  assert.doesNotMatch(
    main,
    /no representan la rentabilidad|Peso con datos|Peso configurado/,
  );
  assert.match(details, /href="\/">Volver al portafolio/);
  assert.match(details, /no incluyen comisiones/);
});
