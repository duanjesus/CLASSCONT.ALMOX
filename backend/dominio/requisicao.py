"""Ciclo de vida de uma requisição de material (máquina de estados)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from dominio.excecoes import RegraNegocioError, TransicaoInvalidaError


class Status(StrEnum):
    RASCUNHO = "RASCUNHO"
    ENVIADA = "ENVIADA"
    AGUARDANDO_GESTOR = "AGUARDANDO_GESTOR"
    APROVADA = "APROVADA"
    RECUSADA = "RECUSADA"
    ATENDIDA = "ATENDIDA"
    ATENDIDA_PARCIALMENTE = "ATENDIDA_PARCIALMENTE"
    CANCELADA = "CANCELADA"

    @property
    def rotulo(self) -> str:
        return ROTULOS_STATUS[self]


ROTULOS_STATUS: Final[Mapping[Status, str]] = {
    Status.RASCUNHO: "Rascunho",
    Status.ENVIADA: "Aguardando aprovação",
    Status.AGUARDANDO_GESTOR: "Aguardando gestor",
    Status.APROVADA: "Aprovada",
    Status.RECUSADA: "Recusada",
    Status.ATENDIDA: "Atendida",
    Status.ATENDIDA_PARCIALMENTE: "Atendida parcialmente",
    Status.CANCELADA: "Cancelada",
}


class Acao(StrEnum):
    ENVIAR = "ENVIAR"
    APROVAR = "APROVAR"
    ENCAMINHAR_GESTOR = "ENCAMINHAR_GESTOR"
    RECUSAR = "RECUSAR"
    ATENDER = "ATENDER"
    ATENDER_PARCIALMENTE = "ATENDER_PARCIALMENTE"
    CANCELAR = "CANCELAR"


_VERBOS: Final[Mapping[Acao, str]] = {
    Acao.ENVIAR: "enviar",
    Acao.APROVAR: "aprovar",
    Acao.ENCAMINHAR_GESTOR: "encaminhar ao gestor",
    Acao.RECUSAR: "recusar",
    Acao.ATENDER: "atender",
    Acao.ATENDER_PARCIALMENTE: "atender",
    Acao.CANCELAR: "cancelar",
}

# A tabela de transições É a regra: o que não está aqui é proibido.
TRANSICOES: Final[Mapping[Status, Mapping[Acao, Status]]] = {
    Status.RASCUNHO: {
        Acao.ENVIAR: Status.ENVIADA,
        Acao.CANCELAR: Status.CANCELADA,
    },
    Status.ENVIADA: {
        Acao.APROVAR: Status.APROVADA,
        Acao.ENCAMINHAR_GESTOR: Status.AGUARDANDO_GESTOR,
        Acao.RECUSAR: Status.RECUSADA,
        Acao.CANCELAR: Status.CANCELADA,
    },
    Status.AGUARDANDO_GESTOR: {
        Acao.APROVAR: Status.APROVADA,
        Acao.RECUSAR: Status.RECUSADA,
        Acao.CANCELAR: Status.CANCELADA,
    },
    Status.APROVADA: {
        Acao.ATENDER: Status.ATENDIDA,
        Acao.ATENDER_PARCIALMENTE: Status.ATENDIDA_PARCIALMENTE,
        Acao.CANCELAR: Status.CANCELADA,
    },
}

STATUS_FINAIS: Final = frozenset(Status) - frozenset(TRANSICOES)
STATUS_EM_AVALIACAO: Final = frozenset({Status.ENVIADA, Status.AGUARDANDO_GESTOR})


def acoes_possiveis(status: Status) -> frozenset[Acao]:
    return frozenset(TRANSICOES.get(status, {}))


def transicionar(status: Status, acao: Acao) -> Status:
    try:
        return TRANSICOES[status][acao]
    except KeyError:
        raise TransicaoInvalidaError(
            f"Não é possível {_VERBOS[acao]} uma requisição com status “{status.rotulo}”."
        ) from None


def validar_quantidades_aprovadas(tetos: Mapping[int, int], informadas: Mapping[int, int]) -> dict[int, int]:
    """Quem aprova pode reduzir as quantidades, nunca aumentar.

    ``tetos`` mapeia item → quantidade máxima (a solicitada, ou a já aprovada pela
    chefia quando o gestor revisa). Itens não informados mantêm o teto.
    Pelo menos um item precisa continuar com quantidade maior que zero.
    """
    desconhecidos = set(informadas) - set(tetos)
    if desconhecidos:
        raise RegraNegocioError("Há itens que não pertencem a esta requisição.")

    aprovadas: dict[int, int] = {}
    for item, teto in tetos.items():
        quantidade = informadas.get(item, teto)
        if quantidade < 0:
            raise RegraNegocioError("A quantidade aprovada não pode ser negativa.")
        if quantidade > teto:
            raise RegraNegocioError(f"A quantidade aprovada ({quantidade}) excede a solicitada ({teto}).")
        aprovadas[item] = quantidade

    if not any(aprovadas.values()):
        raise RegraNegocioError("Para aprovar, mantenha ao menos um item. Se nada for atendido, recuse.")
    return aprovadas
