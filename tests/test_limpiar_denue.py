"""Pruebas unitarias para src/preprocesamiento/limpiar_denue.py."""

from pathlib import Path

import pandas as pd
import pytest

from src.preprocesamiento.limpiar_denue import (
    ETIQUETA_SIN_CLASIFICAR,
    _extraer_codigo_entidad,
    _extraer_marca_tiempo,
    clasificar_marca_afore,
    encontrar_csv_nacional_reciente,
    encontrar_csvs_crudos_recientes,
    extraer_municipio_estado,
    filtrar_afores,
    filtrar_coordenadas_validas,
    limpiar_dataframe,
    limpiar_denue,
)


def test_clasificar_marca_afore_encuentra_palabra_clave_conocida():
    assert clasificar_marca_afore("AFORE XXI BANORTE", "AFORE XXI BANORTE") == "XXI BANORTE"
    assert clasificar_marca_afore("PROFUTURO AFORE", "PROFUTURO AFORE") == "PROFUTURO"


def test_clasificar_marca_afore_usa_sin_clasificar_como_respaldo():
    assert clasificar_marca_afore("ASESORES DE AFORE BROKER", None) == ETIQUETA_SIN_CLASIFICAR


def test_extraer_municipio_estado_obtiene_ambos_valores():
    municipio, estado = extraer_municipio_estado(" NAZARENO   , Lerdo, DURANGO")
    assert municipio == "Lerdo"
    assert estado == "DURANGO"


def test_extraer_municipio_estado_maneja_valores_faltantes():
    assert extraer_municipio_estado("") == ("", "")


def test_filtrar_coordenadas_validas_descarta_cero_y_fuera_de_rango():
    df = pd.DataFrame(
        {
            "Longitud": [-99.13, 0.0, -200.0, None],
            "Latitud": [19.43, 0.0, 25.0, 20.0],
        }
    )

    resultado = filtrar_coordenadas_validas(df)

    assert len(resultado) == 1
    assert resultado.iloc[0]["Longitud"] == -99.13


def test_filtrar_afores_agrega_columnas_derivadas():
    df = pd.DataFrame(
        {
            "Nombre": ["AFORE SURA DURANGO"],
            "Razon_social": ["FORE SURA"],
            "Ubicacion": [", Durango, DURANGO"],
        }
    )

    resultado = filtrar_afores(df)

    assert resultado.loc[0, "afore_marca"] == "SURA"
    assert resultado.loc[0, "municipio"] == "Durango"
    assert resultado.loc[0, "estado"] == "DURANGO"


def test_filtrar_afores_soporta_columnas_del_diccionario_oficial():
    # Descarga masiva del portal INEGI usa nom_estab/raz_social en vez de
    # Nombre/Razon_social.
    df = pd.DataFrame(
        {
            "nom_estab": ["AFORE SURA DURANGO"],
            "raz_social": ["FORE SURA"],
            "Ubicacion": [", Durango, DURANGO"],
        }
    )

    resultado = filtrar_afores(df)

    assert resultado.loc[0, "afore_marca"] == "SURA"


def test_limpiar_dataframe_aplica_coordenadas_y_clasificacion():
    df = pd.DataFrame(
        {
            "Nombre": ["AFORE SURA DURANGO", "AFORE X"],
            "Razon_social": ["FORE SURA", "AFORE X"],
            "Ubicacion": [", Durango, DURANGO", ", Culiacan, SINALOA"],
            "Longitud": [-104.66, 0.0],
            "Latitud": [24.02, 0.0],
        }
    )

    resultado = limpiar_dataframe(df)

    assert len(resultado) == 1  # la fila con coordenadas 0,0 se descarta
    assert resultado.iloc[0]["afore_marca"] == "SURA"


def test_extraer_marca_tiempo_obtiene_sufijo_de_timestamp():
    assert _extraer_marca_tiempo("denue_afore_9_20260930_101139") == "20260930_101139"
    assert _extraer_marca_tiempo("sin_timestamp") is None


def test_extraer_codigo_entidad_obtiene_el_codigo():
    assert _extraer_codigo_entidad("denue_afore_9_20260930_101139", "20260930_101139") == "9"
    assert _extraer_codigo_entidad("otro_formato", "20260930_101139") is None


