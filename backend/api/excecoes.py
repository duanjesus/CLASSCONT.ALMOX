"""Formato único de erro da API: ``{"erro": "...", "detalhes": {"campo": "..."}}``.

- regra de negócio (``RegraNegocioError``) → 422 com a mensagem;
- permissão de perfil (``AcessoNegadoError``) → 403;
- validação de entrada (serializer) → 400 com ``detalhes`` por campo;
- qualquer outra exceção → 500 **sem** expor detalhes internos.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from dominio.excecoes import AcessoNegadoError, RegraNegocioError

logger = logging.getLogger(__name__)


def _achatar(dados: Any, prefixo: str = "") -> dict[str, str]:
    """{"itens": [{"quantidade": ["Mín. 1"]}]} → {"itens[0].quantidade": "Mín. 1"}"""
    if isinstance(dados, dict):
        resultado: dict[str, str] = {}
        for chave, valor in dados.items():
            if isinstance(chave, int):  # erros de ListSerializer vêm indexados: {0: {...}}
                caminho = f"{prefixo}[{chave}]"
            else:
                nome = chave if chave != "non_field_errors" else "geral"
                caminho = f"{prefixo}.{nome}" if prefixo else nome
            resultado.update(_achatar(valor, caminho))
        return resultado
    if isinstance(dados, list):
        if all(isinstance(v, str) for v in dados):
            return {prefixo or "geral": " ".join(str(v) for v in dados)}
        resultado = {}
        for i, valor in enumerate(dados):
            resultado.update(_achatar(valor, f"{prefixo}[{i}]"))
        return resultado
    return {prefixo or "geral": str(dados)}


def tratar_excecao(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, RegraNegocioError):
        return Response({"erro": str(exc)}, status=422)
    if isinstance(exc, AcessoNegadoError):
        return Response({"erro": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ObjectDoesNotExist):
        exc = exceptions.NotFound()

    resposta = exception_handler(exc, context)
    if resposta is None:
        if settings.DEBUG:
            return None  # deixa o Django mostrar a página de debug
        logger.exception("Erro não tratado na API", exc_info=exc)
        return Response({"erro": "Erro interno. Tente novamente mais tarde."}, status=500)

    if isinstance(exc, exceptions.ValidationError):
        resposta.data = {"erro": "Verifique os dados informados.", "detalhes": _achatar(resposta.data)}
    elif isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        mensagem = str(exc.detail) if isinstance(exc.detail, str) else "Sessão inválida. Entre novamente."
        resposta.data = {"erro": mensagem}
    elif isinstance(resposta.data, dict) and "detail" in resposta.data:
        resposta.data = {"erro": str(resposta.data["detail"])}
    return resposta
