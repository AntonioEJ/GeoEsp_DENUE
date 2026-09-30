"""Utilidades de reproyección y validación de geometrías."""


def reproyectar(gdf, crs_destino: str):
    """Reproyecta un GeoDataFrame al CRS objetivo (ej. definido en config/crs_config.yaml)."""
    return gdf.to_crs(crs_destino)


def validar_geometrias(gdf):
    """Filtra geometrías nulas o inválidas de un GeoDataFrame."""
    return gdf[gdf.geometry.notnull() & gdf.geometry.is_valid]
