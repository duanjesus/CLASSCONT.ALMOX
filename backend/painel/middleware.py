"""Converte erros do domínio em respostas do painel (padrão Post/Redirect/Get).

As views de ação (aprovar, atender, fechar mês...) só chamam o serviço. Se ele
levantar ``RegraNegocioError``, a mensagem vira um *flash* e o usuário volta
para a página de onde veio. ``AcessoNegadoError`` vira 403.
"""

from __future__ import annotations

from collections.abc import Callable

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme

from dominio.excecoes import AcessoNegadoError, RegraNegocioError


class ErrosDeDominioMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exc: Exception) -> HttpResponse | None:
        if not request.path.startswith("/painel/"):
            return None
        if isinstance(exc, AcessoNegadoError):
            raise PermissionDenied(str(exc))
        if isinstance(exc, RegraNegocioError):
            messages.error(request, str(exc))
            destino = request.META.get("HTTP_REFERER", "")
            if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
                destino = "/painel/"
            return HttpResponseRedirect(destino)
        return None
