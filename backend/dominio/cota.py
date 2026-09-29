"""Cota mensal de consumo por setor (em reais)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from dominio.dinheiro import ZERO, arredondar_moeda


@dataclass(frozen=True, slots=True)
class SituacaoCota:
    """``cota`` None = setor sem limite.

    - consumido: saídas já entregues ao setor no mês;
    - comprometido: requisições aprovadas e ainda não atendidas (valor estimado).
    """

    cota: Decimal | None
    consumido: Decimal = ZERO
    comprometido: Decimal = ZERO

    @property
    def utilizado(self) -> Decimal:
        return self.consumido + self.comprometido

    @property
    def disponivel(self) -> Decimal | None:
        return None if self.cota is None else self.cota - self.utilizado

    @property
    def percentual_utilizado(self) -> Decimal | None:
        if self.cota is None or self.cota == 0:
            return None
        return arredondar_moeda(self.utilizado * 100 / self.cota)

    def comporta(self, valor: Decimal) -> bool:
        return self.cota is None or self.utilizado + valor <= self.cota

    def excedente(self, valor: Decimal) -> Decimal:
        if self.cota is None:
            return ZERO
        return max(ZERO, self.utilizado + valor - self.cota)
