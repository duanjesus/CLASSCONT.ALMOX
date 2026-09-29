"""Guia de saída de material em PDF: template Django → HTML → WeasyPrint."""

from __future__ import annotations

from django.template.loader import render_to_string
from django.utils import timezone

from requisicoes.models import Requisicao


def gerar_guia_saida(requisicao: Requisicao) -> bytes:
    # Import tardio: o WeasyPrint depende de bibliotecas do sistema (Pango),
    # instaladas na imagem Docker; o resto do sistema funciona sem elas.
    from weasyprint import HTML

    requisicao = (
        Requisicao.objects.select_related("requisitante", "setor")
        .prefetch_related("itens__material", "historico__usuario")
        .get(pk=requisicao.pk)
    )
    atendimento = next(
        (h for h in reversed(requisicao.historico.all()) if h.para_status.startswith("ATENDIDA")), None
    )
    html = render_to_string(
        "pdf/guia_saida.html",
        {"requisicao": requisicao, "atendimento": atendimento, "emitido_em": timezone.localtime()},
    )
    pdf: bytes = HTML(string=html).write_pdf()
    return pdf
