"""Custo médio ponderado móvel, o método de valoração de estoque do setor público.

Toda entrada recalcula o custo médio::

    novo_custo = (qtd_atual × custo_atual + qtd_entrada × custo_entrada) / (qtd_atual + qtd_entrada)

As saídas são valoradas pelo custo médio do momento e **não** alteram o custo.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from dominio.dinheiro import ZERO, arredondar_custo, valor_de
from dominio.excecoes import RegraNegocioError, SaldoInsuficienteError


@dataclass(frozen=True, slots=True)
class PosicaoEstoque:
    """Quantidade física e custo médio unitário de um material."""

    quantidade: int
    custo_medio: Decimal = ZERO

    def __post_init__(self) -> None:
        if self.quantidade < 0:
            raise ValueError("A quantidade em estoque não pode ser negativa.")
        if self.custo_medio < 0:
            raise ValueError("O custo médio não pode ser negativo.")

    @property
    def valor_total(self) -> Decimal:
        return valor_de(self.quantidade, self.custo_medio)

    def com_entrada(self, quantidade: int, custo_unitario: Decimal) -> PosicaoEstoque:
        if quantidade <= 0:
            raise RegraNegocioError("A quantidade de entrada deve ser maior que zero.")
        if custo_unitario < 0:
            raise RegraNegocioError("O valor unitário não pode ser negativo.")
        nova_quantidade = self.quantidade + quantidade
        valor_acumulado = self.custo_medio * self.quantidade + custo_unitario * quantidade
        return PosicaoEstoque(nova_quantidade, arredondar_custo(valor_acumulado / nova_quantidade))

    def com_saida(self, quantidade: int) -> PosicaoEstoque:
        if quantidade <= 0:
            raise RegraNegocioError("A quantidade de saída deve ser maior que zero.")
        if quantidade > self.quantidade:
            raise SaldoInsuficienteError(
                f"Saldo insuficiente: há {self.quantidade} em estoque e a saída pede {quantidade}."
            )
        # Mesmo zerando o estoque, o último custo médio é mantido (serve de referência)
        return PosicaoEstoque(self.quantidade - quantidade, self.custo_medio)

    def valor_saida(self, quantidade: int) -> Decimal:
        return valor_de(quantidade, self.custo_medio)
