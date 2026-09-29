"""Arredondamentos monetários.

Dinheiro é sempre ``Decimal`` (nunca ``float``): 0.1 + 0.2 != 0.3 em ponto
flutuante. Valores em reais têm 2 casas; o custo médio unitário guarda 4 casas
para não acumular erro ao longo de muitas entradas.
"""

from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")
QUATRO_CASAS = Decimal("0.0001")
ZERO = Decimal("0")


def arredondar_moeda(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def arredondar_custo(valor: Decimal) -> Decimal:
    return valor.quantize(QUATRO_CASAS, rounding=ROUND_HALF_UP)


def valor_de(quantidade: int, custo_unitario: Decimal) -> Decimal:
    """Valor em reais de ``quantidade`` unidades a um custo unitário."""
    return arredondar_moeda(custo_unitario * quantidade)


def formatar_moeda(valor: Decimal | None) -> str:
    """``Decimal("1234.5")`` → ``"R$ 1.234,50"`` (sem depender do locale do servidor)."""
    if valor is None:
        return "—"
    texto = f"{arredondar_moeda(valor):,.2f}"  # 1,234.50
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}".replace("R$ -", "−R$ ")
