"""Limpieza y clasificación del DENUE (filtrado y normalización de AFOREs).

Lee los CSV crudos de ``data/raw/denue/`` (uno por entidad federativa, tal
cual los entrega la API, sin transformar) y escribe en
``data/processed/denue/`` la versión ya corregida de cada uno: coordenadas
válidas + clasificación por marca de AFORE, municipio y estado. Si hay más
de una entidad, también genera un CSV combinado con todas ellas (la vista
nacional).

Uso:
    uv run src/preprocesamiento/limpiar_denue.py
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

LIMITES_MEXICO = {"lat_min": 14.0, "lat_max": 33.0, "lon_min": -119.0, "lon_max": -86.0}

# Palabras clave para clasificar por marca comercial de AFORE. El endpoint
# BuscarEntidad del DENUE hace match de texto libre, así que el DataFrame
# crudo incluye ruido (asesorías, trámites, nombres genéricos) que no
# corresponde a una sucursal real de AFORE; ese ruido cae en "OTRO / SIN
# CLASIFICAR". Ver docs/denue_ingestion.md.
PALABRAS_CLAVE_MARCA_AFORE: dict[str, list[str]] = {
    "XXI BANORTE": ["XXI", "BANORTE"],
    "SURA": ["SURA"],
    "INVERCAP": ["INVERCAP"],
    "CITIBANAMEX": ["BANAMEX", "CITIBANAMEX"],
    "COPPEL": ["COPPEL", "C0PPEL"],
    "PRINCIPAL": ["PRINCIPAL"],
    "PROFUTURO": ["PROFUTURO"],
    "INBURSA": ["INBURSA"],
    "AZTECA": ["AZTECA"],
    "PENSIONISSSTE": ["PENSIONISSSTE", "PENSION ISSSTE"],
}
ETIQUETA_SIN_CLASIFICAR = "OTRO / SIN CLASIFICAR"


def filtrar_coordenadas_validas(
    df: pd.DataFrame,
    columna_lon: str = "Longitud",
    columna_lat: str = "Latitud",
) -> pd.DataFrame:
    """Descarta filas con coordenadas nulas, cero o fuera del territorio mexicano.

    Args:
        df: DataFrame con columnas de longitud/latitud.
        columna_lon: Nombre de la columna de longitud.
        columna_lat: Nombre de la columna de latitud.

    Returns:
        Subconjunto de ``df`` con coordenadas válidas dentro de ``LIMITES_MEXICO``.
    """
    lat = df[columna_lat]
    lon = df[columna_lon]
    mascara_valida = (
        lat.notna()
        & lon.notna()
        & (lat != 0)
        & (lon != 0)
        & lat.between(LIMITES_MEXICO["lat_min"], LIMITES_MEXICO["lat_max"])
        & lon.between(LIMITES_MEXICO["lon_min"], LIMITES_MEXICO["lon_max"])
    )
    n_descartados = int((~mascara_valida).sum())
    if n_descartados:
        logger.warning(
            "Coordenadas inválidas o fuera de México descartadas: %d de %d filas",
            n_descartados,
            len(df),
        )
    return df[mascara_valida].copy()


def extraer_municipio_estado(ubicacion: str) -> tuple[str, str]:
    """Extrae (municipio, estado) del campo ``Ubicacion`` de la API DENUE.

    El campo llega como texto libre con formato aproximado
    ``"<colonia/localidad>, <Municipio>, <ESTADO>"``.

    Args:
        ubicacion: Valor crudo del campo ``Ubicacion``.

    Returns:
        Tupla ``(municipio, estado)``; cadenas vacías si no se pueden inferir.
    """
    partes = [p.strip() for p in str(ubicacion).split(",") if p.strip()]
    estado = partes[-1] if partes else ""
    municipio = partes[-2] if len(partes) >= 2 else ""
    return municipio, estado


def clasificar_marca_afore(nombre: str, razon_social: str) -> str:
    """Clasifica un establecimiento por marca comercial de AFORE.

    Args:
        nombre: Valor del campo ``Nombre``.
        razon_social: Valor del campo ``Razon_social``.

    Returns:
        Nombre de la marca de AFORE detectada, o ``ETIQUETA_SIN_CLASIFICAR``
        si el texto no matchea ninguna palabra clave conocida.
    """
    texto = f"{nombre or ''} {razon_social or ''}".upper()
    for marca, palabras_clave in PALABRAS_CLAVE_MARCA_AFORE.items():
        if any(palabra_clave in texto for palabra_clave in palabras_clave):
            return marca
    return ETIQUETA_SIN_CLASIFICAR


def _obtener_primera_columna(df: pd.DataFrame, *candidatas: str) -> pd.Series:
    """Devuelve la primera columna de ``candidatas`` presente en ``df``.

    Permite soportar tanto los nombres de columna de la API DENUE
    (``Nombre``, ``Razon_social``) como los del diccionario oficial de datos
    usados por la descarga masiva del portal (``nom_estab``, ``raz_social``).

    Args:
        df: DataFrame a inspeccionar.
        *candidatas: Nombres de columna a probar, en orden de preferencia.

    Returns:
        La columna encontrada, o una serie vacía (misma longitud que ``df``)
        si ninguna candidata está presente.
    """
    for candidata in candidatas:
        if candidata in df.columns:
            return df[candidata]
    return pd.Series([""] * len(df), index=df.index, dtype=str)


def filtrar_afores(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas derivadas de limpieza: marca de AFORE, municipio y estado.

    Clasifica por marca de AFORE buscando en nombre comercial
    (``Nombre``/``nom_estab``) y razón social (``Razon_social``/``raz_social``),
    soportando tanto la API DENUE como la descarga masiva del portal.

    Args:
        df: DataFrame crudo del DENUE (salida de ``descargar_denue``).

    Returns:
        Copia de ``df`` con las columnas ``afore_marca``, ``municipio`` y
        ``estado`` agregadas.
    """
    resultado = df.copy()
    nombres = _obtener_primera_columna(resultado, "Nombre", "nombre", "nom_estab")
    razones_sociales = _obtener_primera_columna(
        resultado, "Razon_social", "razon_social", "raz_social"
    )
    resultado["afore_marca"] = [
        clasificar_marca_afore(nombre, razon_social)
        for nombre, razon_social in zip(nombres, razones_sociales)
    ]
    ubicaciones = resultado.get("Ubicacion", pd.Series(dtype=str)).map(extraer_municipio_estado)
    resultado["municipio"] = ubicaciones.map(lambda t: t[0])
    resultado["estado"] = ubicaciones.map(lambda t: t[1])
    return resultado


