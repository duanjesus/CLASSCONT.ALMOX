from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from dominio.competencia import Competencia
from dominio.requisicao import Status
from estoque.models import Entrada, FechamentoCompetencia
from estoque.services import ItemNota, registrar_entrada
from requisicoes import services
from requisicoes.models import Requisicao
from tests.fabricas import SENHA, Cenario, requisicao_aprovada, requisicao_enviada

pytestmark = pytest.mark.django_db


def logado(usuario: object) -> Client:
    cliente = Client()
    cliente.force_login(usuario)  # type: ignore[arg-type]
    return cliente


# --- Acesso -------------------------------------------------------------------------


def test_login_do_painel(cenario: Cenario, client: Client) -> None:
    resposta = client.post(reverse("painel:login"), {"username": "Almox@classcont.local", "password": SENHA})
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("painel:dashboard")


def test_servidor_nao_entra_no_painel(cenario: Cenario, client: Client) -> None:
    resposta = client.post(reverse("painel:login"), {"username": "ana@classcont.local", "password": SENHA})
    assert "exclusivo do almoxarifado" in resposta.content.decode()
    assert logado(cenario.ana).get(reverse("painel:dashboard")).status_code == 403


def test_login_do_painel_tambem_limita_tentativas(cenario: Cenario, client: Client) -> None:
    for _ in range(5):
        client.post(reverse("painel:login"), {"username": "almox@classcont.local", "password": "errada"})
    resposta = client.post(reverse("painel:login"), {"username": "almox@classcont.local", "password": SENHA})
    assert "Muitas tentativas" in resposta.content.decode()


def test_anonimo_vai_para_o_login(client: Client, db: None) -> None:
    resposta = client.get(reverse("painel:material_lista"))
    assert resposta.status_code == 302
    assert resposta["Location"].startswith(reverse("painel:login"))


@pytest.mark.parametrize("rota", ["painel:setor_lista", "painel:usuario_lista", "painel:competencia_lista"])
def test_telas_do_gestor_sao_negadas_ao_almoxarife(cenario: Cenario, rota: str) -> None:
    assert logado(cenario.almox).get(reverse(rota)).status_code == 403


# --- Smoke test: todas as telas renderizam ---------------------------------------------


def test_todas_as_telas_renderizam(cenario: Cenario) -> None:
    atendida = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 5))
    services.atender(atendida.pk, cenario.almox)
    aprovada = requisicao_aprovada(cenario.bruno, cenario.chefe_sti, (cenario.toner, 1))
    aguardando = services.aprovar(requisicao_enviada(cenario.carla, (cenario.toner, 1)).pk, cenario.chefe_sof)
    entrada = Entrada.objects.first()
    assert entrada is not None

    gestor = logado(cenario.gestor)
    urls = [
        reverse("painel:dashboard"),
        reverse("painel:material_lista"),
        reverse("painel:material_lista") + "?situacao=repor&busca=papel",
        reverse("painel:material_novo"),
        reverse("painel:material_detalhe", args=[cenario.papel.pk]),
        reverse("painel:material_editar", args=[cenario.papel.pk]),
        reverse("painel:entrada_lista"),
        reverse("painel:entrada_nova"),
        reverse("painel:entrada_detalhe", args=[entrada.pk]),
        reverse("painel:requisicao_lista"),
        reverse("painel:requisicao_lista") + "?status=APROVADA",
        reverse("painel:requisicao_detalhe", args=[atendida.pk]),
        reverse("painel:requisicao_detalhe", args=[aprovada.pk]),
        reverse("painel:requisicao_detalhe", args=[aguardando.pk]),
        reverse("painel:relatorio_reposicao"),
        reverse("painel:relatorio_abc"),
        reverse("painel:relatorio_consumo"),
        reverse("painel:categoria_lista"),
        reverse("painel:categoria_novo"),
        reverse("painel:fornecedor_lista"),
        reverse("painel:fornecedor_novo"),
        reverse("painel:setor_lista"),
        reverse("painel:setor_editar", args=[cenario.sti.pk]),
        reverse("painel:usuario_lista"),
        reverse("painel:usuario_novo"),
        reverse("painel:competencia_lista"),
    ]
    for url in urls:
        assert gestor.get(url).status_code == 200, url


