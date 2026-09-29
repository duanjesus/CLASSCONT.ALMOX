from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth.views import LoginView
from django.db.models import DecimalField, F, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from dominio.competencia import Competencia
from dominio.dinheiro import ZERO, arredondar_moeda
from dominio.requisicao import Status
from estoque.models import Material, Movimentacao
from estoque.relatorios import materiais_para_repor
from estoque.services import competencias_para_fechar, resumo_competencia
from painel.forms import FormLogin
from painel.mixins import PainelMixin
from requisicoes.models import Requisicao


class EntrarView(LoginView):
    template_name = "painel/login.html"
    authentication_form = FormLogin
    redirect_authenticated_user = True


class DashboardView(PainelMixin, TemplateView):
    template_name = "painel/dashboard.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        competencia = Competencia.de_data(timezone.localdate())
        valor_estoque: Decimal = (
            Material.objects.aggregate(
                total=Sum(F("quantidade_em_estoque") * F("custo_medio"), output_field=DecimalField())
            )["total"]
            or ZERO
        )
        contexto.update(
            competencia=competencia,
            resumo=resumo_competencia(competencia),
            valor_estoque=arredondar_moeda(valor_estoque),
            materiais_ativos=Material.objects.filter(ativo=True).count(),
            para_repor=materiais_para_repor()[:6],
            fila=Requisicao.objects.filter(status=Status.APROVADA)
            .select_related("setor", "requisitante")
            .prefetch_related("itens")
            .order_by("id")[:6],
            ultimas=Movimentacao.objects.select_related("material", "usuario").order_by("-id")[:8],
            meses_abertos=competencias_para_fechar() if self.usuario.eh_gestor else [],
        )
        return contexto
