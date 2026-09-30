"""Descarga sucursales de AFOREs desde la API pública del DENUE (INEGI).

Fuente: DENUE API v1 - https://www.inegi.org.mx/servicios/api_denue.html
Se usa el endpoint ``BuscarEntidad`` (búsqueda por texto libre + entidad
federativa) en vez de la "descarga masiva" del portal INEGI, porque esta
última depende de un ejecutable de Windows con manifiesto de sesión y no
es automatizable de forma reproducible en un pipeline.

Requiere un token gratuito de la API, provisto vía la variable de entorno
``TOKEN_API_DENUE`` (ver ``.env.example``). Nunca hardcodear el token.

Genera, **un archivo por entidad federativa**:
- En ``data/raw/denue/`` (sin ningún filtro ni deduplicación): el JSON tal
  como lo entrega la API, y un CSV con esos mismos registros aplanados
  (``pandas.json_normalize``) — mismo contenido, dos formatos.
- En ``data/processed/denue/``: un CSV deduplicado y filtrado por
  ``palabra_clave_subconjunto`` (por defecto "PROFUTURO") sobre nombre/razón
  social — únicas transformaciones del pipeline.

Uso:
    uv run src/ingesta/descargar_denue.py
    uv run src/ingesta/descargar_denue.py --termino-busqueda AFORE --entidades 09 15
    uv run src/ingesta/descargar_denue.py --palabra-clave-subconjunto "PROFUTURO"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

BASE_API_DENUE = "https://www.inegi.org.mx/app/api/denue/v1/consulta"
MAX_REGISTROS_POR_LLAMADA = 1000
# La API exige el código de entidad con dos dígitos (con cero a la izquierda
# para 1-9, ej. "09" para Ciudad de México). Con un solo dígito ("9") la API
# responde HTTP 200 con cuerpo vacío, sin error explícito — verificado contra
# la API real.
CODIGOS_ENTIDAD_DEFECTO: list[str] = [f"{i:02d}" for i in range(1, 33)]
SEGUNDOS_TIMEOUT_SOLICITUD = 30
# La API DENUE devuelve "Nombre"/"Razon_social" (PascalCase); la descarga
# masiva del portal INEGI usa los nombres del diccionario oficial de datos
# ("nom_estab"/"raz_social"). Se incluyen ambas convenciones para que el
# filtro de subconjunto funcione con cualquiera de las dos fuentes.
COLUMNAS_NOMBRE_CANDIDATAS: tuple[str, ...] = (
    "Nombre",
    "nombre",
    "nom_estab",
    "Razon_social",
    "razon_social",
    "raz_social",
)
# Mapeo de los campos de la API DENUE (PascalCase) a los encabezados del
# diccionario oficial de datos de la descarga masiva de INEGI (snake_case).
# Se usa solo para la ruta legado denue_inegi_09_.csv, que scripts existentes
# (ej. entregables/Parte_1/01_leer_denue.R) esperan leer con esos nombres.
MAPEO_COLUMNAS_API_A_INEGI: dict[str, str] = {
    "Id": "id",
    "CLEE": "clee",
    "Nombre": "nom_estab",
    "Razon_social": "raz_social",
    "Clase_actividad": "nombre_act",
    "Estrato": "per_ocu",
    "Tipo_vialidad": "tipo_vial",
    "Calle": "nom_vial",
    "Num_Exterior": "numero_ext",
    "Num_Interior": "numero_int",
    "Colonia": "nomb_asent",
    "CP": "cod_postal",
    "Ubicacion": "municipio",
    "Telefono": "telefono",
    "Correo_e": "correoelec",
    "Sitio_internet": "www",
    "Tipo": "tipoUniEco",
    "Longitud": "longitud",
    "Latitud": "latitud",
    "tipo_corredor_industrial": "tipoCenCom",
    "nom_corredor_industrial": "nom_CenCom",
    "numero_local": "num_local",
}


class ErrorApiDenue(RuntimeError):
    """Error al consultar la API del DENUE tras agotar reintentos."""


@dataclass
class ConfiguracionDescargaDenue:
    """Parámetros de una corrida de descarga del DENUE.

    Attributes:
        terminos_busqueda: Términos de búsqueda de texto libre (ej. "AFORE").
        codigos_entidad: Códigos de entidad federativa ("01"-"32", con cero a la izquierda) a consultar.
            Se genera un archivo independiente por cada una.
        token: Token de la API DENUE.
        directorio_crudo: Carpeta donde se escribe, por entidad, el archivo
            completo tal cual lo entrega la API (sin deduplicar ni filtrar):
            el JSON y su equivalente aplanado en CSV.
        directorio_procesado: Carpeta donde se escribe, por entidad, el CSV
            deduplicado y filtrado por ``palabra_clave_subconjunto``.
        tamano_pagina: Tamaño de página por llamada (máx. documentado: 1000).
        segundos_espera: Pausa entre páginas para no saturar la API.
        palabra_clave_subconjunto: Si se provee, genera un CSV adicional
            filtrado por este texto (ej. "PROFUTURO") sobre la columna de
            nombre/razón social. None desactiva el subconjunto.
    """

    terminos_busqueda: list[str]
    token: str | None
    codigos_entidad: list[str] = field(default_factory=lambda: list(CODIGOS_ENTIDAD_DEFECTO))
    directorio_crudo: Path = Path("data/raw/denue")
    directorio_procesado: Path = Path("data/processed/denue")
    tamano_pagina: int = MAX_REGISTROS_POR_LLAMADA
    segundos_espera: float = 0.5
    palabra_clave_subconjunto: str | None = "PROFUTURO"


class SalidasEntidad(NamedTuple):
    """Rutas de los artefactos generados para una entidad federativa."""

    codigo_entidad: str
    ruta_json: Path
    ruta_csv: Path
    ruta_csv_subconjunto: Path | None


def cargar_configuracion_app(ruta: str = "config/config.yaml") -> dict:
    """Carga el archivo de configuración YAML del proyecto.

    Args:
        ruta: Ruta al archivo config.yaml.

    Returns:
        Diccionario con la configuración parseada.
    """
    with open(ruta, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.exceptions.RequestException, ErrorApiDenue)),
)
def _obtener_pagina(
    termino_busqueda: str, codigo_entidad: str, inicio: int, fin: int, token: str
) -> list[dict]:
    """Descarga una página de resultados vía el endpoint BuscarEntidad.

    Args:
        termino_busqueda: Texto a buscar en nombre/razón social o actividad.
        codigo_entidad: Código de entidad federativa ("01"-"32", con cero a la izquierda).
        inicio: Índice inicial del rango de registros (1-indexed).
        fin: Índice final del rango de registros.
        token: Token de la API DENUE.

    Returns:
        Lista de establecimientos (dicts) devueltos por la API.

    Raises:
        ErrorApiDenue: Si la API responde con un status distinto de 200
            o con un cuerpo que no es JSON válido.
    """
    url = f"{BASE_API_DENUE}/BuscarEntidad/{termino_busqueda}/{codigo_entidad}/{inicio}/{fin}/{token}"
    logger.info(
        "Consultando DENUE: termino=%s entidad=%s rango=%d-%d",
        termino_busqueda,
        codigo_entidad,
        inicio,
        fin,
    )
    respuesta = requests.get(url, timeout=SEGUNDOS_TIMEOUT_SOLICITUD)
    if respuesta.status_code != 200:
        raise ErrorApiDenue(
            f"DENUE API respondió HTTP {respuesta.status_code} "
            f"(termino={termino_busqueda}, entidad={codigo_entidad})"
        )
    try:
        return respuesta.json()
    except json.JSONDecodeError as exc:
        raise ErrorApiDenue(
            f"Respuesta no es JSON válido para entidad {codigo_entidad}: {respuesta.text[:200]}"
        ) from exc


def obtener_registros_entidad(
    termino_busqueda: str,
    codigo_entidad: str,
    token: str,
    tamano_pagina: int = MAX_REGISTROS_POR_LLAMADA,
    segundos_espera: float = 0.5,
) -> list[dict]:
    """Pagina resultados de una entidad hasta agotar registros disponibles.

    Args:
        termino_busqueda: Texto a buscar.
        codigo_entidad: Código de entidad federativa.
        token: Token de la API DENUE.
        tamano_pagina: Tamaño de página por llamada.
        segundos_espera: Pausa entre llamadas consecutivas.

    Returns:
        Lista acumulada de establecimientos para la entidad.
    """
    registros: list[dict] = []
    inicio = 1
    while True:
        fin = inicio + tamano_pagina - 1
        pagina = _obtener_pagina(termino_busqueda, codigo_entidad, inicio, fin, token)
        if not pagina:
            break
        registros.extend(pagina)
        if len(pagina) < tamano_pagina:
            break
        inicio = fin + 1
        time.sleep(segundos_espera)
    return registros


def _eliminar_duplicados(registros: list[dict]) -> list[dict]:
    """Elimina duplicados cuando varios términos de búsqueda matchean el mismo registro."""
    vistos: set[str] = set()
    registros_unicos: list[dict] = []
    for registro in registros:
        clave = str(registro.get("Id") or registro.get("id") or json.dumps(registro, sort_keys=True))
        if clave not in vistos:
            vistos.add(clave)
            registros_unicos.append(registro)
    return registros_unicos


def _columnas_nombre_presentes(df: pd.DataFrame) -> list[str]:
    """Devuelve todas las columnas candidatas a nombre/razón social presentes en df."""
    return [candidata for candidata in COLUMNAS_NOMBRE_CANDIDATAS if candidata in df.columns]


def construir_dataframe(registros: list[dict]) -> pd.DataFrame:
    """Aplana los registros crudos del DENUE (JSON) en un DataFrame tabular.

    Args:
        registros: Registros devueltos por la API.

    Returns:
        DataFrame con una fila por establecimiento.
    """
    return pd.json_normalize(registros)


def escribir_csv_completo(
    df: pd.DataFrame,
    directorio_crudo: Path,
    identificador: str,
    marca_tiempo: str,
) -> Path:
    """Escribe el CSV con todos los registros de una entidad (sin filtrar) en raw.

    Es el mismo contenido que el JSON crudo, solo aplanado a tabla — no hay
    transformación de datos, por eso vive junto al JSON en ``directorio_crudo``.

    Args:
        df: DataFrame con los establecimientos descargados de una entidad.
        directorio_crudo: Carpeta destino (la misma del JSON crudo).
        identificador: Slug para el nombre de archivo (términos + entidad).
        marca_tiempo: Timestamp de la corrida, usado en el nombre de archivo.

    Returns:
        Ruta del CSV completo escrito.
    """
    ruta_csv = directorio_crudo / f"denue_{identificador}_{marca_tiempo}.csv"
    df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
    logger.info("CSV completo escrito: %d filas -> %s", len(df), ruta_csv)
    return ruta_csv


def filtrar_por_palabra_clave(
    df: pd.DataFrame, palabra_clave_subconjunto: str | None, codigo_entidad: str
) -> pd.DataFrame | None:
    """Filtra registros de una entidad por palabra clave en nombre/razón social.

    Args:
        df: DataFrame con los establecimientos de una entidad (ya deduplicado).
        palabra_clave_subconjunto: Texto a buscar en las columnas de nombre
            comercial/razón social (ej. "PROFUTURO"). None desactiva el
            subconjunto.
        codigo_entidad: Código de entidad federativa, usado solo en logs.

    Returns:
        DataFrame filtrado, o None si el filtro está desactivado o no hay
        columna de nombre/razón social disponible.
    """
    if not palabra_clave_subconjunto:
        return None

    columnas_nombre = _columnas_nombre_presentes(df)
    if not columnas_nombre:
        logger.warning(
            "No se encontró columna de nombre/razón social (candidatas: %s); "
            "no se generó el subconjunto filtrado por '%s' (entidad=%s)",
            COLUMNAS_NOMBRE_CANDIDATAS,
            palabra_clave_subconjunto,
            codigo_entidad,
        )
        return None

    # Se busca en TODAS las columnas de nombre/razón social presentes (no
    # solo la primera), para no perder coincidencias que solo aparecen en
    # una de ellas (ej. razón social pero no nombre comercial).
    texto_busqueda = df[columnas_nombre].astype(str).agg(" ".join, axis=1)
    return df[texto_busqueda.str.contains(palabra_clave_subconjunto, case=False, na=False)]


def escribir_csv_subconjunto(
    df_subconjunto: pd.DataFrame,
    directorio_procesado: Path,
    codigo_entidad: str,
    marca_tiempo: str,
    palabra_clave_subconjunto: str,
) -> Path:
    """Escribe el CSV de una entidad ya filtrado por palabra clave (processed).

    Args:
        df_subconjunto: DataFrame ya filtrado por ``palabra_clave_subconjunto``.
        directorio_procesado: Carpeta destino del CSV filtrado.
        codigo_entidad: Código de entidad federativa, usado en el nombre de archivo.
        marca_tiempo: Timestamp de la corrida, usado en el nombre de archivo.
        palabra_clave_subconjunto: Texto usado para filtrar (ej. "PROFUTURO").

    Returns:
        Ruta del CSV filtrado escrito.
    """
    identificador_subconjunto = palabra_clave_subconjunto.lower().replace(" ", "_")
    ruta_csv_subconjunto = (
        directorio_procesado / f"denue_{identificador_subconjunto}_{codigo_entidad}_{marca_tiempo}.csv"
    )
    df_subconjunto.to_csv(ruta_csv_subconjunto, index=False, encoding="utf-8-sig")
    logger.info(
        "CSV filtrado por '%s' (entidad=%s): %d filas -> %s",
        palabra_clave_subconjunto,
        codigo_entidad,
        len(df_subconjunto),
        ruta_csv_subconjunto,
    )
    if df_subconjunto.empty:
        logger.warning(
            "El filtro '%s' no encontró coincidencias (entidad=%s)",
            palabra_clave_subconjunto,
            codigo_entidad,
        )
    return ruta_csv_subconjunto


def escribir_csv_subconjunto_nacional(
    subconjuntos_por_entidad: list[pd.DataFrame],
    directorio_procesado: Path,
    marca_tiempo: str,
    palabra_clave_subconjunto: str,
) -> Path | None:
    """Acumula los subconjuntos de todas las entidades en un único CSV nacional.

    Args:
        subconjuntos_por_entidad: Subconjuntos filtrados, uno por entidad con
            al menos una coincidencia.
        directorio_procesado: Carpeta destino del CSV acumulado.
        marca_tiempo: Timestamp de la corrida, usado en el nombre de archivo.
        palabra_clave_subconjunto: Texto usado para filtrar (ej. "PROFUTURO").

    Returns:
        Ruta del CSV acumulado, o None si ninguna entidad tuvo coincidencias.
    """
    if not subconjuntos_por_entidad:
        logger.warning(
            "No se generó CSV nacional acumulado: ninguna entidad tuvo coincidencias para '%s'",
            palabra_clave_subconjunto,
        )
        return None

    df_nacional = pd.concat(subconjuntos_por_entidad, ignore_index=True)
    identificador_subconjunto = palabra_clave_subconjunto.lower().replace(" ", "_")
    ruta_csv_nacional = directorio_procesado / f"denue_{identificador_subconjunto}_nacional_{marca_tiempo}.csv"
    df_nacional.to_csv(ruta_csv_nacional, index=False, encoding="utf-8-sig")
    logger.info(
        "CSV nacional acumulado por '%s': %d filas (de %d entidades) -> %s",
        palabra_clave_subconjunto,
        len(df_nacional),
        len(subconjuntos_por_entidad),
        ruta_csv_nacional,
    )
    return ruta_csv_nacional


def limpiar_municipio_desde_ubicacion(serie_ubicacion: pd.Series) -> pd.Series:
    """Extrae el nombre de municipio limpio del campo ``Ubicacion`` de la API.

    La API devuelve ``Ubicacion`` como texto combinado con el formato
    ``"<localidad>, <municipio>, <entidad>"`` (con saltos de línea/espacios
    de relleno alrededor de la localidad). Se toma solo la parte de en medio.

    Args:
        serie_ubicacion: Columna ``Ubicacion`` tal como la entrega la API.

    Returns:
        Serie con el nombre de municipio, o el valor original si no tiene
        el formato de 3 partes separadas por coma.
    """
    partes = serie_ubicacion.astype(str).str.split(",")
    return partes.apply(lambda p: p[1].strip() if len(p) == 3 else "\n".join(p).strip())


def copiar_csv_a_ruta_legado(ruta_csv_origen: Path, directorio_procesado: Path) -> Path:
    """Copia un CSV (entidad 09) a la ruta legado, con encabezados del formato oficial INEGI.

    Mantiene compatibilidad con scripts que leen la estructura de la descarga
    masiva del portal INEGI (``denue_09_csv/conjunto_de_datos/denue_inegi_09_.csv``),
    renombrando las columnas de la API DENUE (PascalCase) a los nombres del
    diccionario oficial de datos (snake_case, ej. ``nom_estab``, ``latitud``)
    y limpiando ``municipio`` (la API solo da el texto combinado ``Ubicacion``).

    Args:
        ruta_csv_origen: Ruta del CSV de la entidad 09 ya escrito (esquema API).
        directorio_procesado: Carpeta base de processed (ej. ``data/processed/denue``).

    Returns:
        Ruta de la copia generada.
    """
    ruta_legado = directorio_procesado / "denue_09_csv" / "conjunto_de_datos" / "denue_inegi_09_.csv"
    ruta_legado.parent.mkdir(parents=True, exist_ok=True)
    df_legado = pd.read_csv(ruta_csv_origen).rename(columns=MAPEO_COLUMNAS_API_A_INEGI)
    if "municipio" in df_legado.columns:
        df_legado["municipio"] = limpiar_municipio_desde_ubicacion(df_legado["municipio"])
    df_legado.to_csv(ruta_legado, index=False, encoding="utf-8-sig")
    logger.info("CSV de la entidad 09 con encabezados INEGI en ruta legado -> %s", ruta_legado)
    return ruta_legado


def descargar_entidad(
    codigo_entidad: str, configuracion: ConfiguracionDescargaDenue, marca_tiempo: str
) -> tuple[SalidasEntidad | None, list[str], pd.DataFrame | None]:
    """Descarga y escribe los archivos (raw + processed) de una sola entidad.

    Args:
        codigo_entidad: Código de entidad federativa a consultar.
        configuracion: Configuración de la descarga.
        marca_tiempo: Timestamp compartido por toda la corrida.

    Returns:
        Tupla (salidas de la entidad o None si no hubo registros, términos
        de búsqueda que fallaron para esta entidad, subconjunto filtrado por
        palabra clave o None si no aplica/no hubo coincidencias).
    """
    registros_entidad: list[dict] = []
    terminos_fallidos: list[str] = []

    for termino_busqueda in configuracion.terminos_busqueda:
        try:
            registros = obtener_registros_entidad(
                termino_busqueda,
                codigo_entidad,
                configuracion.token,
                configuracion.tamano_pagina,
                configuracion.segundos_espera,
            )
            logger.info(
                "termino=%s entidad=%s -> %d registros", termino_busqueda, codigo_entidad, len(registros)
            )
            registros_entidad.extend(registros)
        except ErrorApiDenue as exc:
            logger.error(
                "Fallo definitivo termino=%s entidad=%s: %s", termino_busqueda, codigo_entidad, exc
            )
            terminos_fallidos.append(termino_busqueda)

    if not registros_entidad:
        logger.warning("Sin registros para entidad=%s; no se generan archivos", codigo_entidad)
        return None, terminos_fallidos, None

    identificador_terminos = "-".join(t.lower() for t in configuracion.terminos_busqueda)
    identificador = f"{identificador_terminos}_{codigo_entidad}"

    # Capa raw: exactamente lo que devolvió la API para esta entidad, sin
    # deduplicar ni filtrar.
    ruta_json = configuracion.directorio_crudo / f"denue_{identificador}_{marca_tiempo}.json"
    with open(ruta_json, "w", encoding="utf-8") as fh:
        json.dump(registros_entidad, fh, ensure_ascii=False, indent=2)

    df_crudo = construir_dataframe(registros_entidad)
    ruta_csv = escribir_csv_completo(df_crudo, configuracion.directorio_crudo, identificador, marca_tiempo)

    # Capa processed: deduplicado + filtro por marca, únicas transformaciones.
    registros_unicos = _eliminar_duplicados(registros_entidad)
    df_procesado = construir_dataframe(registros_unicos)
    df_subconjunto = filtrar_por_palabra_clave(
        df_procesado, configuracion.palabra_clave_subconjunto, codigo_entidad
    )
    ruta_csv_subconjunto = None
    if df_subconjunto is not None and configuracion.palabra_clave_subconjunto:
        ruta_csv_subconjunto = escribir_csv_subconjunto(
            df_subconjunto,
            configuracion.directorio_procesado,
            codigo_entidad,
            marca_tiempo,
            configuracion.palabra_clave_subconjunto,
        )

    return (
        SalidasEntidad(
            codigo_entidad=codigo_entidad,
            ruta_json=ruta_json,
            ruta_csv=ruta_csv,
            ruta_csv_subconjunto=ruta_csv_subconjunto,
        ),
        terminos_fallidos,
        df_subconjunto,
    )


def descargar_denue(configuracion: ConfiguracionDescargaDenue) -> list[SalidasEntidad]:
    """Descarga ``terminos_busqueda`` para cada entidad de ``codigos_entidad``.

    Genera un archivo independiente por entidad federativa. Por cada entidad
    con al menos un registro, escribe en ``configuracion.directorio_crudo``
    el JSON y CSV completos (sin deduplicar ni filtrar), y en
    ``configuracion.directorio_procesado`` el CSV deduplicado y, si
    ``configuracion.palabra_clave_subconjunto`` está definido, filtrado por
    ese texto. Adicionalmente, si el filtro está activo, acumula los
    subconjuntos de todas las entidades en un único CSV nacional en
    ``configuracion.directorio_procesado``.

    Args:
        configuracion: Configuración de la descarga.

    Returns:
        Lista de salidas, una por cada entidad que produjo al menos un registro.

    Raises:
        ValueError: Si no se provee un token de la API.
        ErrorApiDenue: Si ninguna entidad produjo registros.
    """
    if not configuracion.token:
        raise ValueError(
            "Falta TOKEN_API_DENUE. Regístrate gratis en "
            "https://www.inegi.org.mx/servicios/api_denue.html y colócalo en .env"
        )

    configuracion.directorio_crudo.mkdir(parents=True, exist_ok=True)
    configuracion.directorio_procesado.mkdir(parents=True, exist_ok=True)

    marca_tiempo = time.strftime("%Y%m%d_%H%M%S")
    salidas: list[SalidasEntidad] = []
    llamadas_fallidas: list[tuple[str, str]] = []
    subconjuntos_por_entidad: list[pd.DataFrame] = []

    for codigo_entidad in configuracion.codigos_entidad:
        salida_entidad, terminos_fallidos, df_subconjunto = descargar_entidad(
            codigo_entidad, configuracion, marca_tiempo
        )
        llamadas_fallidas.extend((termino, codigo_entidad) for termino in terminos_fallidos)
        if salida_entidad is not None:
            salidas.append(salida_entidad)
        if df_subconjunto is not None and not df_subconjunto.empty:
            subconjuntos_por_entidad.append(df_subconjunto)

    if not salidas:
        raise ErrorApiDenue(
            "La descarga no produjo ningún registro en ninguna entidad; revisa "
            "terminos_busqueda, codigos_entidad y el token en .env"
        )

    if configuracion.palabra_clave_subconjunto:
        escribir_csv_subconjunto_nacional(
            subconjuntos_por_entidad,
            configuracion.directorio_procesado,
            marca_tiempo,
            configuracion.palabra_clave_subconjunto,
        )
        # Ruta legado (formato descarga masiva INEGI): solo entidad 09, no el
        # acumulado nacional.
        salida_entidad_09 = next((s for s in salidas if s.codigo_entidad == "09"), None)
        if salida_entidad_09 is not None and salida_entidad_09.ruta_csv_subconjunto is not None:
            copiar_csv_a_ruta_legado(salida_entidad_09.ruta_csv_subconjunto, configuracion.directorio_procesado)
        else:
            logger.warning(
                "No se generó denue_inegi_09_.csv: la entidad '09' no tiene subconjunto "
                "(revisa codigos_entidad en config.yaml)"
            )

    # Cifras control (DQ) - regla obligatoria de CLAUDE.md
    total_llamadas = len(configuracion.terminos_busqueda) * len(configuracion.codigos_entidad)
    logger.info(
        "Descarga completada: %d/%d entidades con archivos generados, %d/%d llamadas OK",
        len(salidas),
        len(configuracion.codigos_entidad),
        total_llamadas - len(llamadas_fallidas),
        total_llamadas,
    )
    if llamadas_fallidas:
        logger.warning("Llamadas fallidas (termino, entidad): %s", llamadas_fallidas)

    return salidas


def construir_analizador_argumentos() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos de línea de comandos."""
    analizador = argparse.ArgumentParser(
        description="Descarga sucursales de AFOREs desde la API DENUE (INEGI), un archivo por entidad."
    )
    analizador.add_argument(
        "--termino-busqueda",
        action="append",
        dest="terminos_busqueda",
        default=None,
        help="Término de búsqueda (repetible). Sobrescribe config.yaml.",
    )
    analizador.add_argument(
        "--entidades",
        nargs="*",
        default=None,
        help="Códigos de entidad federativa 01-32 (con cero a la izquierda). Por defecto: todas.",
    )
    analizador.add_argument(
        "--config",
        default="config/config.yaml",
        help="Ruta al config.yaml del proyecto.",
    )
    analizador.add_argument(
        "--directorio-crudo",
        default=None,
        help="Directorio para el archivo completo (JSON + CSV) por entidad. Por defecto data/raw/denue.",
    )
    analizador.add_argument(
        "--directorio-procesado",
        default=None,
        help="Directorio para el CSV filtrado por marca, por entidad. Por defecto data/processed/denue.",
    )
    analizador.add_argument(
        "--palabra-clave-subconjunto",
        default=None,
        help="Texto para filtrar un CSV adicional (ej. PROFUTURO). "
        "Usa '' (vacío) para desactivarlo. Sobrescribe config.yaml.",
    )
    return analizador


