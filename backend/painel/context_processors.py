from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from contas.models import Usuario
from dominio.requisicao import Status
from requisicoes.models import Requisicao


def painel(request: HttpRequest) -> dict[str, Any]:
    """Contadores do menu lateral do painel (somente nas páginas do painel)."""
    usuario = getattr(request, "user", None)
    if (
        not request.path.startswith("/painel/")
        or not isinstance(usuario, Usuario)
        or not usuario.acessa_painel
    ):
        return {}
    return {
        "menu_fila_atendimento": Requisicao.objects.filter(status=Status.APROVADA).count(),
        "menu_aguardando_gestor": (
            Requisicao.objects.filter(status=Status.AGUARDANDO_GESTOR).count() if usuario.eh_gestor else 0
        ),
    }
