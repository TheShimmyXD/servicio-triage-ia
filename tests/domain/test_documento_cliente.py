from __future__ import annotations

import pytest

from domain.contrato import DocumentoCliente
from domain.documento_cliente import extraer_documento
from tests.domain.datos import TEXTO_JUANA


def test_juana_da_cedula_con_su_numero():
    assert extraer_documento(TEXTO_JUANA) == DocumentoCliente("CC", "102045678")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Soy cliente con CC 102045678 y no tengo gas", DocumentoCliente("CC", "102045678")),
        ("C.C. No. 1.020.456.789, falla en el medidor", DocumentoCliente("CC", "1020456789")),
        ("mi CÉDULA: 79 555 111", None),  # espacios entre grupos: no se arriesga a unir
        ("Cédula de extranjería 4567890, llamo por la factura", DocumentoCliente("CE", "4567890")),
        (
            "Empresa con NIT 900.123.456-7 reporta cobro doble",
            DocumentoCliente("NIT", "900123456-7"),
        ),
        ("Tarjeta de identidad 1001234567 de mi hijo", DocumentoCliente("TI", "1001234567")),
        ("Pasaporte AB123456, extranjero", DocumentoCliente("PA", "AB123456")),
    ],
)
def test_tipos_de_documento(texto, esperado):
    assert extraer_documento(texto) == esperado


def test_sin_documento_devuelve_none():
    assert extraer_documento("La estufa no prende desde ayer, necesito revisión") is None


def test_numero_corto_no_es_documento():
    assert extraer_documento("cc 1234 por favor") is None


def test_gana_el_documento_que_aparece_primero():
    texto = "NIT 900123456 de la empresa; contacto con cédula 102045678"
    assert extraer_documento(texto) == DocumentoCliente("NIT", "900123456")
