"""Mapas estáticos (matplotlib / geopandas.plot) para reportes."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt

COLOR_DEFECTO = "#2a78d6"


def graficar_mapa_puntos(
    gdf: gpd.GeoDataFrame,
    ruta_salida: Path | None = None,
    titulo: str = "",
) -> plt.Axes:
    """Genera un mapa estático de puntos (un solo color; sin categorías).

    Args:
        gdf: GeoDataFrame con geometría de puntos.
        ruta_salida: Si se provee, guarda la figura en esta ruta (ej. reports/figures/).
        titulo: Título del mapa.

    Returns:
        Axes de matplotlib con el mapa dibujado.
    """
    _fig, ax = plt.subplots(figsize=(8, 8))
    gdf.plot(ax=ax, color=COLOR_DEFECTO, markersize=15, alpha=0.85)
    ax.set_title(titulo)
    ax.set_axis_off()
    if ruta_salida is not None:
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        ax.figure.savefig(ruta_salida, dpi=150, bbox_inches="tight")
    return ax
