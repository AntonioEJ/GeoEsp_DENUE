"""Pruebas unitarias para src/caracteristicas/construir_caracteristicas.py."""

import pandas as pd

from src.caracteristicas.construir_caracteristicas import agregar_geometria


def test_agregar_geometria_construye_puntos_con_crs_wgs84():
    df = pd.DataFrame({"Longitud": [-99.13, -103.42], "Latitud": [19.43, 25.40]})

    gdf = agregar_geometria(df)

    assert gdf.crs.to_string() == "EPSG:4326"
    assert gdf.geometry.iloc[0].x == -99.13
    assert gdf.geometry.iloc[0].y == 19.43
