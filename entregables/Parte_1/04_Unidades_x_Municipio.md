# 04 - Unidades x Municipio

**Tarea:** Cuenta cuántas unidades hay de tu giro por municipio (tabla).

**Evidencia:**

```r
denue_filtrado %>%
  count(municipio, sort = TRUE)
```

| municipio             |  n  |
|-----------------------|-----|
| Cuauhtémoc            |  9  |
| Benito Juárez         |  6  |
| Miguel Hidalgo        |  6  |
| Iztapalapa            |  4  |
| Coyoacán              |  2  |
| Gustavo A. Madero     |  2  |
| Iztacalco             |  2  |
| Azcapotzalco          |  1  |
| Cuajimalpa de Morelos |  1  |
| Tlalpan               |  1  |
| Xochimilco            |  1  |
| Álvaro Obregón        |  1  |
| **Total**             | **36** |
