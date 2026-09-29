from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView

from dominio.excecoes import RegraNegocioError
from dominio.requisicao import Status
from estoque.models import Material
from estoque.services import ajustar_inventario
from painel.forms import AjusteForm, FiltroMateriaisForm, MaterialForm
from painel.mixins import PainelMixin
from painel.views.crud import CrudCriar, CrudEditar
from requisicoes.models import ItemRequisicao


class MaterialLista(PainelMixin, ListView[Material]):
    template_name = "painel/materiais/lista.html"
    paginate_by = 20
    context_object_name = "materiais"

    def get_queryset(self) -> QuerySet[Material]:
        self.filtro = FiltroMateriaisForm(self.request.GET or None)
        qs = Material.objects.select_related("categoria")
        if not self.filtro.is_valid():
            return qs.filter(ativo=True)
        dados = self.filtro.cleaned_data
        qs = qs.filter(ativo=dados["situacao"] != "inativos")
        if dados["busca"]:
            qs = qs.filter(Q(descricao__icontains=dados["busca"]) | Q(codigo__icontains=dados["busca"]))
        if dados["categoria"]:
            qs = qs.filter(categoria=dados["categoria"])
        if dados["situacao"] == "repor":
            # mesma regra de dominio.reposicao.precisa_repor, expressa em SQL
            qs = qs.filter(estoque_minimo__gt=0).filter(
                quantidade_em_estoque__lte=F("quantidade_reservada") + F("estoque_minimo")
            )
        return qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        contexto["filtro"] = self.filtro
        return contexto


class MaterialBase:
    model = Material
    form_class = MaterialForm
    titulo, titulo_singular, rota = "Materiais", "material", "material"


class MaterialNovo(MaterialBase, CrudCriar):
    pass


class MaterialEditar(MaterialBase, CrudEditar):
    pass


class MaterialDetalhe(PainelMixin, DetailView[Material]):
    """Ficha do material: posição, reservas, kardex e ajuste de inventário."""

    model = Material
    template_name = "painel/materiais/detalhe.html"
    context_object_name = "material"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        material = self.object
        kardex = material.movimentacoes.select_related("usuario", "requisicao", "setor", "entrada").order_by(
            "-id"
        )
        contexto["kardex"] = Paginator(kardex, 15).get_page(self.request.GET.get("page"))
        contexto["page_obj"] = contexto["kardex"]
        contexto["reservas"] = ItemRequisicao.objects.filter(
            material=material, requisicao__status=Status.APROVADA, quantidade_reservada__gt=0
        ).select_related("requisicao__setor", "requisicao__requisitante")
        contexto.setdefault(
            "ajuste_form", AjusteForm(initial={"quantidade_contada": material.quantidade_em_estoque})
        )
        return contexto

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Ajuste de inventário. Com erro, a página é redesenhada mostrando o formulário com as mensagens."""
        self.object = self.get_object()
        form = AjusteForm(request.POST)
        if form.is_valid():
            try:
                mov = ajustar_inventario(
                    material_id=self.object.pk,
                    quantidade_contada=form.cleaned_data["quantidade_contada"],
                    justificativa=form.cleaned_data["justificativa"],
                    usuario=self.usuario,
                )
            except RegraNegocioError as erro:
                form.add_error(None, str(erro))
            else:
                messages.success(request, f"Ajuste registrado: {mov.get_tipo_display()} de {mov.quantidade}.")
                return redirect("painel:material_detalhe", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(ajuste_form=form))