def principal() -> None:
    """Punto de entrada CLI: descarga el DENUE y guarda un archivo por entidad."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    load_dotenv()

    argumentos = construir_analizador_argumentos().parse_args()
    configuracion_app = cargar_configuracion_app(argumentos.config)
    configuracion_denue = configuracion_app.get("denue", {})

    terminos_busqueda = argumentos.terminos_busqueda or configuracion_denue.get(
        "terminos_busqueda", ["AFORE"]
    )
    codigos_entidad = (
        argumentos.entidades
        or configuracion_denue.get("codigos_entidad")
        or CODIGOS_ENTIDAD_DEFECTO
    )
    directorio_crudo = Path(
        argumentos.directorio_crudo or configuracion_denue.get("directorio_crudo", "data/raw/denue")
    )
    directorio_procesado = Path(
        argumentos.directorio_procesado
        or configuracion_denue.get("directorio_procesado", "data/processed/denue")
    )
    tamano_pagina = int(configuracion_denue.get("tamano_pagina", MAX_REGISTROS_POR_LLAMADA))
    palabra_clave_subconjunto = (
        argumentos.palabra_clave_subconjunto
        if argumentos.palabra_clave_subconjunto is not None
        else configuracion_denue.get("palabra_clave_subconjunto", "PROFUTURO")
    )
    token = os.environ.get("TOKEN_API_DENUE")

    configuracion = ConfiguracionDescargaDenue(
        terminos_busqueda=terminos_busqueda,
        codigos_entidad=codigos_entidad,
        directorio_crudo=directorio_crudo,
        directorio_procesado=directorio_procesado,
        tamano_pagina=tamano_pagina,
        token=token,
        palabra_clave_subconjunto=palabra_clave_subconjunto or None,
    )

    try:
        salidas = descargar_denue(configuracion)
    except (ValueError, ErrorApiDenue) as exc:
        logger.error("Descarga de DENUE fallida: %s", exc)
        raise SystemExit(1) from exc

    for salida in salidas:
        logger.info(
            "Entidad %s -> json=%s csv=%s subconjunto=%s",
            salida.codigo_entidad,
            salida.ruta_json,
            salida.ruta_csv,
            salida.ruta_csv_subconjunto,
        )


if __name__ == "__main__":
    principal()
