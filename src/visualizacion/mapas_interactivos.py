"""Mapas interactivos (folium) con filtro por marca de AFORE."""

from __future__ import annotations

import logging
from pathlib import Path

import folium
import geopandas as gpd

logger = logging.getLogger(__name__)

# Paleta categórica (8 tonos) validada para distinguibilidad bajo daltonismo.
# Ver dataviz skill / docs de diseño del proyecto: orden fijo, nunca ciclado;
# más allá de 8 marcas se usa un gris de "cola" en vez de generar más tonos.
COLORES_CATEGORICOS: list[str] = [
    "#2a78d6",  # azul
    "#eb6834",  # naranja
    "#1baf7a",  # aqua
    "#eda100",  # amarillo
    "#e87ba4",  # magenta
    "#008300",  # verde
    "#4a3aa7",  # violeta
    "#e34948",  # rojo
]
COLOR_COLA = "#898781"
COLOR_SIN_CLASIFICAR = "#c3c2b7"
CENTRO_MEXICO: tuple[float, float] = (23.6345, -102.5528)


def construir_mapa_color_marca(
    orden_marcas: list[str], etiqueta_sin_clasificar: str
) -> dict[str, str]:
    """Asigna un color fijo por marca, en el orden dado (ej. de mayor a menor frecuencia).

    Las primeras ``len(COLORES_CATEGORICOS)`` marcas reciben un color
    categórico distinto; el resto comparte un gris de "cola" en vez de
    generar tonos adicionales indistinguibles, y el bucket sin clasificar
    recibe su propio gris.

    Args:
        orden_marcas: Marcas ordenadas (ej. de mayor a menor frecuencia).
        etiqueta_sin_clasificar: Etiqueta reservada para registros sin clasificar.

    Returns:
        Diccionario marca -> color hexadecimal.
    """
    mapa_color: dict[str, str] = {}
    marcas_ordenadas = [m for m in orden_marcas if m != etiqueta_sin_clasificar]
    for i, marca in enumerate(marcas_ordenadas):
        mapa_color[marca] = COLORES_CATEGORICOS[i] if i < len(COLORES_CATEGORICOS) else COLOR_COLA
    if etiqueta_sin_clasificar in orden_marcas:
        mapa_color[etiqueta_sin_clasificar] = COLOR_SIN_CLASIFICAR
    return mapa_color


def _html_popup(fila) -> str:
    """Arma el HTML del popup de una sucursal."""
    razon_social = fila.get("Razon_social") or ""
    return (
        f"<b>{fila.get('Nombre', '')}</b><br>"
        f"{razon_social}<br>"
        f"{fila.get('Calle', '')}, {fila.get('Colonia', '')}<br>"
        f"{fila.get('municipio', '')}, {fila.get('estado', '')}<br>"
        f"CP {fila.get('CP', '')}"
    )


def construir_mapa_filtro_afore(
    gdf: gpd.GeoDataFrame,
    columna_marca: str = "afore_marca",
    etiqueta_sin_clasificar: str = "OTRO / SIN CLASIFICAR",
) -> folium.Map:
    """Construye un mapa interactivo de sucursales con filtro por marca de AFORE.

    Cada marca se agrega como una capa (``FeatureGroup``) independiente; el
    ``LayerControl`` deja mostrar/ocultar cada una (ej. dejar solo
    "PROFUTURO" visible desmarcando las demás).

    Args:
        gdf: GeoDataFrame con geometría de puntos y la columna ``columna_marca``.
        columna_marca: Columna con la marca de AFORE por fila.
        etiqueta_sin_clasificar: Etiqueta del bucket sin clasificar.

    Returns:
        Mapa de folium listo para mostrar en el notebook o guardar con
        ``guardar_mapa``.
    """
    conteo_marcas = gdf[columna_marca].value_counts()
    mapa_color_marca = construir_mapa_color_marca(conteo_marcas.index.tolist(), etiqueta_sin_clasificar)

    # OpenStreetMap: no requiere API key (a diferencia de los tiles de CartoDB).
    mapa = folium.Map(location=CENTRO_MEXICO, zoom_start=5, tiles="OpenStreetMap")

    for marca, conteo in conteo_marcas.items():
        color = mapa_color_marca[marca]
        capa = folium.FeatureGroup(name=f"{marca} ({conteo})", show=True)
        subconjunto = gdf[gdf[columna_marca] == marca]
        for _, fila in subconjunto.iterrows():
            folium.CircleMarker(
                location=[fila.geometry.y, fila.geometry.x],
                radius=6,
                color=color,
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                tooltip=marca,
                popup=folium.Popup(_html_popup(fila), max_width=280),
            ).add_to(capa)
        capa.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)
    logger.info("Mapa generado: %d marcas, %d sucursales totales", len(conteo_marcas), len(gdf))
    return mapa


def guardar_mapa(mapa: folium.Map, ruta_salida: Path) -> Path:
    """Guarda un mapa de folium como HTML standalone.

    Args:
        mapa: Mapa de folium a guardar.
        ruta_salida: Ruta destino (ej. en ``reports/maps/``).

    Returns:
        La misma ruta, para encadenar.
    """
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    mapa.save(str(ruta_salida))
    logger.info("Mapa guardado en %s", ruta_salida)
    return ruta_salida
