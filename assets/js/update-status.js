const STORAGE_KEY = "portfolioTracker:lastUpdateResult";

// Sólo guardamos el resultado del intento, sin copiar los datos del portafolio.
export const rememberUpdate = (result) => {
  const entry = { ...result, recordedAt: new Date().toISOString() };
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entry));
  } catch {
    // La aplicación funciona aunque el navegador bloquee el almacenamiento.
  }
  return entry;
};

export const readUpdate = () => {
  try {
    const entry = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY));
    return entry &&
      typeof entry.message === "string" &&
      typeof entry.recordedAt === "string"
      ? entry
      : null;
  } catch {
    return null;
  }
};
