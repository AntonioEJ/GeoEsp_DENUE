"""Pruebas unitarias para src/visualizacion/mapas_estaticos.py."""

from pathlib import Path

import geopandas as gpd

from src.visualizacion.mapas_estaticos import graficar_mapa_puntos


def test_graficar_mapa_puntos_guarda_archivo_si_se_da_ruta_salida(tmp_path: Path):
    gdf = gpd.GeoDataFrame(
        {"Nombre": ["A", "B"]},
        geometry=gpd.points_from_xy([-99.13, -103.42], [19.43, 25.40]),
        crs="EPSG:4326",
    )
    ruta_salida = tmp_path / "figuras" / "resumen.png"

    graficar_mapa_puntos(gdf, ruta_salida=ruta_salida, titulo="Sucursales AFORE")

    assert ruta_salida.exists()
