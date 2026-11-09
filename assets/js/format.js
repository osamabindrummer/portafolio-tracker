// Formatos compartidos por el portafolio y su página de información.
export const escapeHTML = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );

export const formatPercent = (value, { signed = true, decimals = 2 } = {}) => {
  if (!Number.isFinite(value)) return "--";
  const formatted = new Intl.NumberFormat("es-CL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(value * 100));
  const sign = signed && value !== 0 ? (value > 0 ? "+" : "-") : "";
  return `${sign}${formatted}%`;
};

export const formatDateTime = (value) => {
  const date = new Date(value ?? "");
  return Number.isNaN(date.getTime())
    ? "--"
    : new Intl.DateTimeFormat("es-CL", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "America/Santiago",
      }).format(date);
};

export const formatDate = (value) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value ?? "")) return "--";
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isNaN(date.getTime())
    ? "--"
    : new Intl.DateTimeFormat("es-CL", {
        dateStyle: "medium",
        timeZone: "UTC",
      }).format(date);
};
