from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from dominio.dinheiro import ZERO, valor_de
from dominio.requisicao import Status

# As choices do banco vêm do enum do domínio: uma única fonte da verdade
STATUS_CHOICES = [(s.value, s.rotulo) for s in Status]


class Requisicao(models.Model):
    requisitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requisicoes"
    )
    # Setor gravado na criação: se o servidor mudar de setor, a requisição continua do setor de origem
    setor = models.ForeignKey("contas.Setor", on_delete=models.PROTECT, related_name="requisicoes")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=Status.RASCUNHO.value)
    finalidade = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)
    enviado_em = models.DateTimeField(null=True, blank=True)
    atendido_em = models.DateTimeField(null=True, blank=True)
    valor_atendido = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "requisição"
        verbose_name_plural = "requisições"
        indexes = [models.Index(fields=["status"]), models.Index(fields=["setor", "status"])]

    def __str__(self) -> str:
        return f"Requisição {self.numero}"

    @property
    def numero(self) -> str:
        return f"{self.criado_em:%Y}/{self.pk or 0:05d}"

    @property
    def status_enum(self) -> Status:
        return Status(self.status)

    def valor_estimado(self) -> Decimal:
        """Quantidade vigente × custo médio atual (antes do atendimento, é uma estimativa)."""
        return sum((valor_de(i.quantidade_vigente, i.material.custo_medio) for i in self.itens.all()), ZERO)


class ItemRequisicao(models.Model):
    requisicao = models.ForeignKey(Requisicao, on_delete=models.CASCADE, related_name="itens")
    material = models.ForeignKey("estoque.Material", on_delete=models.PROTECT, related_name="+")
    quantidade_solicitada = models.PositiveIntegerField()
    quantidade_aprovada = models.PositiveIntegerField(null=True, blank=True)
    quantidade_reservada = models.PositiveIntegerField(default=0)
    quantidade_atendida = models.PositiveIntegerField(null=True, blank=True)
    custo_unitario = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["requisicao", "material"], name="item_requisicao_material_unico"),
            models.CheckConstraint(
                condition=Q(quantidade_solicitada__gt=0), name="item_requisicao_quantidade_positiva"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantidade_solicitada} × {self.material}"

    @property
    def quantidade_vigente(self) -> int:
        """A aprovada (se já houve avaliação) ou a solicitada."""
        return (
            self.quantidade_aprovada if self.quantidade_aprovada is not None else self.quantidade_solicitada
        )

    @property
    def valor_atendido(self) -> Decimal | None:
        if self.quantidade_atendida is None or self.custo_unitario is None:
            return None
        return valor_de(self.quantidade_atendida, self.custo_unitario)


class HistoricoRequisicao(models.Model):
    """Trilha de auditoria: quem mudou o status, quando e por quê."""

    requisicao = models.ForeignKey(Requisicao, on_delete=models.CASCADE, related_name="historico")
    de_status = models.CharField(max_length=30, choices=STATUS_CHOICES, blank=True)
    para_status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    quando = models.DateTimeField(default=timezone.now)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["quando", "id"]

    def __str__(self) -> str:
        return f"{self.requisicao_id}: {self.de_status} → {self.para_status}"
