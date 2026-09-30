"""Pruebas unitarias para src/ingesta/descargar_denue.py (sin red real)."""

import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from src.ingesta.descargar_denue import (
    ConfiguracionDescargaDenue,
    ErrorApiDenue,
    _eliminar_duplicados,
    copiar_csv_a_ruta_legado,
    descargar_denue,
    escribir_csv_completo,
    escribir_csv_subconjunto,
    escribir_csv_subconjunto_nacional,
    filtrar_por_palabra_clave,
    limpiar_municipio_desde_ubicacion,
    obtener_registros_entidad,
)


class _RespuestaFalsa:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_obtener_registros_entidad_se_detiene_cuando_pagina_es_menor(monkeypatch):
    paginas = [
        [{"Id": "1"}, {"Id": "2"}],
        [{"Id": "3"}],
    ]

    def get_falso(url, timeout):
        return _RespuestaFalsa(200, paginas.pop(0))

    monkeypatch.setattr(requests, "get", get_falso)

    registros = obtener_registros_entidad(
        "AFORE", "9", token="fake-token", tamano_pagina=2, segundos_espera=0
    )

    assert [r["Id"] for r in registros] == ["1", "2", "3"]


def test_obtener_registros_entidad_lanza_error_tras_reintentos(monkeypatch):
    def get_falso(url, timeout):
        return _RespuestaFalsa(500, {})

    monkeypatch.setattr(requests, "get", get_falso)

    with pytest.raises(ErrorApiDenue):
        obtener_registros_entidad(
            "AFORE", "9", token="fake-token", tamano_pagina=10, segundos_espera=0
        )


def test_eliminar_duplicados_quita_repetidos_por_id():
    registros = [{"Id": "1", "Nombre": "AFORE X"}, {"Id": "1", "Nombre": "AFORE X"}, {"Id": "2"}]

    resultado = _eliminar_duplicados(registros)

    assert len(resultado) == 2


def test_escribir_csv_completo_escribe_en_directorio_crudo(tmp_path: Path):
    df = pd.DataFrame({"Id": ["1", "2"], "Nombre": ["AFORE A", "AFORE B"]})

    ruta_csv = escribir_csv_completo(df, tmp_path, "afore_9", "20260101_000000")

    assert ruta_csv.parent == tmp_path
    assert ruta_csv.name == "denue_afore_9_20260101_000000.csv"
    assert len(pd.read_csv(ruta_csv)) == 2


def test_filtrar_por_palabra_clave_filtra_coincidencias(tmp_path: Path):
    df = pd.DataFrame({"Id": ["1", "2"], "Nombre": ["AFORE PROFUTURO", "AFORE SURA"]})

    df_subconjunto = filtrar_por_palabra_clave(df, "PROFUTURO", "9")

    assert df_subconjunto is not None
    assert len(df_subconjunto) == 1
    assert "PROFUTURO" in df_subconjunto.iloc[0]["Nombre"]


def test_filtrar_por_palabra_clave_retorna_none_sin_palabra_clave(tmp_path: Path):
    df = pd.DataFrame({"Id": ["1"], "Nombre": ["AFORE X"]})

    assert filtrar_por_palabra_clave(df, None, "9") is None


def test_filtrar_por_palabra_clave_encuentra_coincidencia_solo_en_razon_social(tmp_path: Path):
    # La palabra clave aparece únicamente en Razon_social, no en Nombre:
    # debe encontrarse igual (antes solo se revisaba la primera columna).
    df = pd.DataFrame(
        {
            "Id": ["1", "2"],
            "Nombre": ["AFORE GENERICO", "AFORE SURA"],
            "Razon_social": ["PROFUTURO AFORE SA DE CV", "AFORE SURA"],
        }
    )

    df_subconjunto = filtrar_por_palabra_clave(df, "PROFUTURO", "9")

    assert len(df_subconjunto) == 1
    assert df_subconjunto.iloc[0]["Id"] == "1"


