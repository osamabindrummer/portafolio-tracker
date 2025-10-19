# Formato del archivo `data/latest.json`

## Propósito
Centralizar en un único archivo JSON toda la información necesaria para renderizar la UI del portafolio tracker:
- Datos generales y metadata de generación.
- Estructura de plataformas y tenencias con métricas clave.
- Datos preprocesados para Chart.js (línea 5Y e histogramas 1Y/5Y).
- Información opcional que complemente la UI (ej. embeds o notas adicionales).

El objetivo es que el frontend solo tenga que leer este archivo y no derivar cálculos complejos ni conocer la fuente original de datos.

## Estructura general
```json
{
  "generated_at": "2024-05-27T12:34:56Z",
  "currency": "USD",
  "source": {
    "provider": "yfinance",
    "retrieved_at": "2024-05-27T12:33:00Z",
    "notes": {
      "CFIETFGE": "Mapeado a ARCA:GEG",
      "CFMITNIPSA": "Uso de índice Merval como proxy"
    }
  },
  "platforms": [
    {
      "id": "racional",
      "name": "Racional",
      "color": "#0050B3",
      "holdings": [],
      "summary": {}
    }
  ],
  "charts": {
    "timeseries_5y": {
      "labels": [],
      "datasets": []
    },
    "histograms": {
      "return_1y": [],
      "return_5y": []
    }
  }
}
```

## Detalle por sección

### Campos raíz
- `generated_at` (`string`, ISO 8601): Fecha/hora UTC en la que se generó el JSON. Se utiliza para mostrar “Última actualización”.
- `currency` (`string`): Moneda base en la que se expresan los precios y retornos (ej. `"USD"`).
- `source` (`object`): Metadata sobre el fetch de datos:
  - `provider` (`string`): Servicio usado (`"yfinance"`, `"alpha_vantage"`, etc.).
  - `retrieved_at` (`string`, ISO 8601): Momento del fetch.
  - `notes` (`object`, opcional): Mapeos o particularidades (claves = ticker original, valores = descripción).

### `platforms` (array)
Cada elemento representa una plataforma (Racional, Fintual, etc.).

Campos obligatorios:
- `id` (`string`): Identificador único en minúsculas (`"racional"`).
- `name` (`string`): Nombre legible.
- `color` (`string`): Color principal recomendado para la plataforma en hex.
- `holdings` (`array`): Lista de ETFs/acciones pertenecientes a la plataforma.

Campos opcionales recomendados:
- `summary` (`object`): Agregaciones precalculadas.
  - `total_weight` (`number`): Suma de pesos (debería ser 1.0).
  - `avg_return_1y` (`number`), `avg_return_5y` (`number`).
  - `timestamp_range` (`{ "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" }`).

#### `holdings` (array de objetos)
Para cada instrumento:
- `ticker` (`string`): Símbolo.
- `display_name` (`string`): Nombre descriptivo (ej. `"iShares U.S. Technology ETF"`).
- `weight` (`number`): Porción del portafolio expresada de 0 a 1 (0.35 = 35%).
- `currency` (`string`): Moneda del activo (si difiere del `currency` general).
- `latest_price` (`number`): Precio de cierre ajustado más reciente.
- `metrics` (`object`):
  - `return_1y` (`number`): Retorno porcentual (0.12 = 12%).
  - `return_5y` (`number`): Retorno porcentual 5 años (0.65 = 65%).
  - `daily_change_pct` (`number`): Variación de la última sesión en porcentaje.
  - `daily_change_abs` (`number`, opcional): Cambios absolutos en moneda base.
- `series` (`object`):
  - `price_history` (`array`): Lista de `{ "date": "YYYY-MM-DD", "close": number }` (precios ajustados).
  - `normalized_5y` (`array`): Lista de `{ "date": "YYYY-MM-DD", "value": number }` donde `value` arranca en `100`.
- `status` (`object`, opcional):
  - `missing_data` (`boolean`): Indica si faltan datos recientes.
  - `warnings` (`array`): Mensajes relevantes para mostrar en UI.
- `platform_id` (`string`, redundante pero útil para trazabilidad).

### `charts`
Datos ya estructurados para alimentar Chart.js sin cálculos extra.

