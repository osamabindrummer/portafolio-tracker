---
name: actualizar-risky-norris
description: Actualiza los ocho principales holdings de Fintual Risky Norris en Portafolio Tracker usando la cartera oficial, su fecha y sus porcentajes, conservando tablas, gráficos e históricos. Usar cuando el usuario solicite actualizar esta cartera.
---

# Actualizar Risky Norris

Trabajar en el checkout vigente de `portafolio-tracker` (en este equipo: `/Users/dsj-imac/Developer/portafolio-tracker`). Leer sus instrucciones y revisar el estado Git; conservar cambios ajenos. Este proceso se ejecuta bajo instrucción del usuario, sin crear automatizaciones. Commit, push y despliegue requieren autorización de la sesión; actualizar localmente no implica haber actualizado producción.

## Fuente y composición

1. Abrir https://fintual.cl/risky-norris y leer **Cartera de Risky Norris**. Esperar a que termine «Cargando cartera del fondo». Si el lector web no devuelve contenido, usar el navegador conectado.
2. Registrar la fecha que aparece **en esa sección**, los primeros ocho instrumentos en el orden visible, sus nombres y sus porcentajes respecto al patrimonio. La fecha de consulta y la de cotizaciones son distintas. No usar la fecha de otra sección por inferencia.
3. Verificar los símbolos para consultar históricos de instrumentos nuevos o ambiguos con el emisor o bolsa oficial. Conservar el ticker visible de Fintual y usar `fetch_symbol` para la cotización correcta. Por ejemplo, SPXS de Invesco S&P 500 UCITS ETF acumulativo cotiza en Londres como `SPXS.L` en Yahoo; `SPXS` de EE. UU. identifica otro producto. No sustituir por un ETF parecido.
4. Si falta fecha, porcentaje, identidad o hay menos de ocho instrumentos verificables, informar la ambigüedad antes de sobrescribir datos. No reutilizar cifras de una ejecución anterior como si fueran actuales.

## Aplicación en el tracker

- La composición canónica está en `PLATFORM_CONFIG["fintual"]` de `scripts/fetch_data.py`. Actualizar los ocho `HoldingConfig`, `portfolio_as_of` (ISO `AAAA-MM-DD`) y `portfolio_source_url`. Los pesos son fracciones: 17,95% → `0.1795`. No normalizarlos a 100%; los ocho holdings representan una parte del fondo.
- Ejecutar `.venv/bin/python -m scripts.update_fintual`. El helper conserva históricos conocidos, consulta los nuevos con yfinance, recalcula el resumen y reconstruye series e histogramas. Conserva las otras plataformas y no guarda si faltan históricos reales. Nunca usar `--offline` para reemplazar la semilla operativa.
- Si una consulta falla, revisar identidad y fuente; conservar el archivo previo, explicar qué falta y no inventar series. Si el helper necesita adaptarse por cambios de arquitectura, seguir el flujo vigente y preservar esas mismas garantías.
- `assets/js/ui.js` usa `portfolio_as_of` para el título `Fintual - Risky Norris (cartera al dd de mes de yyyy)`, manteniendo el hyperlink oficial. No fijar una fecha en HTML ni modificar la fecha de cotizaciones por un cambio de composición.
- `backend/portfolio_refresh.py:fetch_latest_payload` reconcilia un Blob de composición anterior con la configuración y los históricos de `data/latest.json`. Verificar ese caso: publicar sólo el frontend o cambiar sólo la semilla puede dejar datos antiguos en producción.

## Verificación y entrega

- Validar `.venv/bin/python -m scripts.validate_json data/latest.json`, sintaxis Python/JS y correspondencia de orden, pesos, símbolos y fecha entre configuración, holdings y gráficos.
- Comprobar que otras plataformas conservan sus datos; verificar el resumen ponderado y que se retiraron de gráficos los holdings que salieron de los primeros ocho.
- Verificar en navegador tabla, título, link y gráficos. Para vista local respetar el puerto documentado `127.0.0.1:3001` y comprobar que esté libre; no abrir otro puerto por cuenta propia ni dar por válido un proceso ajeno.
- Si hay autorización para publicar, seguir el despliegue vigente y verificar `/api/data/latest` y la página servida: ocho instrumentos correctos, fecha oficial y gráficos consistentes. No afirmar publicación sólo por un push o build iniciado.
- Entregar fecha, ocho holdings y porcentajes, validaciones y estado local/publicado. Citar la página oficial consultada. Indicar limitaciones reales: los retornos calculados de los holdings seleccionados no son la rentabilidad histórica efectiva del fondo activo.
