from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from dominio.atendimento import SaldoMaterial
from dominio.custo_medio import PosicaoEstoque
from dominio.dinheiro import valor_de
from dominio.reposicao import precisa_repor


class Unidade(models.TextChoices):
    UN = "UN", "Unidade"
    CX = "CX", "Caixa"
    PCT = "PCT", "Pacote"
    RESMA = "RESMA", "Resma"
    RL = "RL", "Rolo"
    FR = "FR", "Frasco"
    L = "L", "Litro"
    KG = "KG", "Quilo"
    PAR = "PAR", "Par"


class Categoria(models.Model):
    nome = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Fornecedor(models.Model):
    razao_social = models.CharField("razão social", max_length=150)
    cnpj = models.CharField("CNPJ", max_length=14, unique=True, help_text="Somente números.")
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["razao_social"]
        verbose_name_plural = "fornecedores"

    def __str__(self) -> str:
        return self.razao_social


class Material(models.Model):
    """Material de consumo.

    ``quantidade_em_estoque``, ``quantidade_reservada`` e ``custo_medio`` são um
    *cache* da posição do material: só os serviços de ``estoque.services`` os
    alteram, sempre na mesma transação que grava a movimentação no kardex.
    """

    codigo = models.CharField("código", max_length=20, unique=True)
    descricao = models.CharField("descrição", max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="materiais")
    unidade = models.CharField(max_length=10, choices=Unidade.choices, default=Unidade.UN)
    estoque_minimo = models.PositiveIntegerField("estoque mínimo", default=0)
    estoque_maximo = models.PositiveIntegerField("estoque máximo", default=0)
    ativo = models.BooleanField(default=True)

    quantidade_em_estoque = models.IntegerField(default=0, editable=False)
    quantidade_reservada = models.IntegerField(default=0, editable=False)
    custo_medio = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"), editable=False)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["descricao"]
        verbose_name_plural = "materiais"
        # Constraints no banco: a última linha de defesa, mesmo contra código com bug
        constraints = [
            models.CheckConstraint(
                condition=Q(quantidade_em_estoque__gte=0), name="material_estoque_nao_negativo"
            ),
            models.CheckConstraint(
                condition=Q(quantidade_reservada__gte=0), name="material_reserva_nao_negativa"
            ),
            models.CheckConstraint(
                condition=Q(estoque_maximo__gte=F("estoque_minimo")), name="material_maximo_gte_minimo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} – {self.descricao}"

    def saldo(self) -> SaldoMaterial:
        return SaldoMaterial(fisico=self.quantidade_em_estoque, reservado=self.quantidade_reservada)

    def posicao(self) -> PosicaoEstoque:
        return PosicaoEstoque(self.quantidade_em_estoque, self.custo_medio)

    @property
    def disponivel(self) -> int:
        return self.saldo().disponivel

    @property
    def valor_em_estoque(self) -> Decimal:
        return valor_de(self.quantidade_em_estoque, self.custo_medio)

    @property
    def precisa_repor(self) -> bool:
        return precisa_repor(self.disponivel, self.estoque_minimo)


class Entrada(models.Model):
    """Recebimento de material (nota fiscal)."""

    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name="entradas")
    numero_nota = models.CharField("nº da nota fiscal", max_length=20)
    data_recebimento = models.DateField("data de recebimento")
    empenho = models.CharField("nota de empenho", max_length=20, blank=True)
    observacao = models.TextField("observação", blank=True)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_recebimento", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["fornecedor", "numero_nota"], name="entrada_nota_unica_por_fornecedor"
            ),
        ]

    def __str__(self) -> str:
        return f"NF {self.numero_nota} – {self.fornecedor}"


class ItemEntrada(models.Model):
    entrada = models.ForeignKey(Entrada, on_delete=models.CASCADE, related_name="itens")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="+")
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    valor_unitario = models.DecimalField(
        "valor unitário", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entrada", "material"], name="item_entrada_material_unico"),
            models.CheckConstraint(condition=Q(quantidade__gt=0), name="item_entrada_quantidade_positiva"),
        ]

    def __str__(self) -> str:
        return f"{self.quantidade} × {self.material}"

    @property
    def valor_total(self) -> Decimal:
        return valor_de(self.quantidade, self.valor_unitario)


class TipoMovimentacao(models.TextChoices):
    ENTRADA = "ENTRADA", "Entrada"
    SAIDA = "SAIDA", "Saída"
    AJUSTE_ENTRADA = "AJUSTE_ENTRADA", "Ajuste de inventário (+)"
    AJUSTE_SAIDA = "AJUSTE_SAIDA", "Ajuste de inventário (−)"


class MovimentacaoImutavelError(Exception):
    pass


class Movimentacao(models.Model):
    """Linha do kardex (ficha de estoque). É a fonte da verdade do estoque.

    Imutável: não se edita nem se apaga uma movimentação; corrige-se com outra
    (ajuste). Os campos ``saldo_*`` registram a posição logo após o lançamento.
    """

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="movimentacoes")
    tipo = models.CharField(max_length=20, choices=TipoMovimentacao.choices)
    data = models.DateField()
    quantidade = models.PositiveIntegerField()
    custo_unitario = models.DecimalField(max_digits=14, decimal_places=4)
    valor_total = models.DecimalField(max_digits=14, decimal_places=2)
    saldo_quantidade = models.IntegerField()
    saldo_custo_medio = models.DecimalField(max_digits=14, decimal_places=4)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    entrada = models.ForeignKey(Entrada, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    requisicao = models.ForeignKey(
        "requisicoes.Requisicao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimentacoes",
    )
    # Setor que consumiu (saídas): base da cota mensal e dos relatórios de consumo
    setor = models.ForeignKey(
        "contas.Setor", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    observacao = models.TextField("observação", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "movimentação"
        verbose_name_plural = "movimentações"
        indexes = [
            models.Index(fields=["material", "id"]),
            models.Index(fields=["data"]),
            models.Index(fields=["setor", "data"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(quantidade__gt=0), name="movimentacao_quantidade_positiva"),
            models.CheckConstraint(
                condition=Q(saldo_quantidade__gte=0), name="movimentacao_saldo_nao_negativo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} de {self.quantidade} – {self.material.codigo}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise MovimentacaoImutavelError("Movimentações do kardex não podem ser alteradas.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise MovimentacaoImutavelError("Movimentações do kardex não podem ser excluídas.")

    @property
    def eh_entrada(self) -> bool:
        return self.tipo in (TipoMovimentacao.ENTRADA, TipoMovimentacao.AJUSTE_ENTRADA)


class FechamentoCompetencia(models.Model):
    """Mês fechado: não aceita mais movimentações. Guarda um retrato dos totais."""

    competencia = models.CharField("competência", max_length=7, unique=True)  # AAAA-MM
    fechado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fechado_em = models.DateTimeField(auto_now_add=True)
    valor_entradas = models.DecimalField(max_digits=14, decimal_places=2)
    valor_saidas = models.DecimalField(max_digits=14, decimal_places=2)
    valor_ajustes = models.DecimalField(max_digits=14, decimal_places=2)
    valor_estoque = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["-competencia"]
        verbose_name = "fechamento de competência"
        verbose_name_plural = "fechamentos de competência"

    def __str__(self) -> str:
        return self.competencia
