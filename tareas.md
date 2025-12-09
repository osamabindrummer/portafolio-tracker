# Tareas pendientes

- [ ] Actualizar `scripts/fetch_data.py` para reemplazar `datetime.utcnow()` por `datetime.datetime.now(datetime.UTC)` (o `datetime.now(timezone.utc)`) en `iso_now()` y en el generador offline. Esto elimina el DeprecationWarning observado al ejecutar `python3 scripts/fetch_data.py` y asegura compatibilidad con futuras versiones de Python.
