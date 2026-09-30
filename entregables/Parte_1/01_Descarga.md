# 01 - Descarga

**Descarga el DENUE de tu entidad desde el sitio de INEGI.**


## Método

En vez de la descarga manual desde el portal de INEGI, se usa la **API pública DENUE v1**
(`https://www.inegi.org.mx/app/api/denue/v1/consulta/`), endpoint `BuscarEntidad`.  (detalle completo en
[`docs/denue_ingestion.md`](../../docs/denue_ingestion.md)).

El script (`src/ingesta/descargar_denue.py`) consulta el término de búsqueda `AFORE` contra
las 32 entidades federativas, paginando resultados, y guarda la respuesta cruda sin transformar
**en un archivo independiente por entidad** (no un archivo nacional único).

## Pasos para reproducir la descarga

1. Instalar dependencias: `uv sync`.
2. Obtener un token gratuito en <https://www.inegi.org.mx/servicios/api_denue.html> y copiarlo
   a `.env` (variable `TOKEN_API_DENUE`), a partir de `.env.example`.
3. Ejecutar la descarga: `make download-denue` (equivalente a
   `uv run python src/ingesta/descargar_denue.py`).
4. El script genera, **por cada entidad federativa** (con timestamp, no versionado en git):
   - `data/raw/denue/denue_afore_<entidad>_<timestamp>.json` — respuesta cruda de la API, sin deduplicar ni filtrar.
   - `data/raw/denue/denue_afore_<entidad>_<timestamp>.csv` — mismos registros, aplanados a tabla (mismo contenido que el JSON, ningún filtro).
   - `data/processed/denue/denue_profuturo_<entidad>_<timestamp>.csv` — registros deduplicados y filtrados por marca Profuturo (únicas transformaciones del pipeline).

**Evidencia:** [`src/ingesta/descargar_denue.py`](../../src/ingesta/descargar_denue.py),
[`docs/denue_ingestion.md`](../../docs/denue_ingestion.md) y las cifras de control impresas al
correr `make download-denue`.
