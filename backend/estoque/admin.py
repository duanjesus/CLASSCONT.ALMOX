from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from estoque.models import Categoria, Entrada, FechamentoCompetencia, Fornecedor, Material, Movimentacao


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin[Categoria]):
    search_fields = ("nome",)


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin[Fornecedor]):
    list_display = ("razao_social", "cnpj", "ativo")
    search_fields = ("razao_social", "cnpj")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin[Material]):
    list_display = (
        "codigo",
        "descricao",
        "categoria",
        "quantidade_em_estoque",
        "quantidade_reservada",
        "ativo",
    )
    list_filter = ("categoria", "ativo")
    search_fields = ("codigo", "descricao")
    readonly_fields = ("quantidade_em_estoque", "quantidade_reservada", "custo_medio")


@admin.register(Entrada)
class EntradaAdmin(admin.ModelAdmin[Entrada]):
    list_display = ("numero_nota", "fornecedor", "data_recebimento", "valor_total")

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False  # entradas são registradas pelo painel (o serviço atualiza o kardex)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin[Movimentacao]):
    """Kardex somente leitura, inclusive no Django Admin."""

    list_display = ("id", "data", "material", "tipo", "quantidade", "valor_total", "saldo_quantidade")
    list_filter = ("tipo",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(FechamentoCompetencia)
class FechamentoAdmin(admin.ModelAdmin[FechamentoCompetencia]):
    list_display = ("competencia", "fechado_por", "fechado_em", "valor_estoque")
