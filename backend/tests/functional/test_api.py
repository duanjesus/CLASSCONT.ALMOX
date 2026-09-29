from typing import Any

import pytest
from rest_framework.test import APIClient

from contas.models import Usuario
from dominio.requisicao import Status
from requisicoes import services
from tests.fabricas import SENHA, Cenario, requisicao_aprovada, requisicao_enviada

pytestmark = pytest.mark.django_db


def entrar(api: APIClient, usuario: Usuario) -> APIClient:
    api.force_authenticate(usuario)
    return api


# --- Autenticação ------------------------------------------------------------------


def test_login_devolve_tokens_jwt_e_ignora_maiusculas_no_email(cenario: Cenario, api: APIClient) -> None:
    resposta = api.post("/api/auth/login", {"email": "ANA@classcont.local", "password": SENHA}, format="json")
    assert resposta.status_code == 200
    assert {"access", "refresh"} <= set(resposta.json())


def test_login_errado(cenario: Cenario, api: APIClient) -> None:
    resposta = api.post("/api/auth/login", {"email": "ana@classcont.local", "password": "x"}, format="json")
    assert resposta.status_code == 401
    assert resposta.json() == {"erro": "E-mail ou senha inválidos."}


def test_forca_bruta_bloqueia_mesmo_com_a_senha_certa(cenario: Cenario, api: APIClient) -> None:
    for _ in range(5):
        api.post("/api/auth/login", {"email": "ana@classcont.local", "password": "errada"}, format="json")
    resposta = api.post("/api/auth/login", {"email": "ana@classcont.local", "password": SENHA}, format="json")
    assert resposta.status_code == 429


def test_usuario_desativado_perde_o_acesso_mesmo_com_token_valido(cenario: Cenario, api: APIClient) -> None:
    token = api.post(
        "/api/auth/login", {"email": "ana@classcont.local", "password": SENHA}, format="json"
    ).json()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token['access']}")
    assert api.get("/api/me").status_code == 200

    cenario.ana.is_active = False
    cenario.ana.save()
    assert api.get("/api/me").status_code == 401


def test_sem_token(api: APIClient, db: None) -> None:
    resposta = api.get("/api/me")
    assert resposta.status_code == 401
    assert "erro" in resposta.json()


def test_me_deriva_a_chefia_do_cadastro_de_setores(cenario: Cenario, api: APIClient) -> None:
    dados = entrar(api, cenario.chefe_sti).get("/api/me").json()
    assert dados["papeis"] == ["SERVIDOR", "CHEFIA"]
    assert dados["setores_chefiados"][0]["sigla"] == "STI"
    assert entrar(APIClient(), cenario.ana).get("/api/me").json()["papeis"] == ["SERVIDOR"]


# --- Catálogo ----------------------------------------------------------------------


def test_catalogo_com_busca_e_disponivel(cenario: Cenario, api: APIClient) -> None:
    requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 10))
    dados = entrar(api, cenario.bruno).get("/api/materiais", {"busca": "papel"}).json()
    assert [(m["codigo"], m["disponivel"]) for m in dados] == [("EXP-001", 40)]


# --- Requisições --------------------------------------------------------------------


def criar(api: APIClient, itens: list[dict[str, Any]]) -> Any:
    return api.post("/api/requisicoes", {"finalidade": "Teste", "itens": itens}, format="json")


def test_criar_editar_e_enviar(cenario: Cenario, api: APIClient) -> None:
    entrar(api, cenario.ana)
    resposta = criar(api, [{"material_id": cenario.papel.pk, "quantidade": 3}])
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["status"] == Status.RASCUNHO
    assert set(dados["acoes"]) == {"editar", "enviar", "cancelar"}

    url = f"/api/requisicoes/{dados['id']}"
    itens = [{"material_id": cenario.toner.pk, "quantidade": 1}]
    assert api.put(url, {"itens": itens}, format="json").json()["itens"][0]["material"]["codigo"] == "INF-001"

    enviada = api.post(f"{url}/enviar").json()
    assert enviada["status"] == Status.ENVIADA
    assert enviada["acoes"] == ["cancelar"]
    assert api.put(url, {"itens": itens}, format="json").status_code == 403  # não é mais rascunho