def limpiar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica todas las correcciones de calidad sobre el DataFrame crudo.

    Args:
        df: DataFrame crudo del DENUE (sin transformar).

    Returns:
        DataFrame con coordenadas válidas y columnas ``afore_marca``,
        ``municipio``, ``estado`` agregadas.
    """
    df_valido = filtrar_coordenadas_validas(df)
    return filtrar_afores(df_valido)


def _extraer_marca_tiempo(nombre_archivo: str) -> str | None:
    """Extrae el sufijo de timestamp (``YYYYMMDD_HHMMSS``) de un nombre de archivo."""
    coincidencia = re.search(r"(\d{8}_\d{6})$", nombre_archivo)
    return coincidencia.group(1) if coincidencia else None


def _extraer_codigo_entidad(nombre_archivo: str, marca_tiempo: str) -> str | None:
    """Extrae el código de entidad de un nombre ``denue_afore_<entidad>_<marca_tiempo>``."""
    prefijo = "denue_afore_"
    sufijo = f"_{marca_tiempo}"
    if not (nombre_archivo.startswith(prefijo) and nombre_archivo.endswith(sufijo)):
        return None
    codigo = nombre_archivo[len(prefijo) : -len(sufijo)]
    return codigo or None


def _listar_marcas_tiempo(directorio_crudo: Path) -> list[str]:
    """Lista, ordenadas, las marcas de tiempo únicas presentes en los CSV crudos."""
    marcas = {
        marca
        for ruta in directorio_crudo.glob("denue_afore_*.csv")
        if (marca := _extraer_marca_tiempo(ruta.stem)) is not None
    }
    return sorted(marcas)


def encontrar_csvs_crudos_recientes(directorio_crudo: Path) -> list[Path]:
    """Busca los CSV crudos de la corrida (misma marca de tiempo) más reciente.

    Como `descargar_denue` genera un CSV por entidad federativa, esto
    devuelve un archivo por cada entidad descargada en la última corrida.

    Args:
        directorio_crudo: Carpeta donde `descargar_denue` escribe los CSV crudos.

    Returns:
        Rutas de los CSV de la corrida más reciente, ordenadas.

    Raises:
        FileNotFoundError: Si no hay ningún CSV crudo en la carpeta.
    """
    candidatos = sorted(directorio_crudo.glob("denue_afore_*.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"No se encontró ningún CSV en {directorio_crudo}. Corre primero: make download-denue"
        )
    marca_reciente = _listar_marcas_tiempo(directorio_crudo)[-1]
    return [c for c in candidatos if c.stem.endswith(marca_reciente)]


def encontrar_csv_nacional_reciente(
    directorio_procesado: Path, palabra_clave_subconjunto: str = "AFORE"
) -> Path:
    """Busca el CSV nacional acumulado (todas las entidades) más reciente.

    ``descargar_denue`` ya escribe, en cada corrida, un único CSV con todas
    las entidades combinadas (``denue_<palabra_clave>_nacional_<timestamp>.csv``)
    en ``directorio_procesado``; a diferencia de ``encontrar_csvs_crudos_recientes``,
    no hace falta concatenar un archivo por entidad.

    Args:
        directorio_procesado: Carpeta donde `descargar_denue` escribe el CSV nacional.
        palabra_clave_subconjunto: Palabra clave usada al descargar (ej. "AFORE").

    Returns:
        Ruta del CSV nacional más reciente.

    Raises:
        FileNotFoundError: Si no hay ningún CSV nacional en la carpeta.
    """
    identificador = palabra_clave_subconjunto.lower().replace(" ", "_")
    candidatos = sorted(directorio_procesado.glob(f"denue_{identificador}_nacional_*.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"No se encontró ningún CSV nacional en {directorio_procesado}. Corre primero: make download-denue"
        )
    return candidatos[-1]


def limpiar_denue(
    directorio_crudo: Path,
    directorio_procesado: Path,
    ruta_csv_crudo: Path | None = None,
) -> list[Path]:
    """Limpia los CSV crudos (los de la corrida más reciente, o uno específico).

    Cada archivo de entrada se lee de ``directorio_crudo`` sin modificarlo; el
    resultado corregido (coordenadas válidas + marca/municipio/estado) se
    escribe como un CSV nuevo por entidad en ``directorio_procesado``. Cuando
    se procesa más de una entidad, además se escribe un CSV combinado con
    todas ellas (``denue_afore_limpio_<marca_tiempo>.csv``, sin sufijo de
    entidad) — la vista nacional lista para análisis.

    Args:
        directorio_crudo: Carpeta con los CSV crudos (salida de `descargar_denue`).
        directorio_procesado: Carpeta destino de los CSV ya limpios.
        ruta_csv_crudo: Si se provee, limpia únicamente este archivo en vez
            de los de la corrida más reciente en ``directorio_crudo``.

    Returns:
        Rutas de los CSV limpios generados: uno por archivo de entrada, y
        (si hubo más de una entidad) el CSV combinado al final.
    """
    directorio_procesado.mkdir(parents=True, exist_ok=True)
    rutas_entrada = [ruta_csv_crudo] if ruta_csv_crudo else encontrar_csvs_crudos_recientes(directorio_crudo)

    rutas_salida: list[Path] = []
    dfs_limpios: list[pd.DataFrame] = []
    marca_tiempo_corrida: str | None = None

    for ruta_entrada in rutas_entrada:
        df_crudo = pd.read_csv(ruta_entrada)
        n_crudo = len(df_crudo)

        df_limpio = limpiar_dataframe(df_crudo)
        dfs_limpios.append(df_limpio)

        marca_tiempo = _extraer_marca_tiempo(ruta_entrada.stem) or time.strftime("%Y%m%d_%H%M%S")
        marca_tiempo_corrida = marca_tiempo_corrida or marca_tiempo
        codigo_entidad = _extraer_codigo_entidad(ruta_entrada.stem, marca_tiempo)
        sufijo_entidad = f"_{codigo_entidad}" if codigo_entidad else ""
        ruta_salida = directorio_procesado / f"denue_afore_limpio{sufijo_entidad}_{marca_tiempo}.csv"
        df_limpio.to_csv(ruta_salida, index=False, encoding="utf-8-sig")

        # Cifras control (DQ) - regla obligatoria de CLAUDE.md
        logger.info(
            "Limpieza completada (entidad=%s): %d registros crudos, %d válidos (%d descartados), "
            "%d marcas de AFORE detectadas -> %s",
            codigo_entidad or "?",
            n_crudo,
            len(df_limpio),
            n_crudo - len(df_limpio),
            df_limpio["afore_marca"].nunique() if not df_limpio.empty else 0,
            ruta_salida,
        )
        rutas_salida.append(ruta_salida)

    if len(dfs_limpios) > 1:
        df_combinado = pd.concat(dfs_limpios, ignore_index=True)
        ruta_combinada = directorio_procesado / f"denue_afore_limpio_{marca_tiempo_corrida}.csv"
        df_combinado.to_csv(ruta_combinada, index=False, encoding="utf-8-sig")
        logger.info(
            "CSV combinado (%d entidades): %d filas, %d marcas de AFORE detectadas -> %s",
            len(dfs_limpios),
            len(df_combinado),
            df_combinado["afore_marca"].nunique() if not df_combinado.empty else 0,
            ruta_combinada,
        )
        rutas_salida.append(ruta_combinada)

    return rutas_salida


def construir_analizador_argumentos() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos de línea de comandos."""
    analizador = argparse.ArgumentParser(
        description="Limpia los CSV crudos del DENUE (uno por entidad): coordenadas válidas "
        "y clasificación por marca."
    )
    analizador.add_argument(
        "--directorio-crudo",
        default="data/raw/denue",
        help="Carpeta con los CSV crudos. Por defecto data/raw/denue.",
    )
    analizador.add_argument(
        "--directorio-procesado",
        default="data/processed/denue",
        help="Carpeta destino de los CSV limpios. Por defecto data/processed/denue.",
    )
    analizador.add_argument(
        "--csv-entrada",
        default=None,
        help="Ruta a un CSV crudo específico. Por defecto, los de la corrida más reciente "
        "en --directorio-crudo (uno por entidad).",
    )
    return analizador


def principal() -> None:
    """Punto de entrada CLI: limpia los CSV crudos más recientes y guarda el resultado."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    argumentos = construir_analizador_argumentos().parse_args()
    ruta_csv_crudo = Path(argumentos.csv_entrada) if argumentos.csv_entrada else None

    try:
        rutas_salida = limpiar_denue(
            directorio_crudo=Path(argumentos.directorio_crudo),
            directorio_procesado=Path(argumentos.directorio_procesado),
            ruta_csv_crudo=ruta_csv_crudo,
        )
    except FileNotFoundError as exc:
        logger.error("Limpieza del DENUE fallida: %s", exc)
        raise SystemExit(1) from exc

    for ruta_salida in rutas_salida:
        logger.info("Archivo generado: %s", ruta_salida)


if __name__ == "__main__":
    principal()
