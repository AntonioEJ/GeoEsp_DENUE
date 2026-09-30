"""Construcción de variables derivadas para el análisis geoespacial."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd


def agregar_geometria(
    df: pd.DataFrame,
    columna_lon: str = "Longitud",
    columna_lat: str = "Latitud",
    crs: str = "EPSG:4326",
) -> gpd.GeoDataFrame:
    """Convierte un DataFrame con columnas de lon/lat en un GeoDataFrame.

    Args:
        df: DataFrame con columnas de longitud/latitud (ej. campos
            ``Longitud``/``Latitud`` de la API DENUE).
        columna_lon: Nombre de la columna de longitud.
        columna_lat: Nombre de la columna de latitud.
        crs: CRS de las coordenadas de entrada (por defecto WGS84).

    Returns:
        GeoDataFrame con geometría de puntos en el CRS indicado.
    """
    geometria = gpd.points_from_xy(df[columna_lon], df[columna_lat])
    return gpd.GeoDataFrame(df, geometry=geometria, crs=crs)
