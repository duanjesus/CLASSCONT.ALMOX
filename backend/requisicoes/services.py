"""Casos de uso das requisições de material.

Cada serviço: trava a requisição (``SELECT ... FOR UPDATE``) para que duas
pessoas não avaliem/atendam a mesma requisição ao mesmo tempo, valida a
transição de status no domínio, confere a permissão e grava o histórico.
E-mails saem com ``transaction.on_commit``: só depois que o banco confirmou.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import partial

from django.db import transaction
from django.db.models import F, Q, QuerySet, Sum
from django.utils import timezone

from contas.models import Setor, Usuario
from dominio.atendimento import ItemParaAtender, planejar_atendimento, quantidade_reservavel
from dominio.competencia import Competencia
from dominio.cota import SituacaoCota
from dominio.dinheiro import ZERO, formatar_moeda, valor_de
from dominio.excecoes import AcessoNegadoError, RegraNegocioError
from dominio.requisicao import Acao, Status, transicionar, validar_quantidades_aprovadas
from estoque.models import Material, Movimentacao, TipoMovimentacao
from estoque.services import garantir_competencia_aberta, registrar_saida, travar_materiais
from requisicoes import notificacoes
from requisicoes.models import HistoricoRequisicao, ItemRequisicao, Requisicao
from requisicoes.permissoes import pode_atender, pode_avaliar, pode_cancelar, pode_editar


@dataclass(frozen=True)
class ItemPedido:
    material_id: int
    quantidade: int


def _travar(requisicao_id: int) -> Requisicao:
    return (
        Requisicao.objects.select_for_update(of=("self",))
        .select_related("setor", "requisitante")
        .get(pk=requisicao_id)
    )


def _historico(
    requisicao: Requisicao,
    de: Status | None,
    para: Status,
    usuario: Usuario,
    agora: datetime,
    observacao: str = "",
) -> None:
    HistoricoRequisicao.objects.create(
        requisicao=requisicao,
        de_status=de.value if de else "",
        para_status=para.value,
        usuario=usuario,
        quando=agora,
        observacao=observacao,
    )


def _validar_itens(itens: Sequence[ItemPedido]) -> None:
    if not itens:
        raise RegraNegocioError("Inclua ao menos um material na requisição.")
    ids = [i.material_id for i in itens]
    if len(set(ids)) != len(ids):
        raise RegraNegocioError(
            "O mesmo material aparece mais de uma vez: ajuste a quantidade em um só item."
        )
    materiais = Material.objects.in_bulk(ids)
    for item in itens:
        material = materiais.get(item.material_id)
        if material is None or not material.ativo:
            raise RegraNegocioError("Há um material inexistente ou inativo na requisição.")
        if item.quantidade <= 0:
            raise RegraNegocioError(f"{material.descricao}: a quantidade deve ser maior que zero.")
        if material.estoque_maximo and item.quantidade > material.estoque_maximo:
            raise RegraNegocioError(
                f"{material.descricao}: a quantidade pedida ({item.quantidade}) passa do "
                f"estoque máximo do material ({material.estoque_maximo})."
            )


def _gravar_itens(requisicao: Requisicao, itens: Sequence[ItemPedido]) -> None:
    ItemRequisicao.objects.bulk_create(
        ItemRequisicao(requisicao=requisicao, material_id=i.material_id, quantidade_solicitada=i.quantidade)
        for i in itens
    )


# --- Criação e edição (requisitante) --------------------------------------------


@transaction.atomic
def criar_requisicao(
    *,
    requisitante: Usuario,
    itens: Sequence[ItemPedido],
    finalidade: str = "",
    agora: datetime | None = None,
) -> Requisicao:
    agora = agora or timezone.now()
    if requisitante.setor_id is None:
        raise RegraNegocioError("Seu cadastro não tem setor: procure a gestão de pessoas.")
    _validar_itens(itens)
    requisicao = Requisicao.objects.create(
        requisitante=requisitante,
        setor_id=requisitante.setor_id,
        finalidade=finalidade.strip(),
        criado_em=agora,
    )
    _gravar_itens(requisicao, itens)
    _historico(requisicao, None, Status.RASCUNHO, requisitante, agora)
    return requisicao


@transaction.atomic
def atualizar_rascunho(
    requisicao_id: int, usuario: Usuario, itens: Sequence[ItemPedido], finalidade: str = ""
) -> Requisicao:
    requisicao = _travar(requisicao_id)
    if not pode_editar(usuario, requisicao):
        raise AcessoNegadoError("Só o requisitante altera a requisição, e apenas enquanto é rascunho.")
    _validar_itens(itens)
    requisicao.itens.all().delete()
    _gravar_itens(requisicao, itens)
    requisicao.finalidade = finalidade.strip()
    requisicao.save(update_fields=["finalidade"])
    return requisicao


@transaction.atomic
def enviar(requisicao_id: int, usuario: Usuario, agora: datetime | None = None) -> Requisicao:
    agora = agora or timezone.now()
    requisicao = _travar(requisicao_id)
    novo = transicionar(requisicao.status_enum, Acao.ENVIAR)
    if not pode_editar(usuario, requisicao):
        raise AcessoNegadoError("Só o requisitante envia a requisição.")
    if not requisicao.itens.exists():
        raise RegraNegocioError("Inclua ao menos um material antes de enviar.")
    _historico(requisicao, requisicao.status_enum, novo, usuario, agora)
    requisicao.status = novo
    requisicao.enviado_em = agora
    requisicao.save(update_fields=["status", "enviado_em"])
    return requisicao


# --- Avaliação (chefia / gestor) ------------------------------------------------


def situacao_cota(setor: Setor, competencia: Competencia, excluir_id: int | None = None) -> SituacaoCota:
    consumido = (
        Movimentacao.objects.filter(
            tipo=TipoMovimentacao.SAIDA,
            setor=setor,
            data__range=(competencia.primeiro_dia, competencia.ultimo_dia),
        ).aggregate(total=Sum("valor_total"))["total"]
        or ZERO
    )
    aprovados = ItemRequisicao.objects.filter(
        requisicao__setor=setor, requisicao__status=Status.APROVADA
    ).select_related("material")
    if excluir_id is not None:
        aprovados = aprovados.exclude(requisicao_id=excluir_id)
    comprometido = sum((valor_de(i.quantidade_vigente, i.material.custo_medio) for i in aprovados), ZERO)
    return SituacaoCota(cota=setor.cota_mensal, consumido=consumido, comprometido=comprometido)


def pendentes_de_avaliacao(usuario: Usuario) -> QuerySet[Requisicao]:
    """O que este usuário tem para aprovar (nunca inclui as próprias requisições)."""
    condicao = Q(status=Status.ENVIADA, setor_id__in=usuario.ids_setores_chefiados)
    if usuario.eh_gestor:
        condicao |= Q(status=Status.AGUARDANDO_GESTOR)
        # Requisições do próprio chefe (ou de setor sem chefe) sobem para o gestor
        condicao |= Q(status=Status.ENVIADA) & (
            Q(setor__chefe=F("requisitante")) | Q(setor__chefe__isnull=True)
        )
    return Requisicao.objects.filter(condicao).exclude(requisitante=usuario)


def _exigir_avaliador(usuario: Usuario, requisicao: Requisicao) -> None:
    if pode_avaliar(usuario, requisicao):
        return
    # A chefia já aprovou e a cota estourou: quem ainda está com a tela antiga aberta
    # precisa saber que a vez agora é do gestor, não que "avaliou a própria".
    if requisicao.status_enum == Status.AGUARDANDO_GESTOR and not usuario.eh_gestor:
        raise AcessoNegadoError(
            "A chefia já aprovou esta requisição e ela passou da cota do setor: "
            "agora só o gestor pode autorizar ou recusar."
        )
    raise AcessoNegadoError(
        "Esta requisição é avaliada pela chefia do setor ou pelo gestor, e ninguém avalia a própria."
    )


@transaction.atomic
def aprovar(
    requisicao_id: int,
    usuario: Usuario,
    quantidades: Mapping[int, int] | None = None,
    observacao: str = "",
    agora: datetime | None = None,
) -> Requisicao:
    agora = agora or timezone.now()
    requisicao = _travar(requisicao_id)
    status = requisicao.status_enum
    transicionar(status, Acao.APROVAR)  # valida o status antes de tudo
    _exigir_avaliador(usuario, requisicao)

    itens = list(requisicao.itens.select_related("material").order_by("material_id"))
    aprovadas = validar_quantidades_aprovadas({i.pk: i.quantidade_vigente for i in itens}, quantidades or {})
    for item in itens:
        item.quantidade_aprovada = aprovadas[item.pk]

    # Chefia aprovando: confere a cota do setor. Estourou → sobe para o gestor.
    if status == Status.ENVIADA and not usuario.eh_gestor:
        valor = sum((valor_de(i.quantidade_vigente, i.material.custo_medio) for i in itens), ZERO)
        cota = situacao_cota(requisicao.setor, Competencia.de_data(timezone.localdate(agora)), requisicao.pk)
        if not cota.comporta(valor):
            novo = transicionar(status, Acao.ENCAMINHAR_GESTOR)
            ItemRequisicao.objects.bulk_update(itens, ["quantidade_aprovada"])
            nota = (
                f"Aprovada pela chefia, mas passa a cota mensal do setor em "
                f"{formatar_moeda(cota.excedente(valor))}. "
                "Aguardando autorização do gestor."
            )
            _historico(requisicao, status, novo, usuario, agora, " ".join(filter(None, [observacao, nota])))
            requisicao.status = novo
            requisicao.save(update_fields=["status"])
            transaction.on_commit(partial(notificacoes.avisar_gestores_cota, requisicao.pk))
            return requisicao

    novo = transicionar(status, Acao.APROVAR)
    materiais = travar_materiais([i.material_id for i in itens])
    for item in itens:
        material = materiais[item.material_id]
        reserva = quantidade_reservavel(item.quantidade_vigente, material.saldo())
        item.quantidade_reservada = reserva
        material.quantidade_reservada += reserva
        material.save(update_fields=["quantidade_reservada", "atualizado_em"])
    ItemRequisicao.objects.bulk_update(itens, ["quantidade_aprovada", "quantidade_reservada"])

    _historico(requisicao, status, novo, usuario, agora, observacao.strip())
    requisicao.status = novo
    requisicao.save(update_fields=["status"])
    transaction.on_commit(partial(notificacoes.avisar_requisitante, requisicao.pk))
    return requisicao


@transaction.atomic
def recusar(requisicao_id: int, usuario: Usuario, motivo: str, agora: datetime | None = None) -> Requisicao:
    agora = agora or timezone.now()
    requisicao = _travar(requisicao_id)
    status = requisicao.status_enum
    novo = transicionar(status, Acao.RECUSAR)
    _exigir_avaliador(usuario, requisicao)
    motivo = motivo.strip()
    if len(motivo) < 5:
        raise RegraNegocioError("A recusa exige um motivo.")
    _historico(requisicao, status, novo, usuario, agora, motivo)
    requisicao.status = novo
    requisicao.save(update_fields=["status"])
    transaction.on_commit(partial(notificacoes.avisar_requisitante, requisicao.pk))
    return requisicao


# --- Cancelamento ---------------------------------------------------------------


def _liberar_reservas(requisicao: Requisicao) -> None:
    itens = list(requisicao.itens.filter(quantidade_reservada__gt=0).order_by("material_id"))
    materiais = travar_materiais([i.material_id for i in itens])
    for item in itens:
        material = materiais[item.material_id]
        material.quantidade_reservada = max(0, material.quantidade_reservada - item.quantidade_reservada)
        material.save(update_fields=["quantidade_reservada", "atualizado_em"])
        item.quantidade_reservada = 0
    ItemRequisicao.objects.bulk_update(itens, ["quantidade_reservada"])


@transaction.atomic
def cancelar(
    requisicao_id: int, usuario: Usuario, motivo: str = "", agora: datetime | None = None
) -> Requisicao:
    agora = agora or timezone.now()
    requisicao = _travar(requisicao_id)
    status = requisicao.status_enum
    novo = transicionar(status, Acao.CANCELAR)
    if not pode_cancelar(usuario, requisicao):
        raise AcessoNegadoError("Você não pode cancelar esta requisição.")
    if status == Status.APROVADA:
        _liberar_reservas(requisicao)
    _historico(requisicao, status, novo, usuario, agora, motivo.strip())
    requisicao.status = novo
    requisicao.save(update_fields=["status"])
    if requisicao.requisitante_id != usuario.pk:
        transaction.on_commit(partial(notificacoes.avisar_requisitante, requisicao.pk))
    return requisicao


# --- Atendimento (almoxarifado) -------------------------------------------------


@transaction.atomic
def atender(
    requisicao_id: int,
    usuario: Usuario,
    quantidades: Mapping[int, int] | None = None,
    agora: datetime | None = None,
) -> Requisicao:
    """Entrega o material: baixa o estoque, consome a reserva e grava as saídas no kardex.

    ``quantidades`` (item → quantidade) é opcional: por padrão entrega o máximo possível.
    Se algum item sair abaixo do aprovado, o atendimento é parcial e o restante é liberado.
    """
    agora = agora or timezone.now()
    quantidades = quantidades or {}
    requisicao = _travar(requisicao_id)
    status = requisicao.status_enum
    transicionar(status, Acao.ATENDER)
    if not pode_atender(usuario, requisicao):
        raise AcessoNegadoError("O almoxarifado atende requisições, mas não as próprias.")
    dia = timezone.localdate(agora)
    garantir_competencia_aberta(dia)

    itens = list(requisicao.itens.select_related("material").order_by("material_id"))
    if set(quantidades) - {i.pk for i in itens}:
        raise RegraNegocioError("Há itens que não pertencem a esta requisição.")
    materiais = travar_materiais([i.material_id for i in itens])
    plano = planejar_atendimento(
        [
            ItemParaAtender(
                chave=i.pk,
                descricao=i.material.descricao,
                aprovada=i.quantidade_vigente,
                reservada=i.quantidade_reservada,
                saldo=materiais[i.material_id].saldo(),
                informada=quantidades.get(i.pk),
            )
            for i in itens
        ]
    )

    total = ZERO
    para_repor: list[int] = []
    for item in itens:
        material = materiais[item.material_id]
        quantidade = plano.quantidades[item.pk]
        material.quantidade_reservada = max(0, material.quantidade_reservada - item.quantidade_reservada)
        if quantidade > 0:
            saida = registrar_saida(
                material=material,
                quantidade=quantidade,
                usuario=usuario,
                setor=requisicao.setor,
                requisicao_id=requisicao.pk,
                dia=dia,
            )
            total += saida.valor_total
        material.save(update_fields=["quantidade_em_estoque", "quantidade_reservada", "atualizado_em"])
        item.quantidade_atendida = quantidade
        item.custo_unitario = material.custo_medio
        item.quantidade_reservada = 0
        if material.precisa_repor:
            para_repor.append(material.pk)
    ItemRequisicao.objects.bulk_update(
        itens, ["quantidade_atendida", "custo_unitario", "quantidade_reservada"]
    )

    novo = transicionar(status, Acao.ATENDER_PARCIALMENTE if plano.parcial else Acao.ATENDER)
    nota = "Atendimento parcial por falta de saldo; o restante foi liberado." if plano.parcial else ""
    _historico(requisicao, status, novo, usuario, agora, nota)
    requisicao.status = novo
    requisicao.atendido_em = agora
    requisicao.valor_atendido = total
    requisicao.save(update_fields=["status", "atendido_em", "valor_atendido"])

    transaction.on_commit(partial(notificacoes.avisar_requisitante, requisicao.pk))
    if para_repor:
        transaction.on_commit(partial(notificacoes.alertar_reposicao, para_repor))
    return requisicao
