"""Validação de CNPJ (dígitos verificadores, módulo 11)."""

from __future__ import annotations

import re

_PESOS_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_2 = (6, *_PESOS_1)


def somente_digitos(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _digito(numeros: str, pesos: tuple[int, ...]) -> str:
    resto = sum(int(n) * p for n, p in zip(numeros, pesos, strict=True)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(cnpj: str) -> bool:
    numeros = somente_digitos(cnpj)
    if len(numeros) != 14 or numeros == numeros[0] * 14:
        return False
    primeiro = _digito(numeros[:12], _PESOS_1)
    segundo = _digito(numeros[:12] + primeiro, _PESOS_2)
    return numeros[12:] == primeiro + segundo


def completar_cnpj(base: str) -> str:
    """Acrescenta os dois dígitos verificadores a uma base de 12 dígitos."""
    numeros = somente_digitos(base)
    if len(numeros) != 12:
        raise ValueError("A base do CNPJ deve ter 12 dígitos.")
    primeiro = _digito(numeros, _PESOS_1)
    return numeros + primeiro + _digito(numeros + primeiro, _PESOS_2)


def formatar_cnpj(cnpj: str) -> str:
    n = somente_digitos(cnpj)
    if len(n) != 14:
        return cnpj
    return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
