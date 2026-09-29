"""Competência (mês de referência) e regras de fechamento mensal."""

from __future__ import annotations

import calendar
import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from dominio.excecoes import CompetenciaFechadaError, CompetenciaInvalidaError, RegraNegocioError

MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip

_FORMATO = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True, order=True, slots=True)
class Competencia:
    """Value object: imutável, comparável e com igualdade por valor."""

    ano: int
    mes: int

    def __post_init__(self) -> None:
        if not 1 <= self.mes <= 12:
            raise CompetenciaInvalidaError(f"Mês inválido: {self.mes}.")
        if not 2000 <= self.ano <= 2100:
            raise CompetenciaInvalidaError(f"Ano inválido: {self.ano}.")

    @classmethod
    def de_texto(cls, texto: str) -> Competencia:
        """``"2026-09"`` → ``Competencia(2026, 9)``."""
        casamento = _FORMATO.match(texto.strip())
        if not casamento:
            raise CompetenciaInvalidaError("Competência inválida: use o formato AAAA-MM.")
        return cls(int(casamento.group(1)), int(casamento.group(2)))

    @classmethod
    def de_data(cls, dia: date) -> Competencia:
        return cls(dia.year, dia.month)

    @property
    def primeiro_dia(self) -> date:
        return date(self.ano, self.mes, 1)

    @property
    def ultimo_dia(self) -> date:
        return date(self.ano, self.mes, calendar.monthrange(self.ano, self.mes)[1])

    @property
    def nome(self) -> str:
        return f"{MESES[self.mes - 1]} de {self.ano}"

    def anterior(self) -> Competencia:
        return Competencia(self.ano - 1, 12) if self.mes == 1 else Competencia(self.ano, self.mes - 1)

    def proxima(self) -> Competencia:
        return Competencia(self.ano + 1, 1) if self.mes == 12 else Competencia(self.ano, self.mes + 1)

    def contem(self, dia: date) -> bool:
        return (dia.year, dia.month) == (self.ano, self.mes)

    def __str__(self) -> str:
        return f"{self.ano:04d}-{self.mes:02d}"


def validar_lancamento(dia: date, fechadas: Collection[Competencia]) -> None:
    """Movimentações não podem cair numa competência já fechada."""
    competencia = Competencia.de_data(dia)
    if competencia in fechadas:
        raise CompetenciaFechadaError(
            f"A competência {competencia.nome} está fechada: não aceita novas movimentações."
        )


def validar_fechamento(
    alvo: Competencia,
    hoje: date,
    fechadas: Collection[Competencia],
    primeira_com_movimento: Competencia | None,
) -> None:
    """Regras para fechar um mês.

    - só fecha mês já encerrado (nem o corrente, nem futuro);
    - não fecha duas vezes;
    - fecha em ordem: se o mês anterior teve movimento, ele precisa estar fechado.
    """
    if alvo in fechadas:
        raise RegraNegocioError(f"A competência {alvo.nome} já está fechada.")
    if alvo >= Competencia.de_data(hoje):
        raise RegraNegocioError("Só é possível fechar competências já encerradas.")
    anterior = alvo.anterior()
    if primeira_com_movimento is not None and anterior >= primeira_com_movimento and anterior not in fechadas:
        raise RegraNegocioError(f"Feche antes a competência de {anterior.nome}.")
