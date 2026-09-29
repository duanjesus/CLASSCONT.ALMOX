from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from contas.models import Setor, Usuario


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin[Setor]):
    list_display = ("sigla", "nome", "chefe", "cota_mensal")
    search_fields = ("sigla", "nome")


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):  # type: ignore[type-arg]
    ordering = ("nome",)
    list_display = ("nome", "email", "matricula", "setor", "perfil", "is_active")
    list_filter = ("perfil", "is_active", "setor")
    search_fields = ("nome", "email", "matricula")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados funcionais", {"fields": ("nome", "matricula", "cargo", "setor", "perfil")}),
        ("Acesso", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "nome", "matricula", "setor", "perfil", "password1", "password2")}),
    )
