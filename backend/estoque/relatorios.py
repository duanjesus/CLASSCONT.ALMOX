"""Consultas de relatório: buscam no banco e aplicam as regras puras do domínio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from dominio.curva_abc import ItemClassificado, ItemConsumo, classificar
from dominio.reposicao import cobertura_em_dias, quantidade_sugerida
from estoque.models import Material, Movimentacao, TipoMovimentacao

DIAS_BASE_CONSUMO = 90


@dataclass(frozen=True)
class LinhaReposicao:
    material: Material
    disponivel: int
    sugerida: int
    consumo_periodo: int
    cobertura_dias: int | None


def materiais_para_repor(hoje: date | None = None) -> list[LinhaReposicao]:
    hoje = hoje or timezone.localdate()
    inicio = hoje - timedelta(days=DIAS_BASE_CONSUMO)
    consumo = dict(
        Movimentacao.objects.filter(tipo=TipoMovimentacao.SAIDA, data__gte=inicio)
        .values("material_id")
        .annotate(total=Sum("quantidade"))
        .values_list("material_id", "total")
    )
    linhas = []
    for material in (
        Material.objects.filter(ativo=True)
        .select_related("categoria")
        .order_by("categoria__nome", "descricao")
    ):
        if not material.precisa_repor:
            continue
        consumido = consumo.get(material.pk, 0)
        linhas.append(
            LinhaReposicao(
                material=material,
                disponivel=material.disponivel,
                sugerida=quantidade_sugerida(material.disponivel, material.estoque_maximo),
                consumo_periodo=consumido,
                cobertura_dias=cobertura_em_dias(material.disponivel, consumido, DIAS_BASE_CONSUMO),
            )
        )
    return linhas


def curva_abc(inicio: date, fim: date) -> list[ItemClassificado]:
    consumos = (
        Movimentacao.objects.filter(tipo=TipoMovimentacao.SAIDA, data__range=(inicio, fim))
        .values("material_id", "material__codigo", "material__descricao")
        .annotate(total=Sum("valor_total"))
    )
    return classificar(
        ItemConsumo(
            chave=c["material_id"],
            descricao=f"{c['material__codigo']} – {c['material__descricao']}",
            valor=c["total"],
        )
        for c in consumos
    )