def test_filtrar_por_palabra_clave_soporta_columnas_del_diccionario_oficial(tmp_path: Path):
    # Descarga masiva del portal INEGI usa nom_estab/raz_social en vez de
    # Nombre/Razon_social.
    df = pd.DataFrame({"Id": ["1"], "nom_estab": ["AFORE PROFUTURO"], "raz_social": ["PROFUTURO"]})

    df_subconjunto = filtrar_por_palabra_clave(df, "PROFUTURO", "9")

    assert df_subconjunto is not None
    assert len(df_subconjunto) == 1


def test_escribir_csv_subconjunto_escribe_archivo_por_entidad(tmp_path: Path):
    df_subconjunto = pd.DataFrame({"Id": ["1"], "Nombre": ["AFORE PROFUTURO"]})

    ruta_subconjunto = escribir_csv_subconjunto(df_subconjunto, tmp_path, "9", "20260101_000000", "PROFUTURO")

    assert ruta_subconjunto.parent == tmp_path
    assert ruta_subconjunto.name == "denue_profuturo_9_20260101_000000.csv"
    assert len(pd.read_csv(ruta_subconjunto)) == 1


def test_escribir_csv_subconjunto_nacional_acumula_entidades(tmp_path: Path):
    df_9 = pd.DataFrame({"Id": ["1"], "Nombre": ["AFORE PROFUTURO CDMX"]})
    df_15 = pd.DataFrame({"Id": ["2"], "Nombre": ["AFORE PROFUTURO EDOMEX"]})

    ruta_nacional = escribir_csv_subconjunto_nacional([df_9, df_15], tmp_path, "20260101_000000", "PROFUTURO")

    assert ruta_nacional is not None
    assert ruta_nacional.name == "denue_profuturo_nacional_20260101_000000.csv"
    assert len(pd.read_csv(ruta_nacional)) == 2


def test_escribir_csv_subconjunto_nacional_retorna_none_sin_coincidencias(tmp_path: Path):
    assert escribir_csv_subconjunto_nacional([], tmp_path, "20260101_000000", "PROFUTURO") is None


def test_copiar_csv_a_ruta_legado_crea_estructura_inegi(tmp_path: Path):
    ruta_origen = tmp_path / "denue_profuturo_09_20260101_000000.csv"
    pd.DataFrame({"Id": ["1"], "Nombre": ["AFORE PROFUTURO"]}).to_csv(ruta_origen, index=False)

    ruta_legado = copiar_csv_a_ruta_legado(ruta_origen, tmp_path)

    assert ruta_legado == tmp_path / "denue_09_csv" / "conjunto_de_datos" / "denue_inegi_09_.csv"
    assert ruta_legado.exists()
    assert len(pd.read_csv(ruta_legado)) == 1


def test_copiar_csv_a_ruta_legado_renombra_encabezados_a_formato_inegi(tmp_path: Path):
    # La ruta legado la lee entregables/Parte_1/01_leer_denue.R, que espera
    # los nombres oficiales de INEGI (nom_estab, latitud, longitud), no el
    # esquema PascalCase de la API (Nombre, Latitud, Longitud).
    ruta_origen = tmp_path / "denue_profuturo_09_20260101_000000.csv"
    pd.DataFrame(
        {"Id": ["1"], "Nombre": ["AFORE PROFUTURO"], "Latitud": [19.4], "Longitud": [-99.1]}
    ).to_csv(ruta_origen, index=False)

    ruta_legado = copiar_csv_a_ruta_legado(ruta_origen, tmp_path)

    columnas = list(pd.read_csv(ruta_legado).columns)
    assert "nom_estab" in columnas
    assert "latitud" in columnas
    assert "longitud" in columnas
    assert "Nombre" not in columnas


def test_limpiar_municipio_desde_ubicacion_extrae_parte_de_en_medio():
    serie = pd.Series(["IZTAPALAPA\n                    , Iztapalapa, CIUDAD DE MÉXICO"])

    resultado = limpiar_municipio_desde_ubicacion(serie)

    assert resultado.iloc[0] == "Iztapalapa"


