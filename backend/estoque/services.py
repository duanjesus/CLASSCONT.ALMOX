"""Casos de uso do estoque.

Padrão de todos os serviços que mexem em saldo:
1. abrem uma transação (``@transaction.atomic``);
2. travam as linhas dos materiais com ``SELECT ... FOR UPDATE``, **sempre em
   ordem de id** (a ordem fixa evita deadlock entre duas operações simultâneas);
3. aplicam a regra pura do ``dominio`` e gravam material + kardex juntos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, F, Sum, When
from django.utils import timezone

from contas.models import Setor, Usuario
from dominio.competencia import Competencia, validar_fechamento, validar_lancamento
from dominio.dinheiro import ZERO, valor_de
from dominio.excecoes import AcessoNegadoError, RegraNegocioError
from estoque.models import (
    Entrada,
    FechamentoCompetencia,
    Fornecedor,
    ItemEntrada,
    Material,
    Movimentacao,
    TipoMovimentacao,
)

TIPOS_ENTRADA = (TipoMovimentacao.ENTRADA, TipoMovimentacao.AJUSTE_ENTRADA)


def competencias_fechadas() -> set[Competencia]:
    return {
        Competencia.de_texto(c) for c in FechamentoCompetencia.objects.values_list("competencia", flat=True)
    }


def garantir_competencia_aberta(dia: date) -> None:
    validar_lancamento(dia, competencias_fechadas())


def travar_materiais(ids: Sequence[int]) -> dict[int, Material]:
    """SELECT ... FOR UPDATE nos materiais, em ordem de id."""
    materiais = Material.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    return {m.pk: m for m in materiais}


def _exigir_operador(usuario: Usuario) -> None:
    if not usuario.acessa_painel:
        raise AcessoNegadoError("Somente o almoxarifado pode movimentar o estoque.")


# --- Entradas -------------------------------------------------------------------


@dataclass(frozen=True)
class ItemNota:
    material_id: int
    quantidade: int
    valor_unitario: Decimal


@transaction.atomic
def registrar_entrada(
    *,
    fornecedor: Fornecedor,
    numero_nota: str,
    data_recebimento: date,
    itens: Sequence[ItemNota],
    usuario: Usuario,
    empenho: str = "",
    observacao: str = "",
) -> Entrada:
    _exigir_operador(usuario)
    if data_recebimento > timezone.localdate():
        raise RegraNegocioError("A data de recebimento não pode ser futura.")
    garantir_competencia_aberta(data_recebimento)
    if not itens:
        raise RegraNegocioError("Informe ao menos um item da nota.")
    ids = [i.material_id for i in itens]
    if len(set(ids)) != len(ids):
        raise RegraNegocioError("O mesmo material aparece mais de uma vez na nota: some as quantidades.")
    numero_nota = numero_nota.strip()
    duplicada = RegraNegocioError(f"A nota fiscal {numero_nota} deste fornecedor já foi registrada.")
    if Entrada.objects.filter(fornecedor=fornecedor, numero_nota=numero_nota).exists():
        raise duplicada

    try:
        # Savepoint: dois lançamentos simultâneos da mesma NF passam juntos pela checagem acima;
        # quem decide é a constraint única do banco, e o perdedor recebe a mesma mensagem.
        with transaction.atomic():
            entrada = Entrada.objects.create(
                fornecedor=fornecedor,
                numero_nota=numero_nota,
                data_recebimento=data_recebimento,
                empenho=empenho.strip(),
                observacao=observacao.strip(),
                registrado_por=usuario,
            )
    except IntegrityError:
        raise duplicada from None
    materiais = travar_materiais(ids)
    total = ZERO
    for item in sorted(itens, key=lambda i: i.material_id):
        material = materiais.get(item.material_id)
        if material is None or not material.ativo:
            raise RegraNegocioError("Material inexistente ou inativo na nota.")
        nova = material.posicao().com_entrada(item.quantidade, item.valor_unitario)
        ItemEntrada.objects.create(
            entrada=entrada,
            material=material,
            quantidade=item.quantidade,
            valor_unitario=item.valor_unitario,
        )
        valor = valor_de(item.quantidade, item.valor_unitario)
        total += valor
        Movimentacao.objects.create(
            material=material,
            tipo=TipoMovimentacao.ENTRADA,
            data=data_recebimento,
            quantidade=item.quantidade,
            custo_unitario=item.valor_unitario,
            valor_total=valor,
            saldo_quantidade=nova.quantidade,
            saldo_custo_medio=nova.custo_medio,
            usuario=usuario,
            entrada=entrada,
            observacao=f"NF {numero_nota}",
        )
        material.quantidade_em_estoque = nova.quantidade
        material.custo_medio = nova.custo_medio
        material.save(update_fields=["quantidade_em_estoque", "custo_medio", "atualizado_em"])

    entrada.valor_total = total
    entrada.save(update_fields=["valor_total"])
    return entrada


# --- Saída (usada pelo atendimento de requisições) --------------------------------


def registrar_saida(
    *,
    material: Material,
    quantidade: int,
    usuario: Usuario,
    setor: Setor,
    requisicao_id: int,
    dia: date,
) -> Movimentacao:
    """Baixa o estoque. O chamador precisa ter travado ``material`` na transação."""
    posicao = material.posicao()
    nova = posicao.com_saida(quantidade)
    movimentacao = Movimentacao.objects.create(
        material=material,
        tipo=TipoMovimentacao.SAIDA,
        data=dia,
        quantidade=quantidade,
        custo_unitario=posicao.custo_medio,
        valor_total=posicao.valor_saida(quantidade),
        saldo_quantidade=nova.quantidade,
        saldo_custo_medio=nova.custo_medio,
        usuario=usuario,
        setor=setor,
        requisicao_id=requisicao_id,
    )
    material.quantidade_em_estoque = nova.quantidade
    return movimentacao


# --- Inventário -----------------------------------------------------------------


@transaction.atomic
def ajustar_inventario(
    *, material_id: int, quantidade_contada: int, justificativa: str, usuario: Usuario
) -> Movimentacao:
    """Acerta o saldo pela contagem física. A diferença vira um lançamento de ajuste."""
    _exigir_operador(usuario)
    justificativa = justificativa.strip()
    if len(justificativa) < 10:
        raise RegraNegocioError("Explique o motivo do ajuste (mínimo de 10 caracteres).")
    if quantidade_contada < 0:
        raise RegraNegocioError("A quantidade contada não pode ser negativa.")
    hoje = timezone.localdate()
    garantir_competencia_aberta(hoje)

    material = travar_materiais([material_id])[material_id]
    diferenca = quantidade_contada - material.quantidade_em_estoque
    if diferenca == 0:
        raise RegraNegocioError("A contagem confere com o saldo: nenhum ajuste é necessário.")

    posicao = material.posicao()
    if diferenca > 0:
        # Sobra de inventário entra pelo custo médio atual (não distorce a média)
        nova = posicao.com_entrada(diferenca, posicao.custo_medio)
        tipo = TipoMovimentacao.AJUSTE_ENTRADA
    else:
        nova = posicao.com_saida(-diferenca)
        tipo = TipoMovimentacao.AJUSTE_SAIDA

    movimentacao = Movimentacao.objects.create(
        material=material,
        tipo=tipo,
        data=hoje,
        quantidade=abs(diferenca),
        custo_unitario=posicao.custo_medio,
        valor_total=posicao.valor_saida(abs(diferenca)),
        saldo_quantidade=nova.quantidade,
        saldo_custo_medio=nova.custo_medio,
        usuario=usuario,
        observacao=justificativa,
    )
    material.quantidade_em_estoque = nova.quantidade
    material.custo_medio = nova.custo_medio
    material.save(update_fields=["quantidade_em_estoque", "custo_medio", "atualizado_em"])
    return movimentacao


# --- Fechamento mensal ----------------------------------------------------------


@dataclass(frozen=True)
class ResumoCompetencia:
    competencia: Competencia
    valor_entradas: Decimal
    valor_saidas: Decimal
    valor_ajustes: Decimal
    valor_estoque: Decimal


def _soma(tipo: TipoMovimentacao, competencia: Competencia) -> Decimal:
    total = Movimentacao.objects.filter(
        tipo=tipo, data__range=(competencia.primeiro_dia, competencia.ultimo_dia)
    ).aggregate(total=Sum("valor_total"))["total"]
    return total or ZERO


def resumo_competencia(competencia: Competencia) -> ResumoCompetencia:
    # Valor do estoque ao fim do mês = tudo que entrou − tudo que saiu, em reais, ATÉ a data.
    # Pela data (e não pelo último saldo do kardex, que segue a ordem de lançamento), uma
    # entrada lançada com data retroativa não "vaza" para meses anteriores.
    sinal = Case(
        When(tipo__in=TIPOS_ENTRADA, then=F("valor_total")),
        default=-F("valor_total"),
        output_field=DecimalField(),
    )
    valor_estoque = Movimentacao.objects.filter(data__lte=competencia.ultimo_dia).aggregate(total=Sum(sinal))[
        "total"
    ]
    return ResumoCompetencia(
        competencia=competencia,
        valor_entradas=_soma(TipoMovimentacao.ENTRADA, competencia),
        valor_saidas=_soma(TipoMovimentacao.SAIDA, competencia),
        valor_ajustes=_soma(TipoMovimentacao.AJUSTE_ENTRADA, competencia)
        - _soma(TipoMovimentacao.AJUSTE_SAIDA, competencia),
        valor_estoque=valor_estoque or ZERO,
    )


def primeira_competencia_com_movimento() -> Competencia | None:
    primeira = Movimentacao.objects.order_by("data").values_list("data", flat=True).first()
    return Competencia.de_data(primeira) if primeira else None


@transaction.atomic
def fechar_competencia(
    competencia: Competencia, usuario: Usuario, agora: datetime | None = None
) -> FechamentoCompetencia:
    if not usuario.eh_gestor:
        raise AcessoNegadoError("Somente o gestor fecha competências.")
    hoje = timezone.localdate(agora) if agora else timezone.localdate()
    validar_fechamento(competencia, hoje, competencias_fechadas(), primeira_competencia_com_movimento())
    resumo = resumo_competencia(competencia)
    return FechamentoCompetencia.objects.create(
        competencia=str(competencia),
        fechado_por=usuario,
        valor_entradas=resumo.valor_entradas,
        valor_saidas=resumo.valor_saidas,
        valor_ajustes=resumo.valor_ajustes,
        valor_estoque=resumo.valor_estoque,
    )


def competencias_para_fechar() -> list[Competencia]:
    """Meses encerrados e ainda abertos, do mais antigo ao mais recente."""
    primeira = primeira_competencia_com_movimento()
    if primeira is None:
        return []
    atual = Competencia.de_data(timezone.localdate())
    fechadas = competencias_fechadas()
    resultado: list[Competencia] = []
    c = primeira
    while c < atual:
        if c not in fechadas:
            resultado.append(c)
        c = c.proxima()
    return resultado


# --- Conferência ---------------------------------------------------------------


def divergencias_de_saldo() -> list[tuple[Material, int, int]]:
    """Materiais cujo saldo em cache difere do último saldo do kardex.

    DISTINCT ON (material_id) é do PostgreSQL: pega uma linha (a mais recente) por material.
    """
    ultimo = dict(
        Movimentacao.objects.order_by("material_id", "-id")
        .distinct("material_id")
        .values_list("material_id", "saldo_quantidade")
    )
    divergentes = []
    for material in Material.objects.all():
        esperado = ultimo.get(material.pk, 0)
        if material.quantidade_em_estoque != esperado:
            divergentes.append((material, material.quantidade_em_estoque, esperado))
    return divergentes