def test_detalhe_mostra_o_formulario_certo_para_cada_perfil(cenario: Cenario) -> None:
    aprovada = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 5))
    html = (
        logado(cenario.almox).get(reverse("painel:requisicao_detalhe", args=[aprovada.pk])).content.decode()
    )
    assert "Confirmar entrega" in html
    aguardando = services.aprovar(requisicao_enviada(cenario.carla, (cenario.toner, 1)).pk, cenario.chefe_sof)
    html = (
        logado(cenario.gestor)
        .get(reverse("painel:requisicao_detalhe", args=[aguardando.pk]))
        .content.decode()
    )
    assert "Autorizar e reservar" in html


# --- Ações ------------------------------------------------------------------------------


def test_entrada_com_formset(cenario: Cenario) -> None:
    dados = {
        "fornecedor": cenario.fornecedor.pk,
        "numero_nota": "777",
        "data_recebimento": timezone.localdate().isoformat(),
        "itens-TOTAL_FORMS": "2",
        "itens-INITIAL_FORMS": "0",
        "itens-MIN_NUM_FORMS": "1",
        "itens-MAX_NUM_FORMS": "1000",
        "itens-0-material": cenario.papel.pk,
        "itens-0-quantidade": "10",
        "itens-0-valor_unitario": "26.00",
        "itens-1-material": cenario.toner.pk,
        "itens-1-quantidade": "1",
        "itens-1-valor_unitario": "310.00",
    }
    resposta = logado(cenario.almox).post(reverse("painel:entrada_nova"), dados)
    assert resposta.status_code == 302
    cenario.recarregar()
    assert cenario.papel.quantidade_em_estoque == 60
    assert cenario.papel.custo_medio == Decimal("21.0000")
    assert Entrada.objects.get(numero_nota="777").valor_total == Decimal("570.00")


def test_formset_recusa_material_repetido(cenario: Cenario) -> None:
    dados = {
        "fornecedor": cenario.fornecedor.pk,
        "numero_nota": "778",
        "data_recebimento": timezone.localdate().isoformat(),
        "itens-TOTAL_FORMS": "2",
        "itens-INITIAL_FORMS": "0",
        **{
            f"itens-{i}-{c}": v
            for i in (0, 1)
            for c, v in [("material", cenario.papel.pk), ("quantidade", 1), ("valor_unitario", "1")]
        },
    }
    resposta = logado(cenario.almox).post(reverse("painel:entrada_nova"), dados)
    assert resposta.status_code == 200
    assert "mesmo material aparece em duas linhas" in resposta.content.decode()


def test_atender_pelo_painel(cenario: Cenario) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 5))
    item = r.itens.get()
    resposta = logado(cenario.almox).post(
        reverse("painel:requisicao_atender", args=[r.pk]), {f"item_{item.pk}": "3"}, follow=True
    )
    assert "atendida parcialmente" in resposta.content.decode()
    assert Requisicao.objects.get(pk=r.pk).status == Status.ATENDIDA_PARCIALMENTE


def test_requisicao_aprovada_sem_saldo_avisa_em_vez_de_oferecer_o_formulario(cenario: Cenario) -> None:
    requisicao_aprovada(cenario.ana, cenario.gestor, (cenario.papel, 50))  # reserva todo o papel
    sem_saldo = requisicao_aprovada(cenario.bruno, cenario.gestor, (cenario.papel, 1))
    pagina = (
        logado(cenario.almox).get(reverse("painel:requisicao_detalhe", args=[sem_saldo.pk])).content.decode()
    )
    assert "Sem saldo para atender agora" in pagina
    assert "Confirmar entrega" not in pagina


def test_formularios_do_painel_travam_o_segundo_envio(cenario: Cenario) -> None:
    pagina = logado(cenario.almox).get(reverse("painel:dashboard")).content.decode()
    assert "form.dataset.enviando" in pagina


