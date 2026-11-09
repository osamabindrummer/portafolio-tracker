import { requestJSON } from "./http.js";
import { initTheme } from "./theme.js";
import {
  escapeHTML,
  formatPercent,
  formatDateTime,
  formatDate,
} from "./format.js";
import { readUpdate } from "./update-status.js";

const METRICS = {
  daily_change_pct: "Variación diaria",
  monthly_change_pct: "Variación mensual",
  return_1y: "Retorno 1 año",
  return_5y: "Retorno 5 años",
};
const percent = (value) => formatPercent(value, { signed: false, decimals: 1 });

export const buildUpdateDetails = (entry) => {
  if (!entry)
    return '<p class="data-muted">No hay un intento de actualización registrado en esta sesión.</p>';
  return `<p class="data-update${entry.failed ? " data-update--warning" : ""}">${escapeHTML(entry.message)}</p>
    <p class="data-muted">Último intento registrado en este navegador: ${formatDateTime(entry.recordedAt)}</p>`;
};

export const buildPortfolioDetails = (platforms) =>
  platforms
    .map((platform) => {
      const summary = platform.summary ?? {};
      const rows = platform.holdings
        .map((holding) => {
          const status = holding.status ?? {};
          const notes = [
            status.stale ? "Cotización desactualizada" : null,
            status.missing_data ? "Histórico insuficiente" : null,
            status.retained ? "Se conservó la descarga anterior" : null,
            ...(status.warnings ?? []),
          ].filter(Boolean);
          return `<tr><th scope="row">${escapeHTML(holding.ticker)}</th><td>${escapeHTML(holding.currency)}</td>
      <td>${formatDate(holding.observed_at)}</td><td>${notes.length ? notes.map(escapeHTML).join("<br>") : "Sin advertencias"}</td></tr>`;
        })
        .join("");
      return `<section class="data-platform" aria-label="${escapeHTML(platform.name)}">
    <h4>${escapeHTML(platform.name)}</h4>
    <dl class="data-facts">
      <div><dt>Moneda</dt><dd>${escapeHTML(platform.currency ?? "--")}</dd></div>
      <div><dt>Peso configurado</dt><dd>${percent(summary.configured_weight)}</dd></div>
      <div><dt>Peso con cotizaciones recientes</dt><dd>${percent(summary.fresh_weight)}</dd></div>
      <div><dt>Fechas de cotización</dt><dd>${formatDate(summary.quote_range?.start)} — ${formatDate(summary.quote_range?.end)}</dd></div>
      ${platform.portfolio_as_of ? `<div><dt>Composición de cartera</dt><dd>${formatDate(platform.portfolio_as_of)}</dd></div>` : ""}
    </dl>
    <div class="table-wrapper"><table class="data-coverage"><caption>Peso con datos por período</caption>
      <thead><tr><th scope="col">Métrica</th><th scope="col">Peso con datos</th></tr></thead>
      <tbody>${Object.entries(METRICS)
        .map(
          ([key, label]) =>
            `<tr><th scope="row">${label}</th><td>${percent(summary.coverage?.[key])}</td></tr>`,
        )
        .join("")}</tbody>
    </table></div>
    <div class="table-wrapper"><table class="data-holdings"><caption>Fechas y advertencias por instrumento</caption>
      <thead><tr><th scope="col">Ticker</th><th scope="col">Moneda</th><th scope="col">Última cotización</th><th scope="col">Observaciones</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  </section>`;
    })
    .join("");

export const buildIndicatorDetails = (payload, warning) => {
  const rows = payload.items
    .map((item) => {
      const value = new Intl.NumberFormat("es-CL", {
        minimumFractionDigits: item.decimals,
        maximumFractionDigits: item.decimals,
      }).format(item.value);
      return `<tr><th scope="row">${escapeHTML(item.label)}</th><td>${escapeHTML(value)} ${escapeHTML(item.unit === "PERCENT" ? "%" : item.unit)}</td><td>${formatDate(item.observed_at)}</td></tr>`;
    })
    .join("");
  return `<p class="data-muted">Fuente: ${escapeHTML(payload.source)} · Consulta: ${formatDateTime(payload.fetched_at)}</p>
    ${warning ? `<p>${escapeHTML(warning)}</p>` : ""}
    <div class="table-wrapper"><table><thead><tr><th scope="col">Indicador</th><th scope="col">Valor</th><th scope="col">Fecha de observación</th></tr></thead><tbody>${rows}</tbody></table></div>`;
};

const loadDetails = async () => {
  document.getElementById("update-result").innerHTML =
    buildUpdateDetails(readUpdate());
  // Cada sección carga de forma independiente para mantener lo que sí esté disponible.
  await Promise.allSettled([
    requestJSON("/api/data/latest")
      .then(({ payload, warning }) => {
        document.getElementById("data-source").innerHTML =
          `<p class="data-muted">Portafolio generado: ${formatDateTime(payload.generated_at)} · Fuente de precios: ${escapeHTML(payload.source?.provider ?? "--")}.</p>${warning ? `<p>${escapeHTML(warning)}</p>` : ""}`;
        document.getElementById("portfolio-details").innerHTML =
          buildPortfolioDetails(payload.platforms);
      })
      .catch((error) => {
        document.getElementById("portfolio-details").textContent =
          `No se pudieron cargar los detalles del portafolio: ${error.message}`;
      }),
    requestJSON("/api/indicators")
      .then(({ payload, warning }) => {
        document.getElementById("indicator-details").innerHTML =
          buildIndicatorDetails(payload, warning);
      })
      .catch((error) => {
        document.getElementById("indicator-details").textContent =
          `No se pudieron cargar los indicadores: ${error.message}`;
      }),
  ]);
};

if (document.getElementById("portfolio-details")) {
  initTheme();
  void loadDetails();
}
