const STORAGE_KEY = "portafolio-tracker:theme";
let cachedPreference = null;

const getStorage = () => {
  try {
    if (typeof window === "undefined") {
      return null;
    }
    return window.localStorage;
  } catch (error) {
    return null;
  }
};

const getSystemPreference = () => {
  if (typeof window === "undefined") {
    return "light";
  }
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

const updateToggleButton = (theme) => {
  const toggleButton = document.getElementById("theme-toggle");
  if (!toggleButton) {
    return;
  }

  const isDark = theme === "dark";
  toggleButton.dataset.theme = theme;
  toggleButton.setAttribute("aria-pressed", String(isDark));
  const nextLabel = isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
  toggleButton.setAttribute("aria-label", nextLabel);
  toggleButton.title = nextLabel;

  const srLabel = toggleButton.querySelector(".theme-toggle__sr-label");
  if (srLabel) {
    srLabel.textContent = nextLabel;
  }
};

const applyTheme = (theme) => {
  const root = document.documentElement;
  if (!root) {
    return;
  }

  const nextTheme = theme === "dark" ? "dark" : "light";
  if (root.dataset.theme === nextTheme) {
    updateToggleButton(nextTheme);
    return;
  }

  root.dataset.theme = nextTheme;
  updateToggleButton(nextTheme);
  window.dispatchEvent(new CustomEvent("themechange", { detail: { theme: nextTheme } }));
};

const resolveInitialTheme = () => {
  const storage = getStorage();
  if (storage) {
    const stored = storage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      cachedPreference = stored;
      return stored;
    }
  }

  return getSystemPreference();
};

const watchSystemPreference = () => {
  if (typeof window === "undefined" || !window.matchMedia) {
    return;
  }

  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = (event) => {
    if (cachedPreference) {
      return;
    }
    applyTheme(event.matches ? "dark" : "light");
  };

  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener("change", handler);
  } else if (mediaQuery.addListener) {
    mediaQuery.addListener(handler);
  }
};

const setupToggle = () => {
  const toggleButton = document.getElementById("theme-toggle");
  if (!toggleButton) {
    return;
  }

  toggleButton.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    const storage = getStorage();
    const systemPreference = getSystemPreference();

    if (nextTheme === systemPreference) {
      cachedPreference = null;
      if (storage) {
        storage.removeItem(STORAGE_KEY);
      }
    } else {
      cachedPreference = nextTheme;
      if (storage) {
        storage.setItem(STORAGE_KEY, nextTheme);
      }
    }

    applyTheme(nextTheme);
  });
};

export const initTheme = () => {
  if (typeof document === "undefined") {
    return;
  }

  const initialTheme = resolveInitialTheme();
  applyTheme(initialTheme);
  watchSystemPreference();
  setupToggle();
};
