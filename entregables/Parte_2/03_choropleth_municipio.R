# =========================================================
# 03_choropleth_municipio.R
# Mapa coroplético por municipio (nivel Parte 2 - reto)
# =========================================================
# Requiere el shapefile de municipios del estado elegido
# (Marco Geoestadístico, INEGI) y el CSV filtrado del script 01.

library(sf)
library(dplyr)
library(readr)
library(tidyr)
library(ggplot2)

# 1. Carga el shapefile de municipios y ajusta su CRS a WGS84
#    options = "ENCODING=ISO-8859-1": el .cpg del shapefile de INEGI declara
#    ISO-8859-1; sin forzarlo, GDAL puede no recodificar bien los acentos de
#    NOMGEO a UTF-8, y entonces no cruza con poblacion_municipio.csv.
municipios <- st_read("municipios_estado.shp", options = "ENCODING=ISO-8859-1") %>%
  st_transform(4326)

# 2. Carga los puntos del DENUE ya filtrados (script 01) y conviértelos a sf
denue_filtrado <- read_csv("denue_filtrado.csv")

denue_sf <- st_as_sf(denue_filtrado,
                      coords = c("longitud", "latitud"),
                      crs = 4326)

# 3. Unión espacial: asigna a cada punto el municipio que lo contiene
denue_con_municipio <- st_join(denue_sf, municipios)

# 4. Conteo de unidades económicas por municipio
#    El shapefile 09mun.shp (Marco Geoestadístico INEGI) usa NOMGEO como
#    nombre del municipio.
conteo_municipio <- denue_con_municipio %>%
  st_drop_geometry() %>%
  count(NOMGEO, name = "n_unidades")

# 5. Une el conteo de vuelta a los polígonos para poder pintarlos
municipios_conteo <- municipios %>%
  left_join(conteo_municipio, by = "NOMGEO") %>%
  mutate(n_unidades = replace_na(n_unidades, 0))

# 6. Mapa coroplético (conteo crudo)
ggplot(municipios_conteo) +
  geom_sf(aes(fill = n_unidades), color = "white", linewidth = 0.2) +
  scale_fill_viridis_c(option = "plasma", name = "Unidades") +
  theme_minimal() +
  labs(title = "Densidad del giro elegido por municipio (conteo crudo)",
       subtitle = "DENUE INEGI")

# =========================================================
# REQUISITO DE RIGOR: normaliza por población
# =========================================================
# Población por municipio: Censo de Población y Vivienda 2020 (INEGI),
# producto ITER, filas "Total del Municipio" (ver poblacion_municipio.csv).
poblacion_municipio <- read_csv("poblacion_municipio.csv")  # columnas: NOMGEO, poblacion

# select(-any_of(...)) hace este bloque seguro de re-correr: si ya existía
# "poblacion"/"tasa_10k" de una corrida anterior, el left_join generaría
# "poblacion.x"/"poblacion.y" en vez de "poblacion" y el mutate() de abajo
# fallaría con "object 'poblacion' not found".
municipios_conteo <- municipios_conteo %>%
  select(-any_of(c("poblacion", "tasa_10k"))) %>%
  left_join(poblacion_municipio, by = "NOMGEO") %>%
  mutate(tasa_10k = (n_unidades / poblacion) * 10000)

# 7. Mapa coroplético normalizado (tasa por cada 10,000 habitantes)
ggplot(municipios_conteo) +
  geom_sf(aes(fill = tasa_10k), color = "white", linewidth = 0.2) +
  scale_fill_viridis_c(option = "plasma", name = "Unidades\npor 10k hab.") +
  theme_minimal() +
  labs(title = "Densidad del giro elegido por municipio (normalizado por población)",
       subtitle = "DENUE INEGI")

# 8. Compara los dos rankings (crudo vs. normalizado) y explica los cambios
#    as_tibble() es necesario: st_drop_geometry() deja un data.frame plano,
#    y print(n = ...) en un data.frame (no tibble) falla con "invalid
#    'na.print' specification" (n se empareja por error con na.print).
municipios_conteo %>%
  st_drop_geometry() %>%
  as_tibble() %>%
  select(NOMGEO, n_unidades, poblacion, tasa_10k) %>%
  arrange(desc(n_unidades)) %>%
  print(n = 10)

municipios_conteo %>%
  st_drop_geometry() %>%
  as_tibble() %>%
  select(NOMGEO, n_unidades, poblacion, tasa_10k) %>%
  arrange(desc(tasa_10k)) %>%
  print(n = 10)
