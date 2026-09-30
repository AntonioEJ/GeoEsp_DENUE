"""Utilidades de lectura/escritura de datos (csv, shp, geojson, gpkg)."""

import yaml


def cargar_configuracion(ruta: str = "config/config.yaml") -> dict:
    """Carga el archivo de configuración YAML del proyecto."""
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