def test_erro_de_regra_vira_mensagem_e_volta_para_a_pagina(cenario: Cenario) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 1))  # ainda não aprovada
    detalhe = reverse("painel:requisicao_detalhe", args=[r.pk])
    resposta = logado(cenario.almox).post(
        reverse("painel:requisicao_cancelar", args=[r.pk]), HTTP_REFERER=f"http://testserver{detalhe}"
    )
    # almoxarife só cancela aprovada: AcessoNegadoError → 403
    assert resposta.status_code == 403
    item = r.itens.get()
    resposta = logado(cenario.gestor).post(
        reverse("painel:requisicao_atender", args=[r.pk]),
        {f"item_{item.pk}": "0"},
        HTTP_REFERER=f"http://testserver{detalhe}",
        follow=True,
    )
    assert "Não é possível atender" in resposta.content.decode()


def test_ajuste_de_inventario_pelo_painel(cenario: Cenario) -> None:
    url = reverse("painel:material_detalhe", args=[cenario.papel.pk])
    cliente = logado(cenario.almox)
    resposta = cliente.post(url, {"quantidade_contada": "50", "justificativa": "Contagem trimestral ok"})
    assert "nenhum ajuste é necessário" in resposta.content.decode()
    assert (
        cliente.post(url, {"quantidade_contada": "48", "justificativa": "Duas resmas molhadas"}).status_code
        == 302
    )


def test_fechar_competencia_pelo_painel(cenario: Cenario) -> None:
    mes_passado = Competencia.de_data(timezone.localdate()).anterior()
    registrar_entrada(
        fornecedor=cenario.fornecedor,
        numero_nota="X1",
        data_recebimento=mes_passado.primeiro_dia,
        usuario=cenario.almox,
        itens=[ItemNota(cenario.papel.pk, 1, Decimal("20"))],
    )
    cliente = logado(cenario.gestor)
    assert mes_passado.nome in cliente.get(reverse("painel:competencia_lista")).content.decode()
    cliente.post(reverse("painel:competencia_fechar"), {"competencia": str(mes_passado)})
    assert FechamentoCompetencia.objects.filter(competencia=str(mes_passado)).exists()


def test_gestor_desativa_usuario_mas_nao_a_si_mesmo(cenario: Cenario) -> None:
    cliente = logado(cenario.gestor)
    cliente.post(reverse("painel:usuario_ativo", args=[cenario.bruno.pk]))
    cenario.bruno.refresh_from_db()
    assert cenario.bruno.is_active is False
    resposta = cliente.post(reverse("painel:usuario_ativo", args=[cenario.gestor.pk]), follow=True)
    assert "próprio acesso" in resposta.content.decode()


def test_cadastro_de_fornecedor_valida_cnpj(cenario: Cenario) -> None:
    cliente = logado(cenario.almox)
    resposta = cliente.post(
        reverse("painel:fornecedor_novo"), {"razao_social": "ACME", "cnpj": "11.111.111/1111-11"}
    )
    assert "CNPJ inválido" in resposta.content.decode()
    resposta = cliente.post(
        reverse("painel:fornecedor_novo"),
        {"razao_social": "ACME", "cnpj": "11.222.333/0001-81", "ativo": "on"},
    )
    assert resposta.status_code == 302


def test_guia_pdf_no_painel(cenario: Cenario) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 1))
    services.atender(r.pk, cenario.almox)
    resposta = logado(cenario.almox).get(reverse("painel:requisicao_guia", args=[r.pk]))
    assert resposta["Content-Type"] == "application/pdf"


def test_painel_nao_abre_rascunho(cenario: Cenario) -> None:
    rascunho = services.criar_requisicao(
        requisitante=cenario.ana, itens=[services.ItemPedido(cenario.papel.pk, 1)]
    )
    assert (
        logado(cenario.almox).get(reverse("painel:requisicao_detalhe", args=[rascunho.pk])).status_code == 404
    )


def test_gestor_nao_remove_o_proprio_perfil(cenario: Cenario) -> None:
    dados = {
        "nome": cenario.gestor.nome,
        "email": cenario.gestor.email,
        "matricula": cenario.gestor.matricula,
        "setor": cenario.gestor.setor_id,
        "perfil": "SERVIDOR",
    }
    resposta = logado(cenario.gestor).post(reverse("painel:usuario_editar", args=[cenario.gestor.pk]), dados)
    assert "próprio perfil de gestor" in resposta.content.decode()
    cenario.gestor.refresh_from_db()
    assert cenario.gestor.eh_gestor