def test_erro_de_validacao_aponta_o_campo(cenario: Cenario, api: APIClient) -> None:
    resposta = criar(entrar(api, cenario.ana), [{"material_id": cenario.papel.pk, "quantidade": 0}])
    assert resposta.status_code == 400
    assert "itens[0].quantidade" in resposta.json()["detalhes"]


def test_regra_de_negocio_vira_422(cenario: Cenario, api: APIClient) -> None:
    resposta = criar(entrar(api, cenario.ana), [{"material_id": cenario.papel.pk, "quantidade": 500}])
    assert resposta.status_code == 422
    assert "estoque máximo" in resposta.json()["erro"]


@pytest.mark.parametrize(
    ("quem", "codigo"), [("ana", 200), ("chefe_sti", 200), ("almox", 200), ("bruno", 403), ("chefe_sof", 403)]
)
def test_quem_ve_uma_requisicao(cenario: Cenario, api: APIClient, quem: str, codigo: int) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 1))
    assert entrar(api, getattr(cenario, quem)).get(f"/api/requisicoes/{r.pk}").status_code == codigo


def test_fluxo_de_aprovacao_pela_api(cenario: Cenario, api: APIClient) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 10))
    entrar(api, cenario.chefe_sti)
    pendentes = api.get("/api/requisicoes", {"escopo": "pendentes"}).json()
    assert [p["id"] for p in pendentes["results"]] == [r.pk]
    assert api.get("/api/resumo").json()["pendentes_avaliacao"] == 1

    item = r.itens.get()
    dados = api.post(
        f"/api/requisicoes/{r.pk}/aprovar", {"itens": [{"id": item.pk, "quantidade": 6}]}, format="json"
    ).json()
    assert dados["status"] == Status.APROVADA
    assert dados["itens"][0]["quantidade_aprovada"] == 6
    assert [h["para_status"] for h in dados["historico"]] == ["RASCUNHO", "ENVIADA", "APROVADA"]


def test_colega_nao_aprova(cenario: Cenario, api: APIClient) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 1))
    resposta = entrar(api, cenario.bruno).post(f"/api/requisicoes/{r.pk}/aprovar", {}, format="json")
    assert resposta.status_code == 403


def test_recusar_sem_motivo(cenario: Cenario, api: APIClient) -> None:
    r = requisicao_enviada(cenario.ana, (cenario.papel, 1))
    resposta = entrar(api, cenario.chefe_sti).post(
        f"/api/requisicoes/{r.pk}/recusar", {"motivo": ""}, format="json"
    )
    assert resposta.status_code == 400
    assert "motivo" in resposta.json()["detalhes"]


def test_guia_de_saida_em_pdf(cenario: Cenario, api: APIClient) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 2))
    entrar(api, cenario.ana)
    assert api.get(f"/api/requisicoes/{r.pk}/guia").status_code == 422  # ainda não atendida
    services.atender(r.pk, cenario.almox)
    resposta = api.get(f"/api/requisicoes/{r.pk}/guia")
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")


def test_consumo_do_setor_para_a_chefia(cenario: Cenario, api: APIClient) -> None:
    r = requisicao_aprovada(cenario.ana, cenario.chefe_sti, (cenario.papel, 5))
    services.atender(r.pk, cenario.almox)
    dados = entrar(api, cenario.chefe_sti).get(f"/api/setores/{cenario.sti.pk}/consumo").json()
    assert dados["cota"]["consumido"] == "100.00"
    assert dados["materiais"][0]["codigo"] == "EXP-001"
    assert entrar(APIClient(), cenario.ana).get(f"/api/setores/{cenario.sti.pk}/consumo").status_code == 403


def test_documentacao_openapi(db: None, api: APIClient) -> None:
    assert api.get("/api/schema").status_code == 200