def test_copiar_csv_a_ruta_legado_limpia_municipio(tmp_path: Path):
    ruta_origen = tmp_path / "denue_profuturo_09_20260101_000000.csv"
    pd.DataFrame(
        {
            "Id": ["1"],
            "Nombre": ["AFORE PROFUTURO"],
            "Ubicacion": ["IZTAPALAPA\n                    , Iztapalapa, CIUDAD DE MÉXICO"],
        }
    ).to_csv(ruta_origen, index=False)

    ruta_legado = copiar_csv_a_ruta_legado(ruta_origen, tmp_path)

    assert pd.read_csv(ruta_legado).iloc[0]["municipio"] == "Iztapalapa"


def _configuracion_dos_entidades(tmp_path: Path, **overrides) -> ConfiguracionDescargaDenue:
    base = {
        "terminos_busqueda": ["AFORE"],
        "token": "fake-token",
        "codigos_entidad": ["09", "15"],
        "directorio_crudo": tmp_path / "crudo",
        "directorio_procesado": tmp_path / "procesado",
    }
    base.update(overrides)
    return ConfiguracionDescargaDenue(**base)


def test_descargar_denue_genera_un_archivo_por_entidad(monkeypatch, tmp_path: Path):
    def obtener_registros_falso(termino_busqueda, codigo_entidad, token, tamano_pagina, segundos_espera):
        nombres = {"09": "AFORE PROFUTURO CDMX", "15": "AFORE COPPEL EDOMEX"}
        return [{"Id": f"{codigo_entidad}-1", "Nombre": nombres[codigo_entidad]}]

    monkeypatch.setattr(
        "src.ingesta.descargar_denue.obtener_registros_entidad", obtener_registros_falso
    )

    configuracion = _configuracion_dos_entidades(tmp_path, palabra_clave_subconjunto="PROFUTURO")

    salidas = descargar_denue(configuracion)

    assert len(salidas) == 2
    salidas_por_entidad = {s.codigo_entidad: s for s in salidas}

    # Entidad 09: coincide con la palabra clave -> genera subconjunto
    salida_09 = salidas_por_entidad["09"]
    assert salida_09.ruta_json.exists()
    assert salida_09.ruta_json.parent == configuracion.directorio_crudo
    assert salida_09.ruta_csv.exists()
    assert salida_09.ruta_csv.parent == configuracion.directorio_crudo
    assert salida_09.ruta_csv_subconjunto is not None
    assert salida_09.ruta_csv_subconjunto.parent == configuracion.directorio_procesado
    assert len(pd.read_csv(salida_09.ruta_csv)) == 1
    assert len(pd.read_csv(salida_09.ruta_csv_subconjunto)) == 1

    # Entidad 15: no coincide con la palabra clave -> subconjunto vacío (0 filas)
    salida_15 = salidas_por_entidad["15"]
    assert salida_15.ruta_csv_subconjunto is not None
    assert len(pd.read_csv(salida_15.ruta_csv_subconjunto)) == 0
    assert len(pd.read_csv(salida_15.ruta_csv)) == 1

    # CSV nacional acumulado: solo la fila de la entidad 09, que sí coincidió
    rutas_nacionales = list(configuracion.directorio_procesado.glob("denue_profuturo_nacional_*.csv"))
    assert len(rutas_nacionales) == 1
    assert len(pd.read_csv(rutas_nacionales[0])) == 1

    # Copia en la ruta legado de la descarga masiva del portal INEGI (solo entidad 09)
    ruta_legado = configuracion.directorio_procesado / "denue_09_csv" / "conjunto_de_datos" / "denue_inegi_09_.csv"
    assert ruta_legado.exists()
    assert len(pd.read_csv(ruta_legado)) == 1


