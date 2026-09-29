"""Ponto de reposição: quando comprar e quanto."""

from __future__ import annotations


def precisa_repor(disponivel: int, estoque_minimo: int) -> bool:
    """O material atingiu o mínimo (``estoque_minimo = 0`` significa "não controlar")."""
    return estoque_minimo > 0 and disponivel <= estoque_minimo


def quantidade_sugerida(disponivel: int, estoque_maximo: int) -> int:
    """Compra sugerida: o necessário para voltar ao estoque máximo."""
    return max(0, estoque_maximo - disponivel)


def cobertura_em_dias(disponivel: int, consumo_no_periodo: int, dias_do_periodo: int) -> int | None:
    """Por quantos dias o disponível dura no ritmo de consumo recente (None = sem consumo)."""
    if consumo_no_periodo <= 0 or dias_do_periodo <= 0:
        return None
    return int(disponivel * dias_do_periodo // consumo_no_periodo)
