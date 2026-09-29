"""Quem pode fazer o quê com uma requisição.

São funções puras sobre (usuário, requisição), usadas pela API (permissões do
DRF), pelo painel e pelos serviços (defesa em profundidade). É o equivalente
aos *Voters* do Symfony.
"""

from __future__ import annotations

from contas.models import Usuario
from dominio.requisicao import STATUS_EM_AVALIACAO, Acao, Status, acoes_possiveis
from requisicoes.models import Requisicao


def eh_requisitante(usuario: Usuario, requisicao: Requisicao) -> bool:
    return requisicao.requisitante_id == usuario.pk


def pode_ver(usuario: Usuario, requisicao: Requisicao) -> bool:
    return (
        eh_requisitante(usuario, requisicao)
        or usuario.acessa_painel
        or usuario.chefia_setor(requisicao.setor_id)
    )


def pode_editar(usuario: Usuario, requisicao: Requisicao) -> bool:
    return eh_requisitante(usuario, requisicao) and requisicao.status_enum == Status.RASCUNHO


def pode_enviar(usuario: Usuario, requisicao: Requisicao) -> bool:
    return pode_editar(usuario, requisicao)


def pode_avaliar(usuario: Usuario, requisicao: Requisicao) -> bool:
    """Aprovar/recusar. **Ninguém avalia a própria requisição.**

    - ENVIADA: chefe do setor da requisição, ou o gestor;
    - AGUARDANDO_GESTOR (estourou a cota): somente o gestor.
    """
    status = requisicao.status_enum
    if status not in STATUS_EM_AVALIACAO or eh_requisitante(usuario, requisicao):
        return False
    if usuario.eh_gestor:
        return True
    return status == Status.ENVIADA and usuario.chefia_setor(requisicao.setor_id)


def pode_atender(usuario: Usuario, requisicao: Requisicao) -> bool:
    """Segregação de funções: o almoxarife não entrega material para si mesmo."""
    return (
        usuario.acessa_painel
        and requisicao.status_enum == Status.APROVADA
        and not eh_requisitante(usuario, requisicao)
    )


def pode_cancelar(usuario: Usuario, requisicao: Requisicao) -> bool:
    status = requisicao.status_enum
    if Acao.CANCELAR not in acoes_possiveis(status):
        return False
    if eh_requisitante(usuario, requisicao):
        return True
    # Aprovada e parada no almoxarifado (ex.: material que não chegou): o almoxarifado pode cancelar
    return status == Status.APROVADA and usuario.acessa_painel


def pode_baixar_guia(usuario: Usuario, requisicao: Requisicao) -> bool:
    return pode_ver(usuario, requisicao) and requisicao.status_enum in (
        Status.ATENDIDA,
        Status.ATENDIDA_PARCIALMENTE,
    )


def acoes_do_usuario(usuario: Usuario, requisicao: Requisicao) -> list[str]:
    """O que a interface deve oferecer a este usuário (o back continua validando tudo)."""
    regras = {
        "editar": pode_editar,
        "enviar": pode_enviar,
        "cancelar": pode_cancelar,
        "aprovar": pode_avaliar,
        "recusar": pode_avaliar,
        "atender": pode_atender,
        "guia_pdf": pode_baixar_guia,
    }
    return [acao for acao, regra in regras.items() if regra(usuario, requisicao)]
