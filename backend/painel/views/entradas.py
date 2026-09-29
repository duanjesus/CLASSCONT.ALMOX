from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from dominio.excecoes import RegraNegocioError
from estoque.models import Entrada
from estoque.services import ItemNota, registrar_entrada
from painel.forms import EntradaForm, ItensEntradaFormSet
from painel.mixins import PainelMixin


class EntradaLista(PainelMixin, ListView[Entrada]):
    template_name = "painel/entradas/lista.html"
    paginate_by = 20
    context_object_name = "entradas"

    def get_queryset(self) -> QuerySet[Entrada]:
        return Entrada.objects.select_related("fornecedor", "registrado_por")


class EntradaNova(PainelMixin, View):
    """Nota fiscal com N itens: um ``Form`` para o cabeçalho e um *formset* para as linhas."""

    template_name = "painel/entradas/form.html"
    prefixo = "itens"

    def _render(self, request: HttpRequest, form: EntradaForm, itens: Any) -> HttpResponse:
        return render(request, self.template_name, {"form": form, "itens": itens})

    def get(self, request: HttpRequest) -> HttpResponse:
        form = EntradaForm(initial={"data_recebimento": timezone.localdate()})
        return self._render(request, form, ItensEntradaFormSet(prefix=self.prefixo))

    def post(self, request: HttpRequest) -> HttpResponse:
        form = EntradaForm(request.POST)
        itens = ItensEntradaFormSet(request.POST, prefix=self.prefixo)
        if form.is_valid() and itens.is_valid():
            dados = form.cleaned_data
            try:
                entrada = registrar_entrada(
                    fornecedor=dados["fornecedor"],
                    numero_nota=dados["numero_nota"],
                    data_recebimento=dados["data_recebimento"],
                    empenho=dados["empenho"],
                    observacao=dados["observacao"],
                    usuario=self.usuario,
                    itens=[
                        ItemNota(i["material"].pk, i["quantidade"], i["valor_unitario"])
                        for i in itens.cleaned_data
                        if i
                    ],
                )
            except RegraNegocioError as erro:
                form.add_error(None, str(erro))
            else:
                messages.success(
                    request, f"Entrada da NF {entrada.numero_nota} registrada. O estoque foi atualizado."
                )
                return redirect("painel:entrada_detalhe", pk=entrada.pk)
        return self._render(request, form, itens)


class EntradaDetalhe(PainelMixin, DetailView[Entrada]):
    template_name = "painel/entradas/detalhe.html"
    context_object_name = "entrada"

    def get_queryset(self) -> QuerySet[Entrada]:
        return Entrada.objects.select_related("fornecedor", "registrado_por").prefetch_related(
            "itens__material"
        )
