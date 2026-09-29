from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from dominio.competencia import Competencia
from estoque.models import FechamentoCompetencia
from estoque.services import competencias_para_fechar, fechar_competencia, resumo_competencia
from painel.mixins import GestorMixin


class CompetenciaLista(GestorMixin, TemplateView):
    template_name = "painel/competencias/lista.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        abertas = competencias_para_fechar()
        # Fecha-se em ordem: só a mais antiga pode ser fechada agora
        contexto["proxima"] = resumo_competencia(abertas[0]) if abertas else None
        contexto["demais_abertas"] = abertas[1:]
        contexto["fechadas"] = FechamentoCompetencia.objects.select_related("fechado_por")
        return contexto


class CompetenciaFechar(GestorMixin, View):
    def post(self, request: HttpRequest) -> HttpResponse:
        competencia = Competencia.de_texto(request.POST.get("competencia", ""))
        fechar_competencia(competencia, self.usuario)
        messages.success(request, f"Competência de {competencia.nome} fechada.")
        return redirect("painel:competencia_lista")
