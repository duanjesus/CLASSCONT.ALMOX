from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from contas.models import Usuario


class PainelMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Painel: exige login (senão → tela de login) e perfil do almoxarifado (senão → 403)."""

    request: Any

    @property
    def usuario(self) -> Usuario:
        usuario = self.request.user
        assert isinstance(usuario, Usuario)
        return usuario

    def test_func(self) -> bool:
        return bool(self.usuario.acessa_painel)


class GestorMixin(PainelMixin):
    """Cadastros estruturais (setores, cotas, usuários) e fechamento: só o gestor."""

    def test_func(self) -> bool:
        return self.usuario.eh_gestor
