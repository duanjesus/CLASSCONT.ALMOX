from decimal import Decimal

import pytest

from dominio.custo_medio import PosicaoEstoque
from dominio.excecoes import RegraNegocioError, SaldoInsuficienteError


def test_entrada_recalcula_custo_medio_ponderado() -> None:
    # 10 a R$ 20 + 30 a R$ 24 = (200 + 720) / 40 = R$ 23
    posicao = PosicaoEstoque(10, Decimal("20")).com_entrada(30, Decimal("24"))
    assert posicao == PosicaoEstoque(40, Decimal("23.0000"))


def test_primeira_entrada_usa_o_custo_da_nota() -> None:
    assert PosicaoEstoque(0).com_entrada(5, Decimal("7.35")).custo_medio == Decimal("7.35")


def test_custo_medio_guarda_quatro_casas() -> None:
    # (1 × 1 + 2 × 2) / 3 = 1,6666... → 1,6667
    assert PosicaoEstoque(1, Decimal("1")).com_entrada(2, Decimal("2")).custo_medio == Decimal("1.6667")


def test_saida_nao_altera_o_custo_medio() -> None:
    posicao = PosicaoEstoque(10, Decimal("23")).com_saida(4)
    assert posicao == PosicaoEstoque(6, Decimal("23"))


def test_zerar_o_estoque_mantem_o_ultimo_custo_como_referencia() -> None:
    assert PosicaoEstoque(3, Decimal("9.9")).com_saida(3) == PosicaoEstoque(0, Decimal("9.9"))


def test_saida_acima_do_saldo_e_recusada() -> None:
    with pytest.raises(SaldoInsuficienteError, match="há 2 em estoque"):
        PosicaoEstoque(2, Decimal("1")).com_saida(3)


@pytest.mark.parametrize("quantidade", [0, -1])
def test_quantidades_invalidas(quantidade: int) -> None:
    with pytest.raises(RegraNegocioError):
        PosicaoEstoque(5).com_entrada(quantidade, Decimal("1"))
    with pytest.raises(RegraNegocioError):
        PosicaoEstoque(5).com_saida(quantidade)


def test_valor_de_saida_e_total_sao_arredondados_ao_centavo() -> None:
    posicao = PosicaoEstoque(3, Decimal("1.6667"))
    assert posicao.valor_total == Decimal("5.00")
    assert posicao.valor_saida(2) == Decimal("3.33")


def test_posicao_negativa_nao_existe() -> None:
    with pytest.raises(ValueError, match="negativa"):
        PosicaoEstoque(-1)
