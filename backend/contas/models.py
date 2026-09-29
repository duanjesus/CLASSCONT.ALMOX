from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


class Perfil(models.TextChoices):
    SERVIDOR = "SERVIDOR", "Servidor"
    ALMOXARIFE = "ALMOXARIFE", "Almoxarife"
    GESTOR = "GESTOR", "Gestor do almoxarifado"


class Setor(models.Model):
    sigla = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=120)
    chefe = models.ForeignKey(
        "contas.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="setores_chefiados",
    )
    cota_mensal = models.DecimalField(
        "cota mensal (R$)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Deixe em branco para não limitar o consumo do setor.",
    )

    class Meta:
        ordering = ["sigla"]
        verbose_name_plural = "setores"

    def __str__(self) -> str:
        return f"{self.sigla} – {self.nome}"


class UsuarioManager(BaseUserManager["Usuario"]):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> Usuario:
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        usuario = self.model(email=self.normalize_email(email).lower(), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> Usuario:
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("perfil", Perfil.GESTOR)
        return self.create_user(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Servidor do órgão. O login é pelo e-mail.

    A **chefia não é um perfil gravado**: é derivada de o usuário ser chefe de
    algum setor. Assim o papel nunca fica dessincronizado do cadastro de setores.
    """

    email = models.EmailField("e-mail", unique=True)
    nome = models.CharField(max_length=150)
    matricula = models.CharField("matrícula", max_length=20, unique=True)
    cargo = models.CharField(max_length=80, blank=True)
    setor = models.ForeignKey(
        Setor, on_delete=models.PROTECT, null=True, blank=True, related_name="servidores"
    )
    perfil = models.CharField(max_length=20, choices=Perfil.choices, default=Perfil.SERVIDOR)
    is_active = models.BooleanField("ativo", default=True)
    is_staff = models.BooleanField("acessa o Django Admin", default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["nome", "matricula"]

    objects = UsuarioManager()

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    @cached_property
    def ids_setores_chefiados(self) -> frozenset[int]:
        if self.pk is None:
            return frozenset()
        return frozenset(self.setores_chefiados.values_list("id", flat=True))

    @property
    def eh_chefia(self) -> bool:
        return bool(self.ids_setores_chefiados)

    def chefia_setor(self, setor_id: int) -> bool:
        return setor_id in self.ids_setores_chefiados

    @property
    def eh_almoxarife(self) -> bool:
        return self.perfil == Perfil.ALMOXARIFE

    @property
    def eh_gestor(self) -> bool:
        return self.perfil == Perfil.GESTOR

    @property
    def acessa_painel(self) -> bool:
        """Almoxarife e gestor operam o estoque pelo painel (templates Django)."""
        return self.perfil in (Perfil.ALMOXARIFE, Perfil.GESTOR)

    @property
    def papeis(self) -> list[str]:
        papeis = ["SERVIDOR"]
        if self.eh_chefia:
            papeis.append("CHEFIA")
        if self.perfil != Perfil.SERVIDOR:
            papeis.append(self.perfil)
        return papeis
