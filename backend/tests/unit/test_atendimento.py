import pytest

from dominio.atendimento import (
    ItemParaAtender,
    SaldoMaterial,
    maximo_atendivel,
    planejar_atendimento,
    quantidade_reservavel,
)
from dominio.excecoes import RegraNegocioError


def test_disponivel_desconta_reservas_e_nunca_fica_negativo() -> None:
    assert SaldoMaterial(fisico=10, reservado=4).disponivel == 6
    # inventário achou menos do que já estava reservado
    assert SaldoMaterial(fisico=2, reservado=5).disponivel == 0


def test_reserva_ate_o_disponivel() -> None:
    assert quantidade_reservavel(8, SaldoMaterial(10, 4)) == 6
    assert quantidade_reservavel(3, SaldoMaterial(10, 4)) == 3


def test_a_propria_reserva_pode_ser_entregue() -> None:
    # físico 10, reservado 10 (6 são desta requisição): pode sair até 6
    assert maximo_atendivel(aprovada=6, reservada_pela_requisicao=6, saldo=SaldoMaterial(10, 10)) == 6


def test_reserva_de_outras_requisicoes_e_respeitada() -> None:
    # aprovado 5, reservou só 2; o resto do físico está reservado para outra requisição
    assert maximo_atendivel(aprovada=5, reservada_pela_requisicao=2, saldo=SaldoMaterial(6, 6)) == 2


def test_material_que_chegou_depois_da_aprovacao_pode_completar_o_pedido() -> None:
    # reservou 2 na aprovação; depois entraram mais 10 livres
    assert maximo_atendivel(aprovada=5, reservada_pela_requisicao=2, saldo=SaldoMaterial(12, 2)) == 5


def _item(
    chave: int, aprovada: int, reservada: int, fisico: int, informada: int | None = None
) -> ItemParaAtender:
    return ItemParaAtender(
        chave, f"Item {chave}", aprovada, reservada, SaldoMaterial(fisico, reservada), informada
    )


def test_atendimento_total() -> None:
    plano = planejar_atendimento([_item(1, 5, 5, 10), _item(2, 2, 2, 2)])
    assert plano.quantidades == {1: 5, 2: 2}
    assert plano.parcial is False


def test_atendimento_parcial_por_falta_de_saldo() -> None:
    plano = planejar_atendimento([_item(1, 5, 3, 3), _item(2, 2, 2, 2)])
    assert plano.quantidades == {1: 3, 2: 2}
    assert plano.parcial is True


def test_almoxarife_pode_entregar_menos_que_o_maximo() -> None:
    plano = planejar_atendimento([_item(1, 5, 5, 10, informada=4)])
    assert plano.quantidades == {1: 4}
    assert plano.parcial is True


def test_nao_entrega_acima_do_maximo() -> None:
    with pytest.raises(RegraNegocioError, match="no máximo 5"):
        planejar_atendimento([_item(1, 5, 5, 10, informada=6)])


def test_sem_saldo_para_nenhum_item() -> None:
    with pytest.raises(RegraNegocioError, match="Não há saldo"):
        planejar_atendimento([_item(1, 5, 0, 0)])
