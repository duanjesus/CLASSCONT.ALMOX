"""Reserva de saldo e atendimento (total ou parcial) de requisições.

Conceitos:
- **físico**: o que está na prateleira;
- **reservado**: o que já foi prometido a requisições aprovadas e ainda não entregues;
- **disponível** = físico − reservado: o que uma nova aprovação pode reservar.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from dominio.excecoes import RegraNegocioError


@dataclass(frozen=True, slots=True)
class SaldoMaterial:
    fisico: int
    reservado: int

    @property
    def disponivel(self) -> int:
        # Após um inventário que encontrou menos que o reservado, o físico pode ficar abaixo da reserva
        return max(0, self.fisico - self.reservado)


def quantidade_reservavel(aprovada: int, saldo: SaldoMaterial) -> int:
    """Na aprovação, reserva-se o que houver disponível, até a quantidade aprovada."""
    return max(0, min(aprovada, saldo.disponivel))


def maximo_atendivel(aprovada: int, reservada_pela_requisicao: int, saldo: SaldoMaterial) -> int:
    """Quanto desta requisição pode sair agora.

    A reserva da própria requisição é dela: descontamos do físico só as reservas
    das *outras* requisições. Se chegou material depois da aprovação, o que estiver
    livre também pode ser usado.
    """
    reservado_por_outras = max(0, saldo.reservado - reservada_pela_requisicao)
    livre = saldo.fisico - reservado_por_outras
    return max(0, min(aprovada, livre))


@dataclass(frozen=True, slots=True)
class ItemParaAtender:
    chave: int
    descricao: str
    aprovada: int
    reservada: int
    saldo: SaldoMaterial
    informada: int | None = None  # None → atender o máximo possível


@dataclass(frozen=True, slots=True)
class PlanoAtendimento:
    quantidades: dict[int, int]
    parcial: bool


def planejar_atendimento(itens: Sequence[ItemParaAtender]) -> PlanoAtendimento:
    if not itens:
        raise RegraNegocioError("A requisição não tem itens.")

    quantidades: dict[int, int] = {}
    for item in itens:
        maximo = maximo_atendivel(item.aprovada, item.reservada, item.saldo)
        quantidade = maximo if item.informada is None else item.informada
        if quantidade < 0:
            raise RegraNegocioError(f"{item.descricao}: a quantidade não pode ser negativa.")
        if quantidade > maximo:
            raise RegraNegocioError(
                f"{item.descricao}: é possível entregar no máximo {maximo} "
                f"(pedido aprovado: {item.aprovada})."
            )
        quantidades[item.chave] = quantidade

    if not any(quantidades.values()):
        raise RegraNegocioError("Não há saldo para atender nenhum item desta requisição.")

    parcial = any(quantidades[i.chave] < i.aprovada for i in itens)
    return PlanoAtendimento(quantidades, parcial)