def test_descargar_denue_ruta_legado_solo_incluye_entidad_09(monkeypatch, tmp_path: Path):
    # Las entidades 09 y 15 coinciden con la palabra clave -> el nacional
    # acumula ambas, pero la ruta legado (denue_inegi_09_.csv) debe quedarse
    # solo con los registros de la entidad 09.
    def obtener_registros_falso(termino_busqueda, codigo_entidad, token, tamano_pagina, segundos_espera):
        nombres = {"09": "AFORE PROFUTURO CDMX", "15": "AFORE PROFUTURO EDOMEX"}
        return [{"Id": f"{codigo_entidad}-1", "Nombre": nombres[codigo_entidad]}]

    monkeypatch.setattr(
        "src.ingesta.descargar_denue.obtener_registros_entidad", obtener_registros_falso
    )

    configuracion = _configuracion_dos_entidades(tmp_path, palabra_clave_subconjunto="PROFUTURO")

    descargar_denue(configuracion)

    rutas_nacionales = list(configuracion.directorio_procesado.glob("denue_profuturo_nacional_*.csv"))
    assert len(pd.read_csv(rutas_nacionales[0])) == 2  # nacional: entidad 09 + 15

    ruta_legado = configuracion.directorio_procesado / "denue_09_csv" / "conjunto_de_datos" / "denue_inegi_09_.csv"
    df_legado = pd.read_csv(ruta_legado)
    assert len(df_legado) == 1  # legado: solo entidad 09
    assert df_legado.iloc[0]["id"] == "09-1"
    assert "nom_estab" in df_legado.columns


def test_descargar_denue_no_deduplica_en_crudo_solo_en_procesado(monkeypatch, tmp_path: Path):
    def obtener_registros_falso(termino_busqueda, codigo_entidad, token, tamano_pagina, segundos_espera):
        # Mismo Id repetido a propósito, simulando resultados que se solapan
        # entre términos de búsqueda para la misma entidad.
        return [{"Id": "1", "Nombre": "AFORE PROFUTURO CDMX"}]

    monkeypatch.setattr(
        "src.ingesta.descargar_denue.obtener_registros_entidad", obtener_registros_falso
    )

    configuracion = _configuracion_dos_entidades(
        tmp_path,
        terminos_busqueda=["AFORE", "PROFUTURO"],
        codigos_entidad=["9"],
        palabra_clave_subconjunto=None,
    )

    salidas = descargar_denue(configuracion)

    assert len(salidas) == 1
    df_crudo = pd.read_csv(salidas[0].ruta_csv)
    assert len(df_crudo) == 2  # sin deduplicar: un registro por cada término consultado

    with open(salidas[0].ruta_json, encoding="utf-8") as fh:
        registros_json = json.load(fh)
    assert len(registros_json) == 2  # el JSON crudo tampoco deduplica


def test_descargar_denue_omite_entidades_sin_registros(monkeypatch, tmp_path: Path):
    def obtener_registros_falso(termino_busqueda, codigo_entidad, token, tamano_pagina, segundos_espera):
        return [{"Id": "1", "Nombre": "AFORE X"}] if codigo_entidad == "09" else []

    monkeypatch.setattr(
        "src.ingesta.descargar_denue.obtener_registros_entidad", obtener_registros_falso
    )

    configuracion = _configuracion_dos_entidades(tmp_path, palabra_clave_subconjunto=None)

    salidas = descargar_denue(configuracion)

    assert len(salidas) == 1
    assert salidas[0].codigo_entidad == "09"


def test_descargar_denue_lanza_error_sin_token(tmp_path: Path):
    configuracion = _configuracion_dos_entidades(tmp_path, token=None)

    with pytest.raises(ValueError):
        descargar_denue(configuracion)


def test_descargar_denue_lanza_error_sin_registros_en_ninguna_entidad(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "src.ingesta.descargar_denue.obtener_registros_entidad",
        lambda *args, **kwargs: [],
    )

    configuracion = _configuracion_dos_entidades(tmp_path)

    with pytest.raises(ErrorApiDenue):
        descargar_denue(configuracion)
