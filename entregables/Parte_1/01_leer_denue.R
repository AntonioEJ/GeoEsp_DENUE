# =========================================================

# Tarea 3
# Jose Antonio Esparza
# 01_leer_denue.R
# Lectura, inspección y filtrado inicial del DENUE (INEGI)

# =========================================================
# Uso: cambia "ruta_denue" y "giro_buscado" por los tuyos.
# Columnas típicas del DENUE: nom_estab, nombre_act, codigo_act,
# municipio, localidad, latitud, longitud, per_ocu, telefono, www

library(tidyverse)  # dplyr, readr, stringr, tidyr

# 1. Ruta al CSV del DENUE de Ciudad de México descargado de INEGI
ruta_denue <- "../../data/processed/denue/denue_09_csv/conjunto_de_datos/denue_inegi_09_.csv"

denue <- read_csv(ruta_denue, locale = locale(encoding = "latin1"))

# 2. Explora la estructura general antes de hacer nada
glimpse(denue)
names(denue)

# 3. Limpieza básica: cuántos registros tienen coordenadas faltantes
denue %>%
  summarise(
    total   = n(),
    sin_lat = sum(is.na(latitud)),
    sin_lon = sum(is.na(longitud)),
    duplicados_nombre = sum(duplicated(nom_estab))
  )

# 4. Filtra por el giro económico elegido
#    "AFORE" aparece en el nombre del establecimiento (nom_estab)

giro_buscado <- "afore "

denue_filtrado <- denue %>%
  filter(str_detect(str_to_lower(nom_estab), giro_buscado)) %>%
  filter(!is.na(latitud), !is.na(longitud))

nrow(denue_filtrado)

# 5. Conteo por municipio (equivalente al ejercicio de OXXO visto en clase)
denue_filtrado %>%
  count(municipio, sort = TRUE)

# 6. Guarda el subconjunto limpio para usarlo en los siguientes scripts
write_csv(denue_filtrado, "denue_filtrado.csv")
