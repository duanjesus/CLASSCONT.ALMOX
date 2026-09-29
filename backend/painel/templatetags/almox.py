"""Filtros e tags próprios dos templates (``{% load almox %}``).

- ``@register.filter``: transforma um valor (``{{ valor|moeda }}``);
- ``@register.simple_tag``: devolve um valor calculado (``{% url_front '/x' %}``);
- ``@register.inclusion_tag``: renderiza um pedaço de template com contexto
  próprio (``{% badge_status r.status %}``), o equivalente às macros do Twig.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django import template
from django.conf import settings
from django.urls import reverse

from dominio.cnpj import formatar_cnpj
from dominio.competencia import Competencia
from dominio.dinheiro import formatar_moeda
from dominio.excecoes import RegraNegocioError
from dominio.requisicao import Status

register = template.Library()

CORES_STATUS = {
    Status.RASCUNHO: "bg-slate-100 text-slate-600 ring-slate-500/20",
    Status.ENVIADA: "bg-amber-50 text-amber-700 ring-amber-600/20",
    Status.AGUARDANDO_GESTOR: "bg-orange-50 text-orange-700 ring-orange-600/20",
    Status.APROVADA: "bg-sky-50 text-sky-700 ring-sky-600/20",
    Status.RECUSADA: "bg-red-50 text-red-700 ring-red-600/20",
    Status.ATENDIDA: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    Status.ATENDIDA_PARCIALMENTE: "bg-teal-50 text-teal-700 ring-teal-600/20",
    Status.CANCELADA: "bg-slate-100 text-slate-500 ring-slate-500/20",
}

CORES_ABC = {
    "A": "bg-red-50 text-red-700 ring-red-600/20",
    "B": "bg-amber-50 text-amber-700 ring-amber-600/20",
    "C": "bg-slate-100 text-slate-600 ring-slate-500/20",
}


@register.filter
def moeda(valor: Any) -> str:
    """``{{ 1234.5|moeda }}`` → ``R$ 1.234,50``"""
    if valor in (None, ""):
        return "—"
    try:
        return formatar_moeda(Decimal(str(valor)))
    except InvalidOperation:
        return str(valor)


@register.filter
def numero(valor: Any) -> str:
    """Inteiro com separador de milhar: ``{{ 12500|numero }}`` → ``12.500``"""
    if valor in (None, ""):
        return "—"
    return f"{int(valor):,}".replace(",", ".")


@register.filter
def percentual(valor: Any, casas: int = 1) -> str:
    if valor in (None, ""):
        return "—"
    return f"{Decimal(str(valor)):.{casas}f}%".replace(".", ",")


@register.filter
def competencia(texto: str) -> str:
    """``{{ "2026-09"|competencia }}`` → ``setembro de 2026``"""
    try:
        return Competencia.de_texto(str(texto)).nome
    except RegraNegocioError:
        return str(texto)


@register.filter
def cnpj(valor: str) -> str:
    return formatar_cnpj(valor)


@register.filter
def atributo(objeto: Any, nome: str) -> Any:
    """Lê um atributo pelo nome, preferindo o rótulo de choices (``get_<campo>_display``)."""
    exibicao = getattr(objeto, f"get_{nome}_display", None)
    if callable(exibicao):
        return exibicao()
    valor = getattr(objeto, nome, "")
    return valor() if callable(valor) else valor


@register.simple_tag
def url_front(caminho: str = "") -> str:
    return f"{settings.ALMOX['URL_FRONT']}{caminho}"


@register.inclusion_tag("painel/tags/badge_status.html")
def badge_status(status: str) -> dict[str, str]:
    st = Status(status)
    return {"rotulo": st.rotulo, "classes": CORES_STATUS[st]}


@register.inclusion_tag("painel/tags/badge.html")
def badge_abc(classe: str) -> dict[str, str]:
    return {"rotulo": classe, "classes": CORES_ABC.get(classe, CORES_ABC["C"])}


@register.inclusion_tag("painel/tags/cabecalho.html")
def cabecalho(titulo: str, subtitulo: str = "") -> dict[str, str]:
    return {"titulo": titulo, "subtitulo": subtitulo}


@register.inclusion_tag("painel/tags/botao_post.html", takes_context=True)
def botao_post(
    context: template.Context, url: str, rotulo: str, confirmar: str = "", estilo: str = "secundario"
) -> dict[str, Any]:
    """Botão que faz POST com token CSRF (ações que mudam estado nunca são GET)."""
    return {
        "url": url,
        "rotulo": rotulo,
        "confirmar": confirmar,
        "estilo": estilo,
        # inclusion_tag tem contexto isolado: o token precisa ser repassado
        "csrf_token": context.get("csrf_token"),
    }


@register.inclusion_tag("painel/tags/link_menu.html", takes_context=True)
def link_menu(
    context: template.Context, rota: str, rotulo: str, icone: str, badge: int = 0, query: str | None = None
) -> dict[str, Any]:
    """Item do menu lateral. Fica ativo quando a página atual é da mesma "família" de rotas
    (``painel:material_lista`` acende em ``painel:material_detalhe``). Com ``query``, a
    querystring também precisa bater (ex.: a fila é a lista filtrada por status)."""
    request = context.get("request")
    atual = request.resolver_match.view_name if request and request.resolver_match else ""
    familia = rota.rsplit("_", 1)[0]
    ativo = atual == rota or (familia != rota and atual.startswith(familia + "_"))
    if query is not None:
        ativo = atual == rota and request is not None and request.GET.urlencode() == query
    return {
        "url": reverse(rota) + (f"?{query}" if query else ""),
        "rotulo": rotulo,
        "icone": icone,
        "badge": badge,
        "ativo": ativo,
    }


@register.inclusion_tag("painel/tags/paginacao.html", takes_context=True)
def paginacao(context: template.Context) -> dict[str, Any]:
    return {"page_obj": context.get("page_obj"), "request": context.get("request")}
