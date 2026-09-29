from __future__ import annotations

from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from contas.models import Setor, Usuario
from estoque.models import Categoria, Fornecedor
from painel.forms import CategoriaForm, FornecedorForm, SetorForm, UsuarioForm, UsuarioNovoForm
from painel.mixins import GestorMixin
from painel.views.crud import CrudCriar, CrudEditar, CrudLista

# --- Categorias (almoxarifado) ----------------------------------------------------


class CategoriaBase:
    model = Categoria
    form_class = CategoriaForm
    titulo, titulo_singular, rota = "Categorias", "categoria", "categoria"
    colunas = [("nome", "Nome", "")]


class CategoriaLista(CategoriaBase, CrudLista):
    pass


class CategoriaNova(CategoriaBase, CrudCriar):
    pass


class CategoriaEditar(CategoriaBase, CrudEditar):
    pass


# --- Fornecedores (almoxarifado) --------------------------------------------------


class FornecedorBase:
    model = Fornecedor
    form_class = FornecedorForm
    titulo, titulo_singular, rota = "Fornecedores", "fornecedor", "fornecedor"
    colunas = [
        ("razao_social", "Razão social", ""),
        ("cnpj", "CNPJ", "cnpj"),
        ("email", "E-mail", ""),
        ("ativo", "Ativo", "bool"),
    ]


class FornecedorLista(FornecedorBase, CrudLista):
    pass


class FornecedorNovo(FornecedorBase, CrudCriar):
    pass


class FornecedorEditar(FornecedorBase, CrudEditar):
    pass


# --- Setores e cotas (gestor) -------------------------------------------------------


class SetorBase(GestorMixin):
    model = Setor
    form_class = SetorForm
    titulo, titulo_singular, rota = "Setores e cotas", "setor", "setor"
    colunas = [
        ("sigla", "Sigla", ""),
        ("nome", "Nome", ""),
        ("chefe", "Chefia", ""),
        ("cota_mensal", "Cota mensal", "moeda"),
    ]


class SetorLista(SetorBase, CrudLista):
    def get_queryset(self) -> QuerySet[Setor]:
        return Setor.objects.select_related("chefe")


class SetorNovo(SetorBase, CrudCriar):
    pass


class SetorEditar(SetorBase, CrudEditar):
    pass


# --- Usuários (gestor) ------------------------------------------------------------


class UsuarioBase(GestorMixin):
    model = Usuario
    form_class = UsuarioForm
    titulo, titulo_singular, rota = "Usuários", "usuário", "usuario"
    colunas = [
        ("nome", "Nome", ""),
        ("email", "E-mail", ""),
        ("matricula", "Matrícula", ""),
        ("setor", "Setor", ""),
        ("perfil", "Perfil", ""),
        ("is_active", "Ativo", "bool"),
    ]


class UsuarioLista(UsuarioBase, CrudLista):
    template_name = "painel/usuarios/lista.html"  # estende o genérico e acrescenta uma ação por linha

    def get_queryset(self) -> QuerySet[Usuario]:
        return Usuario.objects.select_related("setor")


class UsuarioNovo(UsuarioBase, CrudCriar):
    form_class = UsuarioNovoForm


class UsuarioEditar(UsuarioBase, CrudEditar):
    pass


class UsuarioAlternarAtivo(GestorMixin, View):
    """Usuários não são excluídos (há histórico ligado a eles): são desativados.
    O acesso cai na hora, inclusive com um JWT já emitido."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        alvo = get_object_or_404(Usuario, pk=pk)
        if alvo.pk == self.usuario.pk:
            messages.error(request, "Você não pode desativar o próprio acesso.")
        else:
            alvo.is_active = not alvo.is_active
            alvo.save(update_fields=["is_active"])
            messages.success(request, f"{alvo.nome} {'reativado' if alvo.is_active else 'desativado'}.")
        return redirect("painel:usuario_lista")
