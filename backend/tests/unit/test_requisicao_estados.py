import pytest

from dominio.excecoes import RegraNegocioError, TransicaoInvalidaError
from dominio.requisicao import (
    STATUS_FINAIS,
    Acao,
    Status,
    acoes_possiveis,
    transicionar,
    validar_quantidades_aprovadas,
)


@pytest.mark.parametrize(
    ("de", "acao", "para"),
    [
        (Status.RASCUNHO, Acao.ENVIAR, Status.ENVIADA),
        (Status.ENVIADA, Acao.APROVAR, Status.APROVADA),
        (Status.ENVIADA, Acao.ENCAMINHAR_GESTOR, Status.AGUARDANDO_GESTOR),
        (Status.ENVIADA, Acao.RECUSAR, Status.RECUSADA),
        (Status.AGUARDANDO_GESTOR, Acao.APROVAR, Status.APROVADA),
        (Status.APROVADA, Acao.ATENDER, Status.ATENDIDA),
        (Status.APROVADA, Acao.ATENDER_PARCIALMENTE, Status.ATENDIDA_PARCIALMENTE),
        (Status.APROVADA, Acao.CANCELAR, Status.CANCELADA),
    ],
)
def test_transicoes_validas(de: Status, acao: Acao, para: Status) -> None:
    assert transicionar(de, acao) == para


@pytest.mark.parametrize(
    ("de", "acao"),
    [
        (Status.RASCUNHO, Acao.APROVAR),  # precisa ser enviada antes
        (Status.ENVIADA, Acao.ATENDER),  # precisa ser aprovada antes
        (Status.AGUARDANDO_GESTOR, Acao.ENCAMINHAR_GESTOR),
        (Status.ATENDIDA, Acao.CANCELAR),  # material já entregue
        (Status.RECUSADA, Acao.APROVAR),
    ],
)
def test_transicoes_invalidas(de: Status, acao: Acao) -> None:
    with pytest.raises(TransicaoInvalidaError, match=de.rotulo):
        transicionar(de, acao)


def test_status_finais_nao_tem_acoes() -> None:
    assert (
        frozenset({Status.RECUSADA, Status.ATENDIDA, Status.ATENDIDA_PARCIALMENTE, Status.CANCELADA})
        == STATUS_FINAIS
    )
    for status in STATUS_FINAIS:
        assert acoes_possiveis(status) == frozenset()


def test_aprovador_pode_reduzir_e_itens_omitidos_mantem_o_pedido() -> None:
    assert validar_quantidades_aprovadas({1: 10, 2: 5}, {1: 4}) == {1: 4, 2: 5}


def test_aprovador_pode_zerar_um_item_mas_nao_todos() -> None:
    assert validar_quantidades_aprovadas({1: 10, 2: 5}, {2: 0}) == {1: 10, 2: 0}
    with pytest.raises(RegraNegocioError, match="recuse"):
        validar_quantidades_aprovadas({1: 10, 2: 5}, {1: 0, 2: 0})


@pytest.mark.parametrize(
    ("informadas", "mensagem"), [({1: 11}, "excede"), ({1: -1}, "negativa"), ({9: 1}, "não pertencem")]
)
def test_quantidades_aprovadas_invalidas(informadas: dict[int, int], mensagem: str) -> None:
    with pytest.raises(RegraNegocioError, match=mensagem):
        validar_quantidades_aprovadas({1: 10}, informadas)
