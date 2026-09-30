# 05 - Mapa de Puntos

**Tarea:** Arma un mapa de puntos (MyMaps o R con leaflet) de tu giro en la entidad elegida.
**Método**

Se usó R con `leaflet`, partiendo de los scripts previos:

1. [`01_leer_denue.R`](01_leer_denue.R) — lee el DENUE de la entidad, filtra por el giro
   "afore" sobre `nom_estab` y descarta registros sin coordenadas, guardando el resultado en
   [`denue_filtrado.csv`](denue_filtrado.csv).
2. [`02_mapa_puntos.R`](02_mapa_puntos.R) — lee `denue_filtrado.csv` y construye el mapa de
   puntos interactivo con `leaflet::addCircleMarkers`, usando `longitud`/`latitud` para
   posicionar cada sucursal y el popup con nombre, actividad y municipio.

**Nota:** el tile provider original (`providers$CartoDB.Positron`) empezó a exigir API key: se
cambió a `providers$OpenStreetMap` (gratuito, sin key) para que el mapa se renderice
correctamente.

**Evidencia:** [`mapa_puntos.html`](mapa_puntos.html) — mapa interactivo exportado como HTML
independiente (`htmlwidgets::saveWidget`), con las 36 sucursales de AFORE encontradas.
