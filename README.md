# Taller MCD — Datos Geoespaciales (Clase 3)

## Entregables

Los entregables de la Clase 3 (Taller MCD — Datos Geoespaciales) del Seminario de Métodos Analíticos de la Empresa - Datos se depositan en `entregables/`, separado por parte:

```
entregables/
├── Parte_1/   # script/notebook, mapa de puntos, tabla de conteo por municipio
└── Parte_2/   # mapa(s) del reto elegido + documento de interpretación (1-2 cuartillas)
```

| Entregable | Estado |
|---|---|
| Documento de interpretación (1-2 cuartillas) | ⏳ pendiente |
| Copia final en `entregables/Parte_1/` y `entregables/Parte_2/` | ⏳ pendiente |

## Caso de uso: Datos Geoespaciales DENUE

Análisis geoespacial de la distribución de sucursales de **AFORE** (Administradoras de Fondos para el Retiro) en México, a partir del **DENUE** (Directorio Estadístico Nacional de Unidades Económicas, INEGI).

## Fuente de datos

- **DENUE (INEGI)** vía su API pública v1 — nombre, actividad económica, dirección y coordenadas de cada establecimiento. Ver método y limitaciones en [`docs/denue_ingestion.md`](docs/denue_ingestion.md).
- **Marco Geoestadístico (INEGI)** (opcional, en `data/external/`): límites municipales/estatales para mapas coropléticos.

## Quickstart (reproducible con `uv`)

```bash
uv sync                          # crea .venv e instala dependencias (ver .python-version)
cp .env.example .env             # agrega tu TOKEN_API_DENUE (gratis, ver docs/denue_ingestion.md)
make download-denue               # descarga el archivo completo por entidad, sin filtrar -> data/raw/denue/
make process-denue                 # limpia coordenadas + clasifica por marca (por entidad + combinado) -> data/processed/denue/
uv run jupyter lab                 # abre notebooks/01_exploracion.ipynb
```

El notebook clasifica cada sucursal por marca de AFORE y genera
`data/processed/afores_denue.gpkg`, `reports/figures/afores_overview.png` y un
**mapa interactivo filtrable por marca**
(`reports/maps/afores_mexico_interactive.html`).

**Importante:** lanza Jupyter desde la raíz del repo (no desde `notebooks/`).

## Comandos

| Comando | Qué hace |
|---|---|
| `make setup` | `uv sync` — crea/actualiza `.venv` y `uv.lock` |
| `make download-denue` | Descarga el archivo completo (JSON + CSV, sin filtrar) -> `data/raw/denue/` |
| `make process-denue` | Limpia coordenadas + clasifica por marca -> `data/processed/denue/` |
| `make lint` / `make format` | `ruff check` / `ruff format` |
| `make test` | `pytest` |
| `make clean` | Limpia cachés y checkpoints |

## Estructura del proyecto

```
GeoEsp_DENUE/
├── config/                  # config.yaml (rutas, parámetros) y crs_config.yaml (proyecciones)
├── data/
│   ├── raw/                 # DENUE completo, sin filtrar (JSON + CSV, con timestamp, no versionado)
│   ├── interim/             # Datos en transformación
│   ├── processed/           # denue/ (CSV limpio + filtrado) + afores_denue.gpkg (con geometría)
│   └── external/            # Capas auxiliares (límites administrativos)
├── notebooks/                # 01_exploracion ... 05_clustering (numerados por etapa)
├── src/
│   ├── ingesta/              # descargar_denue.py — API DENUE v1
│   ├── preprocesamiento/     # limpiar_denue.py — coordenadas, clasificación por marca
│   ├── caracteristicas/      # construir_caracteristicas.py — geometría (GeoDataFrame)
│   ├── analisis_geoespacial/ # densidad.py, proximidad.py, cobertura.py
│   ├── visualizacion/        # mapas_estaticos.py, mapas_interactivos.py
│   └── utilidades/            # entrada_salida.py, utilidades_geo.py
├── reports/
│   ├── figures/               # PNG estáticos
│   └── maps/                  # HTML interactivos (folium)
├── tests/                     # pytest — un archivo por módulo de src/
├── docs/                      # denue_ingestion.md y demás documentación
└── entregables/                # Lo que se sube a evaluación (ver sección académica)
    ├── Parte_1/                # Evidencia de la Réplica
    └── Parte_2/                # Evidencia del Reto
```

## Taller de Ciencia de Datos: Datos Espaciales

Caso de uso propio: **AFOREs a nivel nacional** (las 32 entidades), en vez de
un solo estado/giro como en el ejercicio de clase.

### Parte 1 — Réplica (obligatoria)

| Requisito | Estado |
|---|---|
| Descarga del DENUE (API, `make download-denue`) | ✅ |
| Diccionario de datos (≥5 variables) | ✅ ver tabla abajo |
| Filtro del giro (AFOREs) + reporte de faltantes/duplicados | ✅ `make process-denue` y cifras control en `01_exploracion.ipynb` |
| Conteo de unidades por municipio (tabla) | ⏳ pendiente (hoy el notebook agrega por marca y por estado, falta el corte por municipio) |
| Mapa de puntos | ✅ estático (`reports/figures/`) e interactivo filtrable (`reports/maps/`) |


### Parte 2 — Reto

**Opción x (a elegir):**

| Opción | Descripción | Requisito de rigor |
|---|---|---|
| A. Coroplético normalizado | Densidad de sucursales por municipio | Normalizar por población (por 10,000 hab.) y comparar ranking crudo vs. normalizado |
| B. Heatmap de densidad (KDE) | Mapa de calor de sucursales | Comparar ≥2 bandwidths y cruzar con densidad poblacional |
| C. Proximidad/competencia | Índice de demanda potencial en ≥3 sitios candidatos | Contar competidores en radios de 500 m/1 km/2 km + población por buffer |
| D. Score demográfico (AGEB) | Ranking de zonas por score cuantitativo | Score explícito (población objetivo / competidores cercanos), top 5 zonas |

### Rúbrica 

| Criterio | Puntos | Estado |
|---|---|---|
| Parte 1 completa | 25 | ⏳ falta conteo por municipio |
| Limpieza documentada (faltantes, duplicados) | 10 | ✅ |
| Parte 2: reto + requisito de rigor | 35 | ⏳ pendiente elegir opción |
| Interpretación escrita y justificación | 20 | ⏳ pendiente |
| Código reproducible, comentado, en tiempo | 10 | ✅ |


## Anexos

### Archivos de trabajo

Insumos ya generados que alimentan los entregables (viven en el repo, no en `entregables/`):

| Archivo | Estado |
|---|---|
| Notebook reproducible y comentado | ✅ `notebooks/01_exploracion.ipynb` |
| Mapa(s) generado(s) | ✅ `reports/figures/` y `reports/maps/` |
