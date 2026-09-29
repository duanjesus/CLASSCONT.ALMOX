"""CRUD genérico com class-based views: um template de lista e um de formulário
servem a todos os cadastros simples (categorias, fornecedores, setores, usuários)."""

from __future__ import annotations

from typing import Any

from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from painel.mixins import PainelMixin

# (campo, rótulo, formato) — formato: "", "moeda", "bool" ou "cnpj"
Coluna = tuple[str, str, str]


class CrudMixin(PainelMixin):
    titulo: str
    titulo_singular: str
    rota: str  # prefixo das rotas: "<rota>_lista", "<rota>_novo", "<rota>_editar"
    colunas: list[Coluna] = []

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto: dict[str, Any] = super().get_context_data(**kwargs)  # type: ignore[misc]
        contexto.update(
            titulo=self.titulo,
            titulo_singular=self.titulo_singular,
            colunas=self.colunas,
            rota_lista=f"painel:{self.rota}_lista",
            rota_novo=f"painel:{self.rota}_novo",
            rota_editar=f"painel:{self.rota}_editar",
        )
        return contexto

    def get_success_url(self) -> str:
        return reverse(f"painel:{self.rota}_lista")


class CrudLista(CrudMixin, ListView[Any]):
    template_name = "painel/crud/lista.html"
    paginate_by = 25
    context_object_name = "registros"


class CrudCriar(CrudMixin, SuccessMessageMixin[Any], CreateView[Any, Any]):
    template_name = "painel/crud/form.html"
    success_message = "Cadastro salvo."


class CrudEditar(CrudMixin, SuccessMessageMixin[Any], UpdateView[Any, Any]):
    template_name = "painel/crud/form.html"
    success_message = "Alterações salvas."
