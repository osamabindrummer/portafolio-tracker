// Todas las peticiones tienen un plazo y conservan el mensaje útil del servidor.
export const requestJSON = async (endpoint, { body, timeout = 12000 } = {}) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(endpoint, {
      method: body === undefined ? "GET" : "POST",
      cache: "no-store",
      signal: controller.signal,
      ...(body === undefined
        ? {}
        : {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.message || `HTTP ${response.status}`);
    }
    if (!payload || typeof payload !== "object") {
      throw new Error("El servidor no entregó un JSON válido.");
    }
    return {
      payload,
      warning: response.headers.get("X-Portfolio-Warning") || null,
    };
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(
        "La solicitud tardó demasiado. Puedes intentarlo nuevamente.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
};

export const readPreference = (key) => {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

export const writePreference = (key, value) => {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* La vista sigue funcionando si el navegador no permite guardar preferencias. */
  }
};
