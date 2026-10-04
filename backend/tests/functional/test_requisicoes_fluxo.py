from decimal import Decimal

import pytest
from django.core import mail

from dominio.excecoes import AcessoNegadoError, RegraNegocioError, TransicaoInvalidaError
from dominio.requisicao import Status
from estoque.models import Movimentacao, TipoMovimentacao
from requisicoes import services
from requisicoes.models import Requisicao
from tests.fabricas import Cenario, requisicao_aprovada, requisicao_enviada

pytestmark = pytest.mark.django_db


# --- Criação ---------------------------------------------------------------------


def test_requisicao_nasce_rascunho_no_setor_do_servidor(cenario: Cenario) -> None:
    r = services.criar_requisicao(requisitante=cenario.ana, itens=[services.ItemPedido(cenario.papel.pk, 5)])
    assert (r.status, r.setor) == (Status.RASCUNHO, cenario.sti)
    assert r.historico.count() == 1


@pytest.mark.parametrize(
    ("itens", "mensagem"),
    [
        ([], "ao menos um"),
        ([("papel", 1), ("papel", 2)], "mais de uma vez"),
        ([("papel", 101)], "estoque máximo"),
    ],
)
def test_itens_invalidos(cenario: Cenario, itens: list[tuple[str, int]], mensagem: str) -> None:
    pedido = [services.ItemPedido(getattr(cenario, m).pk, q) for m, q in itens]
    with pytest.raises(RegraNegocioError, match=mensagem):
        services.criar_requisicao(requisitante=cenario.ana, itens=pedido)


def test_material_inativo_nao_pode_ser_pedido(cenario: Cenario) -> None:
    cenario.papel.ativo = False
    cenario.papel.save()
    with pytest.raises(RegraNegocioError, match="inativo"):
        services.criar_requisicao(requisitante=cenario.ana, itens=[services.ItemPedido(cenario.papel.pk, 1)])


def test_so_o_requisitante_envia(cenario: Cenario) -> None:
    r = services.criar_requisicao(requisitante=cenario.ana, itens=[services.ItemPedido(cenario.papel.pk, 1)])
    with pytest.raises(AcessoNegadoError):
        services.enviar(r.pk, cenario.bruno)


# --- Aprovação ------------------------------------------------------------------------


def test_chefia_aprova_e_o_saldo_fica_reservado(cenario: Cenario) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 10))
    assert r.status == Status.APROVADA
    cenario.recarregar()
    assert (cenario.papel.quantidade_em_estoque, cenario.papel.quantidade_reservada) == (50, 10)
    assert cenario.papel.disponivel == 40


def test_ninguem_avalia_a_propria_requisicao(cenario: Cenario) -> None:
    r = requisicao_enviada(cenario.chefe_sti, (cenario.papel, 1))
    with pytest.raises(AcessoNegadoError, match="ninguém avalia a própria"):
        services.aprovar(r.pk, cenario.chefe_sti)
    # a requisição do chefe sobe para o gestor
    assert r in services.pendentes_de_avaliacao(cenario.gestor)
    assert services.aprovar(r.pk, cenario.gestor).status == Status.APROVADA


@pytest.mark.parametrize("avaliador", ["bruno", "chefe_sof", "almox"])
def test_quem_nao_e_chefe_do_setor_nao_avalia(cenario: Cenario, avaliador: str) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 1))
    with pytest.raises(AcessoNegadoError):
        services.aprovar(r.pk, getattr(cenario, avaliador))


def test_pendencias_de_cada_avaliador(cenario: Cenario) -> None:
    da_ana = requisicao_enviada(cenario.ana, (cenario.papel, 1))
    do_chefe = requisicao_enviada(cenario.chefe_sti, (cenario.papel, 1))
    assert list(services.pendentes_de_avaliacao(cenario.chefe_sti)) == [da_ana]
    assert list(services.pendentes_de_avaliacao(cenario.chefe_sof)) == []
    assert do_chefe in services.pendentes_de_avaliacao(cenario.gestor)


def test_aprovacao_pode_reduzir_quantidades(cenario: Cenario) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 10))
    item = r.itens.get()
    services.aprovar(r.pk, cenario.chefe_sti, {item.pk: 4})
    item.refresh_from_db()
    assert (item.quantidade_aprovada, item.quantidade_reservada) == (4, 4)


def test_estouro_de_cota_sobe_para_o_gestor_sem_reservar(cenario: Cenario) -> None:
    # SOF tem cota de R$ 100; 1 toner custa R$ 300
    r = requisicao_enviada(cenario.carla, (cenario.toner, 1))
    r = services.aprovar(r.pk, cenario.chefe_sof)
    assert r.status == Status.AGUARDANDO_GESTOR
    assert "R$ 200,00" in r.historico.last().observacao  # type: ignore[union-attr]
    cenario.recarregar()
    assert cenario.toner.quantidade_reservada == 0

    # a chefia não autoriza o próprio estouro, e a mensagem diz de quem é a vez
    # (é o que vê quem ainda está com a tela de avaliação aberta)
    with pytest.raises(AcessoNegadoError, match="só o gestor pode autorizar"):
        services.aprovar(r.pk, cenario.chefe_sof)
    with pytest.raises(AcessoNegadoError, match="só o gestor pode autorizar"):
        services.recusar(r.pk, cenario.chefe_sof, "Mudei de ideia.")
    assert services.aprovar(r.pk, cenario.gestor).status == Status.APROVADA
    cenario.recarregar()
    assert cenario.toner.quantidade_reservada == 1


