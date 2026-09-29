"""Serializers da API.

Leitura: ``ModelSerializer`` com os campos explícitos (nunca ``__all__``: o
contrato da API não muda sozinho quando o model muda).
Escrita: ``Serializer`` simples que só valida a entrada; quem grava é o serviço.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from contas.models import Setor, Usuario
from dominio.cota import SituacaoCota
from dominio.requisicao import Status
from estoque.models import Categoria, Material
from requisicoes.models import HistoricoRequisicao, ItemRequisicao, Requisicao
from requisicoes.permissoes import acoes_do_usuario

# --- Leitura --------------------------------------------------------------------


class SetorResumoSerializer(serializers.ModelSerializer[Setor]):
    class Meta:
        model = Setor
        fields = ["id", "sigla", "nome"]


class UsuarioSerializer(serializers.ModelSerializer[Usuario]):
    setor = SetorResumoSerializer(allow_null=True)
    papeis = serializers.ListField(child=serializers.CharField(), read_only=True)
    eh_chefia = serializers.BooleanField(read_only=True)
    setores_chefiados = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "nome",
            "email",
            "matricula",
            "cargo",
            "setor",
            "perfil",
            "papeis",
            "eh_chefia",
            "setores_chefiados",
        ]

    def get_setores_chefiados(self, usuario: Usuario) -> list[dict[str, Any]]:
        return SetorResumoSerializer(usuario.setores_chefiados.all(), many=True).data  # type: ignore[return-value]


class CategoriaSerializer(serializers.ModelSerializer[Categoria]):
    class Meta:
        model = Categoria
        fields = ["id", "nome"]


class MaterialSerializer(serializers.ModelSerializer[Material]):
    categoria = serializers.CharField(source="categoria.nome")
    unidade_rotulo = serializers.CharField(source="get_unidade_display")
    disponivel = serializers.IntegerField()

    class Meta:
        model = Material
        fields = [
            "id", "codigo", "descricao", "categoria", "unidade", "unidade_rotulo",
            "disponivel", "estoque_maximo", "custo_medio",
        ]  # fmt: skip


class MaterialResumoSerializer(serializers.ModelSerializer[Material]):
    class Meta:
        model = Material
        fields = ["id", "codigo", "descricao", "unidade", "custo_medio"]


class ItemRequisicaoSerializer(serializers.ModelSerializer[ItemRequisicao]):
    material = MaterialResumoSerializer()
    valor_atendido = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)

    class Meta:
        model = ItemRequisicao
        fields = [
            "id", "material", "quantidade_solicitada", "quantidade_aprovada",
            "quantidade_reservada", "quantidade_atendida", "custo_unitario", "valor_atendido",
        ]  # fmt: skip


class HistoricoSerializer(serializers.ModelSerializer[HistoricoRequisicao]):
    usuario = serializers.CharField(source="usuario.nome")
    para_status_rotulo = serializers.CharField(source="get_para_status_display")

    class Meta:
        model = HistoricoRequisicao
        fields = ["id", "de_status", "para_status", "para_status_rotulo", "usuario", "quando", "observacao"]


class RequisicaoListaSerializer(serializers.ModelSerializer[Requisicao]):
    status_rotulo = serializers.CharField(source="get_status_display")
    setor = SetorResumoSerializer()
    requisitante = serializers.CharField(source="requisitante.nome")
    total_itens = serializers.SerializerMethodField()

    class Meta:
        model = Requisicao
        fields = [
            "id", "numero", "status", "status_rotulo", "setor", "requisitante",
            "finalidade", "criado_em", "enviado_em", "atendido_em", "total_itens", "valor_atendido",
        ]  # fmt: skip

    def get_total_itens(self, requisicao: Requisicao) -> int:
        return len(requisicao.itens.all())  # usa o prefetch_related


class RequisicaoDetalheSerializer(RequisicaoListaSerializer):
    itens = ItemRequisicaoSerializer(many=True)
    historico = HistoricoSerializer(many=True)
    valor_estimado = serializers.DecimalField(max_digits=14, decimal_places=2)
    acoes = serializers.SerializerMethodField()

    class Meta(RequisicaoListaSerializer.Meta):
        fields = [*RequisicaoListaSerializer.Meta.fields, "itens", "historico", "valor_estimado", "acoes"]

    def get_acoes(self, requisicao: Requisicao) -> list[str]:
        return acoes_do_usuario(self.context["request"].user, requisicao)


class SituacaoCotaSerializer(serializers.Serializer[SituacaoCota]):
    cota = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    consumido = serializers.DecimalField(max_digits=14, decimal_places=2)
    comprometido = serializers.DecimalField(max_digits=14, decimal_places=2)
    disponivel = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    percentual_utilizado = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)


# --- Escrita (entrada de dados) ---------------------------------------------------


class ItemPedidoSerializer(serializers.Serializer[dict[str, Any]]):
    material_id = serializers.IntegerField(min_value=1)
    quantidade = serializers.IntegerField(min_value=1, max_value=10_000)


class RequisicaoEscritaSerializer(serializers.Serializer[dict[str, Any]]):
    finalidade = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    itens = ItemPedidoSerializer(many=True, allow_empty=False)


class ItemAprovacaoSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    quantidade = serializers.IntegerField(min_value=0)


class AprovarSerializer(serializers.Serializer[dict[str, Any]]):
    itens = ItemAprovacaoSerializer(many=True, required=False)
    observacao = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")


class RecusarSerializer(serializers.Serializer[dict[str, Any]]):
    motivo = serializers.CharField(min_length=5, max_length=500)


class CancelarSerializer(serializers.Serializer[dict[str, Any]]):
    motivo = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")


class FiltroRequisicaoSerializer(serializers.Serializer[dict[str, Any]]):
    escopo = serializers.ChoiceField(choices=["minhas", "pendentes", "setor"], default="minhas")
    status = serializers.ChoiceField(choices=[s.value for s in Status], required=False)
