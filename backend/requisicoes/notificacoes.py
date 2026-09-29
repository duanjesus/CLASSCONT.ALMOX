"""E-mails do fluxo de requisições (templates Django em ``templates/emails``).

Chamados via ``transaction.on_commit``. Uma falha de SMTP é registrada no log,
mas não desfaz a operação: o e-mail é um aviso, não parte da regra.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from contas.models import Perfil, Usuario
from dominio.requisicao import Status
from estoque.models import Material
from requisicoes.models import Requisicao

logger = logging.getLogger(__name__)

ASSUNTOS = {
    Status.APROVADA: "aprovada",
    Status.RECUSADA: "recusada",
    Status.ATENDIDA: "atendida: material disponível para retirada",
    Status.ATENDIDA_PARCIALMENTE: "atendida parcialmente",
    Status.CANCELADA: "cancelada",
}


def _enviar(assunto: str, destinatarios: Sequence[str], template: str, contexto: dict[str, Any]) -> None:
    if not destinatarios:
        return
    contexto = {
        **contexto,
        "url_front": settings.ALMOX["URL_FRONT"],
        "url_painel": settings.ALMOX["URL_PAINEL"],
    }
    texto = render_to_string(f"emails/{template}.txt", contexto)
    html = render_to_string(f"emails/{template}.html", contexto)
    mensagem = EmailMultiAlternatives(f"[Almoxarifado] {assunto}", texto, to=list(destinatarios))
    mensagem.attach_alternative(html, "text/html")
    try:
        mensagem.send()
    except Exception:  # SMTP fora do ar não pode derrubar o fluxo
        logger.exception("Falha ao enviar e-mail '%s'", assunto)


def _carregar(requisicao_id: int) -> Requisicao:
    return (
        Requisicao.objects.select_related("requisitante", "setor")
        .prefetch_related("itens__material", "historico__usuario")
        .get(pk=requisicao_id)
    )


def avisar_requisitante(requisicao_id: int) -> None:
    requisicao = _carregar(requisicao_id)
    status = requisicao.status_enum
    if status not in ASSUNTOS:
        return
    ultimo = list(requisicao.historico.all())[-1]
    _enviar(
        f"Requisição {requisicao.numero} {ASSUNTOS[status]}",
        [requisicao.requisitante.email],
        "requisicao_atualizada",
        {"requisicao": requisicao, "evento": ultimo},
    )


def avisar_gestores_cota(requisicao_id: int) -> None:
    requisicao = _carregar(requisicao_id)
    gestores = Usuario.objects.filter(perfil=Perfil.GESTOR, is_active=True).exclude(
        pk=requisicao.requisitante_id
    )
    _enviar(
        f"Requisição {requisicao.numero} aguarda sua autorização (cota do setor)",
        [g.email for g in gestores],
        "requisicao_atualizada",
        {"requisicao": requisicao, "evento": list(requisicao.historico.all())[-1], "para_gestor": True},
    )


def alertar_reposicao(material_ids: Sequence[int]) -> None:
    materiais = Material.objects.filter(pk__in=material_ids).order_by("descricao")
    equipe = Usuario.objects.filter(perfil__in=[Perfil.ALMOXARIFE, Perfil.GESTOR], is_active=True)
    _enviar(
        "Materiais atingiram o estoque mínimo",
        [u.email for u in equipe],
        "alerta_reposicao",
        {"materiais": materiais},
    )