def test_cota_conta_o_que_ja_esta_comprometido(cenario: Cenario) -> None:
    # STI: cota R$ 1.000. Primeira requisição compromete R$ 900 (3 toners).
    requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.toner, 3))
    r = requisicao_enviada(cenario.bruno, (cenario.papel, 6))  # + R$ 120 → passa da cota
    assert services.aprovar(r.pk, cenario.chefe_sti).status == Status.AGUARDANDO_GESTOR


def test_recusa_exige_motivo_e_notifica(cenario: Cenario, django_capture_on_commit_callbacks) -> None:  # type: ignore[no-untyped-def]
    r = requisicao_enviada(cenario.ana, (cenario.papel, 1))
    with pytest.raises(RegraNegocioError, match="motivo"):
        services.recusar(r.pk, cenario.chefe_sti, "  ")
    with django_capture_on_commit_callbacks(execute=True):
        services.recusar(r.pk, cenario.chefe_sti, "Há papel sobrando no setor.")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ana@classcont.local"]
    assert "recusada" in mail.outbox[0].subject
    assert "Há papel sobrando" in mail.outbox[0].body


def test_nao_se_aprova_duas_vezes(cenario: Cenario) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 1))
    with pytest.raises(TransicaoInvalidaError, match="Aprovada"):
        services.aprovar(r.pk, cenario.chefe_sti)


# --- Atendimento -------------------------------------------------------------------------


def test_atendimento_baixa_estoque_consome_reserva_e_grava_o_kardex(cenario: Cenario) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 10))
    r = services.atender(r.pk, cenario.almox)
    assert r.status == Status.ATENDIDA
    assert r.valor_atendido == Decimal("200.00")
    cenario.recarregar()
    assert (cenario.papel.quantidade_em_estoque, cenario.papel.quantidade_reservada) == (40, 0)
    saida = Movimentacao.objects.get(tipo=TipoMovimentacao.SAIDA)
    assert (saida.setor, saida.requisicao_id, saida.saldo_quantidade) == (cenario.sti, r.pk, 40)


def test_atendimento_parcial_quando_falta_saldo(cenario: Cenario) -> None:
    # 4 toners em estoque; a primeira reserva 3; a segunda (autorizada pelo gestor) só consegue 1
    requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.toner, 3))
    r = requisicao_enviada(cenario.bruno, (cenario.toner, 2))
    r = services.aprovar(r.pk, cenario.gestor)
    assert r.itens.get().quantidade_reservada == 1

    r = services.atender(r.pk, cenario.almox)
    assert r.status == Status.ATENDIDA_PARCIALMENTE
    assert r.itens.get().quantidade_atendida == 1
    cenario.recarregar()
    # a reserva da outra requisição continua intacta
    assert (cenario.toner.quantidade_em_estoque, cenario.toner.quantidade_reservada) == (3, 3)


def test_almoxarife_nao_atende_a_propria_requisicao(cenario: Cenario) -> None:
    r = requisicao_enviada(cenario.almox, (cenario.papel, 1))
    services.aprovar(r.pk, cenario.gestor)
    with pytest.raises(AcessoNegadoError, match="não as próprias"):
        services.atender(r.pk, cenario.almox)
    assert services.atender(r.pk, cenario.gestor).status == Status.ATENDIDA


def test_so_se_atende_requisicao_aprovada(cenario: Cenario) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 1))
    with pytest.raises(TransicaoInvalidaError):
        services.atender(r.pk, cenario.almox)


def test_cancelar_aprovada_libera_a_reserva(cenario: Cenario) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 10))
    with pytest.raises(AcessoNegadoError):
        services.cancelar(r.pk, cenario.bruno)
    services.cancelar(r.pk, cenario.ana, "Não precisamos mais")
    cenario.recarregar()
    assert cenario.papel.quantidade_reservada == 0
    assert Requisicao.objects.get(pk=r.pk).status == Status.CANCELADA


def test_alerta_de_reposicao_apos_atendimento(cenario: Cenario, django_capture_on_commit_callbacks) -> None:  # type: ignore[no-untyped-def]
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 40))  # sobra 10 = mínimo
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.atender(r.pk, cenario.almox)
    assuntos = sorted(m.subject for m in mail.outbox)
    assert any("estoque mínimo" in a for a in assuntos)
    alerta = next(m for m in mail.outbox if "estoque mínimo" in m.subject)
    assert set(alerta.to) == {"gestor@classcont.local", "almox@classcont.local"}
    assert "Papel A4" in alerta.body
