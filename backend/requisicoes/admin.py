from django.contrib import admin

from requisicoes.models import HistoricoRequisicao, ItemRequisicao, Requisicao


class ItemInline(admin.TabularInline[ItemRequisicao, Requisicao]):
    model = ItemRequisicao
    extra = 0
    can_delete = False
    readonly_fields = ("material", "quantidade_solicitada", "quantidade_aprovada", "quantidade_atendida")


class HistoricoInline(admin.TabularInline[HistoricoRequisicao, Requisicao]):
    model = HistoricoRequisicao
    extra = 0
    can_delete = False
    readonly_fields = ("de_status", "para_status", "usuario", "quando", "observacao")


@admin.register(Requisicao)
class RequisicaoAdmin(admin.ModelAdmin[Requisicao]):
    list_display = ("id", "requisitante", "setor", "status", "criado_em")
    list_filter = ("status", "setor")
    readonly_fields = ("status",)
    inlines = [ItemInline, HistoricoInline]
