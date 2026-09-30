# =========================================================
# Tarea 3
# Jose Antonio Esparza
# 02_mapa_puntos.R

# Mapa de puntos interactivo (nivel Parte 1 - réplica)
# =========================================================

library(leaflet)
library(readr)

denue_filtrado <- read_csv("denue_filtrado.csv")

mapa <- leaflet(denue_filtrado) %>%
  addProviderTiles(providers$CartoDB.Positron) %>%
  addCircleMarkers(
    lng = ~longitud, lat = ~latitud,
    radius = 4, color = "#2A7DE1", stroke = FALSE, fillOpacity = 0.7,
    popup = ~paste0("<b>", nom_estab, "</b><br>",
                     nombre_act, "<br>",
                     municipio)
  )

mapa

# Para guardarlo como HTML independiente:
library(htmlwidgets)

saveWidget(mapa, "mapa_puntos.html", selfcontained = TRUE)
