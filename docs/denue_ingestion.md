# Ingesta de datos DENUE 

INEGI ofrece dos vías para obtener datos del DENUE:

1. **Descarga masiva** (`https://www.inegi.org.mx/app/descarga/?ti=6`): entrega un
   paquete con un ejecutable de Windows (`DescargaMasivaApp.exe`) que lee un
   manifiesto de sesión (`DescargaMasivaOD.xml`) y descarga los archivos. No
   expone una URL estática y reproducible por script, y depende de un binario
   de Windows — no es viable para un pipeline automatizado y multiplataforma.
2. **API DENUE v1** (`https://www.inegi.org.mx/servicios/api_denue.html`):
   servicio REST documentado, con token gratuito, que permite consultar
   establecimientos por texto libre, entidad federativa y paginación.

## Método de descarga

Se usa la **API DENUE v1**, endpoint `BuscarEntidad`, iterando por término de
búsqueda (`AFORE`) y por entidad federativa (`01` a `32`, **siempre con dos
dígitos**), paginando en bloques de hasta 1000 registros (límite documentado
por llamada).

Implementado en [`src/ingesta/descargar_denue.py`](../src/ingesta/descargar_denue.py).

## Artefactos generados

**Se genera un archivo independiente por cada entidad federativa** configurada
en `denue.codigos_entidad` (no un único archivo nacional). Esto aplica tanto a
la descarga como a la limpieza.

`make download-denue` (`src/ingesta/descargar_denue.py`) escribe, por cada
entidad con al menos un registro, dos archivos con el mismo timestamp en
`data/raw/denue/`: exactamente lo que devolvió la API para esa entidad,
**sin ningún filtro ni transformación** (ni siquiera deduplicación).

| Archivo | Carpeta | Contenido |
|---|---|---|
| `denue_afore_<entidad>_<timestamp>.json` | `data/raw/denue/` | Respuesta cruda de la API para esa entidad, sin deduplicar ni transformar. |
| `denue_afore_<entidad>_<timestamp>.csv` | `data/raw/denue/` | Mismos registros que el JSON (incluyendo duplicados, si los hay), aplanados a tabla (`pandas.json_normalize`) — mismo contenido, otro formato. |

`make process-denue` (`src/preprocesamiento/limpiar_denue.py`) toma todos los
CSV crudos de la corrida (misma marca de tiempo) más reciente — uno por
entidad — y escribe en `data/processed/denue/` los artefactos **ya
corregidos** — esta es la única capa con datos transformados:

| Archivo | Carpeta | Contenido |
|---|---|---|
| `denue_afore_limpio_<entidad>_<timestamp>.csv` | `data/processed/denue/` | Registros crudos de esa entidad, con coordenadas inválidas descartadas y columnas `afore_marca`/`municipio`/`estado` agregadas. |
| `denue_afore_limpio_<timestamp>.csv` (sin entidad) | `data/processed/denue/` | **Vista nacional**: todas las entidades de la corrida combinadas en un solo CSV ya limpio. Solo se genera cuando hay más de una entidad. |
| `denue_profuturo_<entidad>_<timestamp>.csv` | `data/processed/denue/` | Subconjunto deduplicado y filtrado por `denue.palabra_clave_subconjunto` (por defecto `PROFUTURO`) sobre nombre/razón social, por entidad — se genera junto con la descarga, no con la limpieza. |

Ambas carpetas de `descargar_denue.py` son configurables (`config/config.yaml`
→ `denue.directorio_crudo` / `denue.directorio_procesado`, o
`--directorio-crudo` / `--directorio-procesado` en su CLI). El filtro de
subconjunto también es configurable (`denue.palabra_clave_subconjunto` o
`--palabra-clave-subconjunto`) y se puede desactivar pasando `""`. Si una
entidad falla o no devuelve registros, se omite (con un log de advertencia) y
la corrida continúa con el resto.

## Cómo obtener el token y configurarlo

1. Entra a <https://www.inegi.org.mx/servicios/api_denue.html> y busca la
   opción de registro (es gratuito).
2. Llena el formulario de registro (nombre, correo, uso previsto de la API) y
   envíalo. INEGI te muestra o envía por correo tu token personal.
3. En la raíz del proyecto, crea tu archivo `.env` a partir de la plantilla
   (si aún no existe):

   ```bash
   cp .env.example .env
   ```

4. Abre `.env` y pega tu token en la variable `TOKEN_API_DENUE`:

   ```
   TOKEN_API_DENUE=tu_token_aqui
   ```

5. Guarda el archivo. **Nunca** pegues el token directamente en el código ni
   en `config/config.yaml` — `.env` ya está en `.gitignore`, así que no se
   sube al repositorio.
6. Verifica que quedó bien configurado corriendo la descarga:

   ```bash
   make download-denue
   ```

   Si el token falta o es inválido, el script falla con un mensaje claro
   (`Falta TOKEN_API_DENUE...` o un error HTTP de la API) en vez de fallar
   silenciosamente.

## Limitaciones conocidas

- **El código de entidad SIEMPRE debe tener dos dígitos** (`01`-`32`). Con un
  solo dígito (ej. `9` en vez de `09`) la API responde HTTP 200 con el cuerpo
  vacío — sin ningún error explícito — para las 9 primeras entidades
  (Aguascalientes a Ciudad de México). Verificado con `curl` directo contra
  la API real. `CODIGOS_ENTIDAD_DEFECTO` en `descargar_denue.py` ya genera
  los códigos con cero a la izquierda (`f"{i:02d}"`); si defines
  `denue.codigos_entidad` manualmente en `config/config.yaml`, usa siempre
  dos dígitos.
- El endpoint `BuscarEntidad` hace *match* de texto libre contra nombre/razón
  social y actividad económica, no contra el código SCIAN exacto. Se eligió
  el término `AFORE` porque las 10 administradoras autorizadas en México lo
  usan en su nombre comercial. **Validar en `notebooks/01_exploracion.ipynb`**
  que la cobertura sea completa (comparar contra el listado oficial de AFOREs
  de CONSAR) y ampliar `denue.terminos_busqueda` en `config/config.yaml` si
  hace falta (ej. nombres de marca específicos).
- La documentación pública de la API no especifica límites de *rate limiting*;
  el script incluye pausas configurables (`segundos_espera`) y reintentos con
  backoff exponencial (`tenacity`) para tolerar fallos transitorios.
- Los nombres exactos de los campos devueltos por la API (`Id`, `Nombre`,
  `Latitud`, `Longitud`, etc.) ya se confirmaron contra la respuesta real y
  quedaron documentados en `notebooks/01_exploracion.ipynb` y en
  `src/preprocesamiento/limpiar_denue.py`.
