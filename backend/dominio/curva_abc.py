"""Curva ABC (princípio de Pareto) do consumo de materiais.

Ordena os materiais pelo valor consumido e classifica pelo percentual acumulado:
- **A**: os que somam os primeiros 80% do valor (poucos itens, muito dinheiro);
- **B**: até 95%;
- **C**: o restante (muitos itens, pouco dinheiro).

Um item entra numa classe pelo acumulado *antes* dele: assim o maior item é
sempre A, mesmo que sozinho represente mais de 80%.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from dominio.dinheiro import ZERO

Classe = Literal["A", "B", "C"]


@dataclass(frozen=True, slots=True)
class ItemConsumo:
    chave: int
    descricao: str
    valor: Decimal


@dataclass(frozen=True, slots=True)
class ItemClassificado:
    item: ItemConsumo
    classe: Classe
    percentual: Decimal
    percentual_acumulado: Decimal


def classificar(
    itens: Iterable[ItemConsumo],
    limite_a: Decimal = Decimal(80),
    limite_b: Decimal = Decimal(95),
) -> list[ItemClassificado]:
    positivos = sorted((i for i in itens if i.valor > 0), key=lambda i: (-i.valor, i.descricao))
    total = sum((i.valor for i in positivos), ZERO)
    if total == 0:
        return []

    resultado: list[ItemClassificado] = []
    acumulado = ZERO
    for item in positivos:
        percentual = item.valor * 100 / total
        classe: Classe = "A" if acumulado < limite_a else "B" if acumulado < limite_b else "C"
        acumulado += percentual
        resultado.append(ItemClassificado(item, classe, percentual, acumulado))
    return resultado
