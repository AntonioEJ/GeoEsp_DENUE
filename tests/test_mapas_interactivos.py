"""Pruebas unitarias para src/visualizacion/mapas_interactivos.py."""

from pathlib import Path

import geopandas as gpd

from src.visualizacion.mapas_interactivos import (
    COLOR_SIN_CLASIFICAR,
    construir_mapa_color_marca,
    construir_mapa_filtro_afore,
    guardar_mapa,
)


def _gdf_ejemplo() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "Nombre": ["AFORE PROFUTURO CDMX", "AFORE SURA EDOMEX"],
            "Razon_social": ["PROFUTURO AFORE", "AFORE SURA"],
            "Calle": ["", ""],
            "Colonia": ["", ""],
            "municipio": ["", ""],
            "estado": ["", ""],
            "CP": ["", ""],
            "afore_marca": ["PROFUTURO", "SURA"],
        },
        geometry=gpd.points_from_xy([-99.13, -103.42], [19.43, 25.40]),
        crs="EPSG:4326",
    )


def test_construir_mapa_color_marca_usa_color_cola_pasando_ocho_marcas():
    orden = [f"MARCA_{i}" for i in range(9)]

    mapa_color = construir_mapa_color_marca(orden, etiqueta_sin_clasificar="OTRO / SIN CLASIFICAR")

    colores_top_ocho = {mapa_color[m] for m in orden[:8]}
    assert len(colores_top_ocho) == 8
    assert mapa_color["MARCA_8"] not in colores_top_ocho


def test_construir_mapa_color_marca_da_color_propio_a_sin_clasificar():
    orden = ["PROFUTURO", "OTRO / SIN CLASIFICAR"]

    mapa_color = construir_mapa_color_marca(orden, etiqueta_sin_clasificar="OTRO / SIN CLASIFICAR")

    assert mapa_color["OTRO / SIN CLASIFICAR"] == COLOR_SIN_CLASIFICAR
    assert mapa_color["PROFUTURO"] != COLOR_SIN_CLASIFICAR


def test_construir_mapa_filtro_afore_crea_una_capa_por_marca():
    gdf = _gdf_ejemplo()

    mapa = construir_mapa_filtro_afore(gdf)
    html = mapa.get_root().render()

    assert "PROFUTURO" in html
    assert "SURA" in html


def test_guardar_mapa_escribe_archivo_html(tmp_path: Path):
    mapa = construir_mapa_filtro_afore(_gdf_ejemplo())
    ruta_salida = tmp_path / "mapas" / "afores.html"

    ruta_resultado = guardar_mapa(mapa, ruta_salida)

    assert ruta_resultado.exists()
    assert "<html" in ruta_resultado.read_text(encoding="utf-8").lower()