def test_encontrar_csvs_crudos_recientes_lanza_error_si_no_hay_archivos(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        encontrar_csvs_crudos_recientes(tmp_path)


def test_encontrar_csvs_crudos_recientes_toma_solo_la_corrida_mas_reciente(tmp_path: Path):
    (tmp_path / "denue_afore_9_20260101_000000.csv").write_text("Id\n1\n")
    reciente_9 = tmp_path / "denue_afore_9_20260930_101139.csv"
    reciente_15 = tmp_path / "denue_afore_15_20260930_101139.csv"
    reciente_9.write_text("Id\n1\n")
    reciente_15.write_text("Id\n1\n")

    resultado = encontrar_csvs_crudos_recientes(tmp_path)

    assert sorted(resultado) == sorted([reciente_9, reciente_15])


def test_encontrar_csv_nacional_reciente_lanza_error_si_no_hay_archivos(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        encontrar_csv_nacional_reciente(tmp_path)


def test_encontrar_csv_nacional_reciente_toma_el_mas_reciente(tmp_path: Path):
    (tmp_path / "denue_afore_nacional_20260101_000000.csv").write_text("Id\n1\n")
    reciente = tmp_path / "denue_afore_nacional_20260930_150832.csv"
    reciente.write_text("Id\n1\n")

    resultado = encontrar_csv_nacional_reciente(tmp_path)

    assert resultado == reciente


def test_limpiar_denue_genera_un_csv_limpio_por_entidad(tmp_path: Path):
    directorio_crudo = tmp_path / "raw"
    directorio_procesado = tmp_path / "processed"
    directorio_crudo.mkdir()

    pd.DataFrame(
        {
            "Nombre": ["AFORE SURA DURANGO"],
            "Razon_social": ["FORE SURA"],
            "Ubicacion": [", Durango, DURANGO"],
            "Longitud": [-104.66],
            "Latitud": [24.02],
        }
    ).to_csv(directorio_crudo / "denue_afore_9_20260930_101139.csv", index=False)
    pd.DataFrame(
        {
            "Nombre": ["AFORE COPPEL ZACATECAS"],
            "Razon_social": ["AFORE COPPEL"],
            "Ubicacion": [", Zacatecas, ZACATECAS"],
            "Longitud": [-102.57],
            "Latitud": [22.77],
        }
    ).to_csv(directorio_crudo / "denue_afore_32_20260930_101139.csv", index=False)

    rutas_salida = limpiar_denue(directorio_crudo, directorio_procesado)

    assert sorted(r.name for r in rutas_salida) == [
        "denue_afore_limpio_20260930_101139.csv",
        "denue_afore_limpio_32_20260930_101139.csv",
        "denue_afore_limpio_9_20260930_101139.csv",
    ]
    for ruta in rutas_salida:
        assert ruta.parent == directorio_procesado
        assert ruta.exists()

    df_9 = pd.read_csv(directorio_procesado / "denue_afore_limpio_9_20260930_101139.csv")
    assert df_9.loc[0, "afore_marca"] == "SURA"
    df_32 = pd.read_csv(directorio_procesado / "denue_afore_limpio_32_20260930_101139.csv")
    assert df_32.loc[0, "afore_marca"] == "COPPEL"

    df_combinado = pd.read_csv(directorio_procesado / "denue_afore_limpio_20260930_101139.csv")
    assert len(df_combinado) == 2
    assert sorted(df_combinado["afore_marca"]) == ["COPPEL", "SURA"]


def test_limpiar_denue_no_genera_combinado_con_una_sola_entidad(tmp_path: Path):
    directorio_crudo = tmp_path / "raw"
    directorio_procesado = tmp_path / "processed"
    directorio_crudo.mkdir()

    pd.DataFrame(
        {
            "Nombre": ["AFORE SURA DURANGO"],
            "Razon_social": ["FORE SURA"],
            "Ubicacion": [", Durango, DURANGO"],
            "Longitud": [-104.66],
            "Latitud": [24.02],
        }
    ).to_csv(directorio_crudo / "denue_afore_9_20260930_101139.csv", index=False)

    rutas_salida = limpiar_denue(directorio_crudo, directorio_procesado)

    assert [r.name for r in rutas_salida] == ["denue_afore_limpio_9_20260930_101139.csv"]


def test_limpiar_denue_respeta_ruta_csv_crudo_especifica(tmp_path: Path):
    directorio_crudo = tmp_path / "raw"
    directorio_procesado = tmp_path / "processed"
    directorio_crudo.mkdir()

    ruta_csv_crudo = directorio_crudo / "denue_afore_9_20260930_101139.csv"
    pd.DataFrame(
        {
            "Nombre": ["AFORE SURA DURANGO"],
            "Razon_social": ["FORE SURA"],
            "Ubicacion": [", Durango, DURANGO"],
            "Longitud": [-104.66],
            "Latitud": [24.02],
        }
    ).to_csv(ruta_csv_crudo, index=False)

    rutas_salida = limpiar_denue(directorio_crudo, directorio_procesado, ruta_csv_crudo=ruta_csv_crudo)

    assert len(rutas_salida) == 1
    assert rutas_salida[0] == directorio_procesado / "denue_afore_limpio_9_20260930_101139.csv"
