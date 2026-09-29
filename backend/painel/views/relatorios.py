from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils import timezone
from django.views.generic import TemplateView

from contas.models import Setor
from dominio.competencia import Competencia
from dominio.dinheiro import ZERO
from dominio.excecoes import RegraNegocioError
from estoque.relatorios import DIAS_BASE_CONSUMO, curva_abc, materiais_para_repor
from painel.forms import PeriodoForm
from painel.mixins import PainelMixin
from requisicoes.services import situacao_cota


class ReposicaoView(PainelMixin, TemplateView):
    template_name = "painel/relatorios/reposicao.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        contexto["linhas"] = materiais_para_repor()
        contexto["dias_base"] = DIAS_BASE_CONSUMO
        return contexto


class CurvaAbcView(PainelMixin, TemplateView):
    template_name = "painel/relatorios/curva_abc.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        form = PeriodoForm(
            self.request.GET if "inicio" in self.request.GET else None, initial=PeriodoForm.padrao()
        )
        periodo = form.cleaned_data if form.is_bound and form.is_valid() else PeriodoForm.padrao()
        itens = curva_abc(periodo["inicio"], periodo["fim"])
        total = sum((i.item.valor for i in itens), ZERO)
        resumo = []
        for classe in ("A", "B", "C"):
            da_classe = [i for i in itens if i.classe == classe]
            valor = sum((i.item.valor for i in da_classe), ZERO)
            resumo.append(
                {
                    "classe": classe,
                    "itens": len(da_classe),
                    "valor": valor,
                    "percentual": valor * 100 / total if total else Decimal(0),
                }
            )
        contexto.update(form=form, itens=itens, total=total, resumo=resumo, periodo=periodo)
        return contexto


class ConsumoSetoresView(PainelMixin, TemplateView):
    template_name = "painel/relatorios/consumo_setores.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        atual = Competencia.de_data(timezone.localdate())
        try:
            competencia = Competencia.de_texto(self.request.GET.get("competencia", str(atual)))
        except RegraNegocioError:
            competencia = atual
        contexto.update(
            competencia=competencia,
            anterior=competencia.anterior(),
            proxima=competencia.proxima() if competencia < atual else None,
            linhas=[
                (setor, situacao_cota(setor, competencia)) for setor in Setor.objects.select_related("chefe")
            ],
        )
        return contexto
