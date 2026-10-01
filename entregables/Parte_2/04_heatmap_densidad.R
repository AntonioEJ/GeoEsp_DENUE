# =========================================================
# 04_heatmap_densidad.R
# Heatmap (densidad kernel) del giro elegido (nivel Parte 2 - reto)
# =========================================================

library(ggplot2)
library(readr)

denue_filtrado <- read_csv("denue_filtrado.csv")

# =========================================================
# REQUISITO DE RIGOR: compara al menos dos anchos de banda
# =========================================================
# El ancho de banda (bandwidth, h) controla qué tanto se "suaviza" la
# densidad. Un h muy chico sobreajusta a los puntos individuales; uno
# muy grande esconde la estructura real. Genera el heatmap con al
# menos dos valores de h y compáralos.

# h por defecto (calculado automáticamente por ggplot2/MASS::bandwidth.nrd)
ggplot(denue_filtrado, aes(x = longitud, y = latitud)) +
  stat_density_2d(aes(fill = after_stat(level)), geom = "polygon", alpha = 0.6) +
  geom_point(size = 0.5, alpha = 0.4, color = "black") +
  scale_fill_viridis_c(option = "inferno") +
  coord_equal() +
  theme_minimal() +
  labs(title = "Heatmap - ancho de banda por defecto")

# h más pequeño (más detalle, más ruido) vs. h más grande (más suave)
h_defecto <- c(MASS::bandwidth.nrd(denue_filtrado$longitud),
               MASS::bandwidth.nrd(denue_filtrado$latitud))

ggplot(denue_filtrado, aes(x = longitud, y = latitud)) +
  stat_density_2d(aes(fill = after_stat(level)), geom = "polygon",
                   alpha = 0.6, h = h_defecto * 0.5) +
  geom_point(size = 0.5, alpha = 0.4, color = "black") +
  scale_fill_viridis_c(option = "inferno") +
  coord_equal() +
  theme_minimal() +
  labs(title = "Heatmap - ancho de banda reducido (más detalle)")

ggplot(denue_filtrado, aes(x = longitud, y = latitud)) +
  stat_density_2d(aes(fill = after_stat(level)), geom = "polygon",
                   alpha = 0.6, h = h_defecto * 2) +
  geom_point(size = 0.5, alpha = 0.4, color = "black") +
  scale_fill_viridis_c(option = "inferno") +
  coord_equal() +
  theme_minimal() +
  labs(title = "Heatmap - ancho de banda amplio (más suave)")

# Escribe 3-4 líneas: ¿cuál interpretación te parece más confiable para
# tus datos y por qué? (piensa en cuántos puntos tienes y qué tan
# dispersos están)

# Opcional: heatmap interactivo sobre un mapa real (leaflet.extras)
 library(leaflet)
 library(leaflet.extras)
#
 leaflet(denue_filtrado) %>%
   addProviderTiles(providers$OpenStreetMap) %>%
   addHeatmap(lng = ~longitud, lat = ~latitud,
              radius = 12, blur = 20, max = 0.6)

# Opcional (huecos de mercado): superpón este heatmap con un mapa de
# densidad poblacional (manzana/AGEB) para ver zonas de alta población
# donde tu heatmap muestra baja densidad de oferta.
