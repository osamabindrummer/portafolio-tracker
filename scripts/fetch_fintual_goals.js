#!/usr/bin/env node

/**
 * Descarga la información privada de metas desde la API de Fintual y escribe
 * un JSON público con metadata adicional para el dashboard. Este script espera
 * que las credenciales se entreguen vía variables de entorno:
 *
 *   - FINTUAL_USER_EMAIL
 *   - FINTUAL_USER_TOKEN
 *
 * El archivo resultante se guarda en public/fintual/goals.json. No se escribirá
 * nada si la descarga falla para proteger el contenido publicado.
 */

const fs = require("fs/promises");
const path = require("path");

const API_BASE_URL = "https://fintual.cl/api/goals";
const OUTPUT_PATH = path.join(__dirname, "..", "public", "fintual", "goals.json");

const readEnv = (name) => {
  const value = process.env[name];
  if (!value || !String(value).trim()) {
    throw new Error(`Variable de entorno requerida ausente: ${name}`);
  }
  return String(value).trim();
};

const fetchGoals = async (email, token) => {
  const url = new URL(API_BASE_URL);
  url.searchParams.set("user_email", email);
  url.searchParams.set("user_token", token);

  const sanitizedUrl = `${url.origin}${url.pathname}`;

  console.info(`Consultando ${sanitizedUrl}…`);

  let response;
  try {
    response = await fetch(url.toString(), {
      headers: {
        Accept: "application/json",
      },
    });
  } catch (error) {
    throw new Error(`No se pudo conectar con la API de Fintual: ${error.message}`);
  }

  if (!response.ok) {
    throw new Error(`La API de Fintual respondió HTTP ${response.status}`);
  }

  try {
    return await response.json();
  } catch (error) {
    throw new Error(`Respuesta inválida desde la API de Fintual: ${error.message}`);
  }
};

const buildPayload = (rawResponse) => {
  const fetchedAt = new Date().toISOString();
  return {
    ...rawResponse,
    fetched_at: fetchedAt,
    source_url: API_BASE_URL,
  };
};

const persistJson = async (payload) => {
  const directory = path.dirname(OUTPUT_PATH);
  await fs.mkdir(directory, { recursive: true });
  const serialized = JSON.stringify(payload, null, 2);
  await fs.writeFile(OUTPUT_PATH, `${serialized}\n`, "utf8");
  console.info(`JSON actualizado en ${OUTPUT_PATH}`);
};

const main = async () => {
  const email = readEnv("FINTUAL_USER_EMAIL");
  const token = readEnv("FINTUAL_USER_TOKEN");

  const goalsData = await fetchGoals(email, token);
  if (!goalsData || typeof goalsData !== "object") {
    throw new Error("La respuesta de /goals está vacía o no es un objeto JSON.");
  }

  const payload = buildPayload(goalsData);
  await persistJson(payload);

  const firstGoal = Array.isArray(payload.data) ? payload.data[0] : null;
  const attributes = firstGoal?.attributes ?? {};
  const nav = attributes.nav ?? "--";
  const deposited = attributes.deposited ?? "--";
  const profit = attributes.profit ?? "--";
  console.info(
    `Primer goal: nav=${nav} · deposited=${deposited} · profit=${profit} (fetched_at=${payload.fetched_at})`,
  );
};

main().catch((error) => {
  console.error(`[fetch_fintual_goals] ${error.message}`);
  process.exitCode = 1;
});
