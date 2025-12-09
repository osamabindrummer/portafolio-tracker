# Plan DIVO: eliminación de CFMDIVO y aumento de CFMITNIPSA

## Contexto
- Racional fusionó el ETF Acciones Chilenas con Dividendos (CFMDIVO) dentro de Acciones Chilenas IPSA (CFMITNIPSA) desde el 1 de diciembre.
- El portafolio Racional del tracker debe reflejar solo cinco holdings y recalcular todo lo que dependa de la ponderación (CFMITNIPSA pasa de 15 % a 20 %).
- Afecta tanto la generación del JSON (script Python + workflow) como el frontend que consume `data/latest.json` y la documentación que describe la composición.

## Tareas
1. **Actualizar la configuración base del generador**
   - Editar `scripts/fetch_data.py` → sección `PLATFORM_CONFIG['racional']` eliminando el bloque de `HoldingConfig` para `CFMDIVO.SN` y cambiando `weight` de `CFMITNIPSA.SN` a `0.20`.
   - Ajustar el diccionario `SAMPLE_BEHAVIOR` (remover entrada `CFMDIVO.SN` y, si corresponde, recalibrar el perfil de `CFMITNIPSA.SN` para el nuevo peso) para evitar KeyError en modo `--offline`.
   - Confirmar que cualquier lógica auxiliar (notas de `generate_online_payload`, validaciones de sumatoria de pesos, etc.) queda consistente con cinco holdings.

2. **Regenerar y validar `data/latest.json`**
   - Ejecutar `python scripts/fetch_data.py` (idealmente en modo en línea) para recrear el dataset sin `CFMDIVO` y con el nuevo peso de `CFMITNIPSA`.
   - Revisar que en la plataforma `racional` ahora existan 5 objetos dentro de `holdings`, que `summary.total_weight` siga en `1.0` y que las métricas ponderadas se recalculen con los nuevos pesos.
   - Verificar que `charts.timeseries_5y.datasets`, `charts.histograms.monthly_change`/`return_1y`/`return_5y` ya no incluyan `CFMDIVO` y que la entrada de `CFMITNIPSA` muestre `weight: 0.2`.
   - Correr los validadores (`python -m json.tool`, `python scripts/validate_json.py data/latest.json`) para asegurar el payload antes de commitear.

3. **Ajustar la capa de frontend/UI**
   - Actualizar `assets/js/ui.js` removiendo `CFMDIVO.SN` del mapa `RACIONAL_DISPLAY_NAMES`; buscar otras referencias directas a `CFMDIVO` en `assets/js/*.js` e `index.html` para limpiarlas.
   - Probar la carga local (`python -m http.server`) con el JSON regenerado para confirmar que las tablas de holdings, tarjetas de métricas y gráficos funcionan sin el ticker eliminado (sin celdas vacías ni porcentajes incorrectos).
   - Validar que el selector de Racional muestre cinco filas y que los cálculos de `%` se formateen correctamente tras el reequilibrio.

4. **Actualizar documentación y artefactos de referencia**
   - Modificar `plan.md` (sección 3.1 "Inventario de tickers y pesos") para reflejar los nuevos pesos de Racional.
   - Añadir una entrada en `changelog.md` mencionando la absorción de CFMDIVO y el consecuente ajuste en el tracker.
   - Si existe otra documentación (README, notas, embeds) donde se detalle la lista de ETFs de Racional, reemplazar la mención a CFMDIVO y explicar brevemente que CFMITNIPSA ahora concentra 20 %.

5. **QA y automatización**
   - Correr `python scripts/fetch_data.py --offline` para asegurar que el modo determinista siga funcionando después de eliminar la entrada del diccionario.
   - Revisar `.github/workflows/update-data.yml` para confirmar que no requiere cambios adicionales (la lógica seguirá apuntando al script actualizado) y, opcionalmente, forzar una ejecución manual tras merge para popular `data/latest.json` en producción.
   - Considerar añadir una verificación en `scripts/validate_json.py` que confirme que la suma de pesos por plataforma sea 1.0; esto evitará que futuros merges reintroduzcan desbalances.
