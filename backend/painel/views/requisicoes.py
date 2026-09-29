from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from contas.models import Setor
from dominio.atendimento import maximo_atendivel
from dominio.competencia import Competencia
from dominio.requisicao import Status
from painel.forms import AtendimentoForm, RecusaForm
from painel.mixins import PainelMixin
from requisicoes import services
from requisicoes.models import Requisicao
from requisicoes.pdf import gerar_guia_saida
from requisicoes.permissoes import acoes_do_usuario


def _itens_para_atender(requisicao: Requisicao) -> list[tuple[int, str, int]]:
    return [
        (
            item.pk,
            f"{item.material.codigo} – {item.material.descricao}",
            maximo_atendivel(item.quantidade_vigente, item.quantidade_reservada, item.material.saldo()),
        )
        for item in requisicao.itens.all()
    ]


class RequisicaoLista(PainelMixin, ListView[Requisicao]):
    template_name = "painel/requisicoes/lista.html"
    paginate_by = 20
    context_object_name = "requisicoes"

    def get_queryset(self) -> QuerySet[Requisicao]:
        qs = (
            Requisicao.objects.exclude(status=Status.RASCUNHO)  # rascunho é privado do servidor
            .select_related("setor", "requisitante")
            .prefetch_related("itens")
        )
        status = self.request.GET.get("status")
        if status in Status.__members__:
            qs = qs.filter(status=status)
            if status == Status.APROVADA:
                qs = qs.order_by("id")  # fila: primeiro a chegar, primeiro a ser atendido
        setor = self.request.GET.get("setor")
        if setor and setor.isdigit():
            qs = qs.filter(setor_id=int(setor))
        return qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        contexto["opcoes_status"] = [s for s in Status if s != Status.RASCUNHO]
        contexto["setores"] = Setor.objects.all()
        contexto["status_atual"] = self.request.GET.get("status", "")
        contexto["setor_atual"] = self.request.GET.get("setor", "")
        return contexto


class RequisicaoDetalhe(PainelMixin, DetailView[Requisicao]):
    template_name = "painel/requisicoes/detalhe.html"
    context_object_name = "requisicao"

    def get_queryset(self) -> QuerySet[Requisicao]:
        return Requisicao.objects.select_related("setor", "requisitante").prefetch_related(
            "itens__material", "historico__usuario"
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        requisicao = self.object
        acoes = acoes_do_usuario(self.usuario, requisicao)
        contexto["acoes"] = acoes
        if "atender" in acoes:
            contexto["atendimento_form"] = AtendimentoForm(itens=_itens_para_atender(requisicao))
        if "recusar" in acoes:
            contexto["recusa_form"] = RecusaForm()
            contexto["cota"] = services.situacao_cota(
                requisicao.setor, Competencia.de_data(timezone.localdate()), excluir_id=requisicao.pk
            )
            contexto["valor_estimado"] = requisicao.valor_estimado()
        return contexto


class RequisicaoAtender(PainelMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        requisicao = get_object_or_404(Requisicao.objects.prefetch_related("itens__material"), pk=pk)
        form = AtendimentoForm(request.POST, itens=_itens_para_atender(requisicao))
        if not form.is_valid():
            erros = "; ".join(
                f"{form.fields[c].label}: {' '.join(str(m) for m in e)}" for c, e in form.errors.items()
            )
            messages.error(request, f"Quantidades inválidas. {erros}")
            return redirect("painel:requisicao_detalhe", pk=pk)
        atendida = services.atender(pk, self.usuario, form.quantidades())
        if atendida.status == Status.ATENDIDA_PARCIALMENTE:
            messages.warning(request, "Requisição atendida parcialmente. O saldo que faltou foi liberado.")
        else:
            messages.success(request, "Requisição atendida. O estoque foi baixado.")
        return redirect("painel:requisicao_detalhe", pk=pk)


class RequisicaoAprovar(PainelMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        services.aprovar(pk, self.usuario, observacao=request.POST.get("observacao", ""))
        messages.success(request, "Requisição autorizada. O saldo foi reservado.")
        return redirect("painel:requisicao_detalhe", pk=pk)


class RequisicaoRecusar(PainelMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        form = RecusaForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe o motivo da recusa (mínimo de 5 caracteres).")
        else:
            services.recusar(pk, self.usuario, form.cleaned_data["motivo"])
            messages.success(request, "Requisição recusada. O servidor foi avisado por e-mail.")
        return redirect("painel:requisicao_detalhe", pk=pk)


class RequisicaoCancelar(PainelMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        services.cancelar(pk, self.usuario, request.POST.get("motivo", "Cancelada pelo almoxarifado."))
        messages.success(request, "Requisição cancelada. As reservas foram liberadas.")
        return redirect("painel:requisicao_detalhe", pk=pk)


class RequisicaoGuia(PainelMixin, View):
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        requisicao = get_object_or_404(Requisicao, pk=pk)
        if requisicao.status_enum not in (Status.ATENDIDA, Status.ATENDIDA_PARCIALMENTE):
            messages.error(request, "A guia de saída só existe para requisições atendidas.")
            return redirect("painel:requisicao_detalhe", pk=pk)
        resposta = HttpResponse(gerar_guia_saida(requisicao), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="guia-{requisicao.pk}.pdf"'
        return resposta