- `timeseries_5y` (`object`):
  - `labels` (`array` de `string`): Fechas en orden ascendente (`["2019-05-27", ...]`).
  - `datasets` (`array`):
    - Cada dataset representa un ticker.
    - Campos mínimos:
      - `id` (`string`): Ticker sin espacios.
      - `label` (`string`): Nombre a mostrar en leyenda.
      - `platform_id` (`string`).
      - `borderColor` / `backgroundColor` (`string`): Colores sugeridos.
      - `data` (`array` de `number|null`): Valores normalizados en el mismo orden que `labels`. Se permite `null` cuando no hay dato para una fecha concreta (Chart.js ignora esos puntos).
    - Campos opcionales:
      - `hidden` (`boolean`): Iniciar dataset oculto.
      - `weight` (`number`): Para usar en tooltips personalizados.

- `histograms` (`object`):
  - `return_1y` (`array`):
    - Objetos `{ "ticker": "IYWCL", "platform_id": "racional", "weight": 0.35, "label": "iShares U.S. Technology", "value": 0.28 }`.
  - `return_5y` (`array`):
    - Misma estructura que `return_1y`, con `value` representando el retorno acumulado a 5 años.
  - Al mantener este formato, Chart.js puede generar barras directamente sin cálculos adicionales.

## Consideraciones adicionales
- **Normalización de datos**: Los arrays `price_history` y `normalized_5y` deben compartir la misma longitud y fechas alineadas. Si se usa interpolación, documentarla en `source.notes`.
- **Pesos**: Asegurar que los pesos (`weight`) sumen 1.0 por plataforma para evitar inconsistencias en la UI.
- **Valores numéricos**: Utilizar decimales con precisión razonable (4 decimales). El frontend puede formatear a porcentaje/monedas.
- **Codificación**: Guardar el archivo con UTF-8 sin BOM.
- **Control de versiones**: Si se agrega un campo nuevo, actualizar esta documentación y versionar el esquema (ej. añadir `schema_version` en la raíz).
- **Modo offline**: Si se generan datos deterministas (ej. para pruebas sin conexión), registrar el origen en `source.provider` y detallar la procedencia en `source.notes`.

## Ejemplo resumido
```json
{
  "generated_at": "2024-05-27T12:34:56Z",
  "currency": "USD",
  "source": {
    "provider": "yfinance",
    "retrieved_at": "2024-05-27T12:33:00Z"
  },
  "platforms": [
    {
      "id": "racional",
      "name": "Racional",
      "color": "#0050B3",
      "summary": {
        "total_weight": 1.0,
        "avg_return_1y": 0.18,
        "avg_return_5y": 0.72,
        "timestamp_range": { "start": "2019-05-27", "end": "2024-05-24" }
      },
      "holdings": [
        {
          "ticker": "IYWCL",
          "display_name": "iShares U.S. Technology",
          "platform_id": "racional",
          "weight": 0.35,
          "currency": "USD",
          "latest_price": 152.34,
          "metrics": {
            "return_1y": 0.24,
            "return_5y": 1.05,
            "daily_change_pct": -0.012,
            "daily_change_abs": -1.83
          },
          "series": {
            "price_history": [
              { "date": "2019-05-27", "close": 67.12 },
              { "date": "2019-05-28", "close": 67.40 }
            ],
            "normalized_5y": [
              { "date": "2019-05-27", "value": 100 },
              { "date": "2019-05-28", "value": 100.42 }
            ]
          }
        }
      ]
    }
  ],
  "charts": {
    "timeseries_5y": {
      "labels": ["2019-05-27", "2019-05-28"],
      "datasets": [
        {
          "id": "IYWCL",
          "label": "IYWCL · Racional",
          "platform_id": "racional",
          "borderColor": "#0050B3",
          "backgroundColor": "rgba(0, 80, 179, 0.2)",
          "data": [100, 100.42],
          "weight": 0.35
        }
      ]
    },
    "histograms": {
      "return_1y": [
        { "ticker": "IYWCL", "platform_id": "racional", "label": "IYWCL", "weight": 0.35, "value": 0.24 }
      ],
      "return_5y": [
        { "ticker": "IYWCL", "platform_id": "racional", "label": "IYWCL", "weight": 0.35, "value": 1.05 }
      ]
    }
  }
}
```
