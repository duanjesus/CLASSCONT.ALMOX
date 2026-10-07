"""Concorrência de verdade: threads com conexões próprias disputando as mesmas linhas.

Os outros testes rodam dentro de uma transação que é desfeita no fim; aqui é
preciso ``transaction=True`` para que cada thread enxergue os dados já gravados
(COMMIT real) e para que os ``SELECT ... FOR UPDATE`` de fato esperem uns pelos outros.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection
from django.utils import timezone

from dominio.excecoes import RegraNegocioError, TransicaoInvalidaError
from dominio.requisicao import Status
from estoque.models import Entrada, Movimentacao, TipoMovimentacao
from estoque.services import ItemNota, registrar_entrada
from requisicoes import services
from requisicoes.models import ItemRequisicao, Requisicao
from tests.fabricas import montar_cenario, requisicao_aprovada, requisicao_enviada

pytestmark = pytest.mark.django_db(transaction=True)


def ao_mesmo_tempo(*tarefas: Callable[[], Any]) -> list[Any]:
    """Dispara as tarefas juntas (barreira) e devolve o resultado ou a exceção de cada uma."""
    largada = threading.Barrier(len(tarefas))

    def executar(tarefa: Callable[[], Any]) -> Any:
        try:
            largada.wait(timeout=10)
            return tarefa()
        except Exception as erro:
            return erro
        finally:
            connection.close()  # cada thread tem a própria conexão: devolve ao pool

    with ThreadPoolExecutor(max_workers=len(tarefas)) as pool:
        return list(pool.map(executar, tarefas))


def test_aprovacoes_simultaneas_nunca_reservam_mais_que_o_estoque() -> None:
    c = montar_cenario()  # 50 resmas de papel
    requisicoes = [requisicao_enviada(c.ana, (c.papel, 10)) for _ in range(8)]  # pedem 80 no total

    resultados = ao_mesmo_tempo(*[lambda r=r: services.aprovar(r.pk, c.gestor) for r in requisicoes])

    assert [r for r in resultados if isinstance(r, Exception)] == []
    c.recarregar()
    reservado_nos_itens = sum(ItemRequisicao.objects.values_list("quantidade_reservada", flat=True))
    # Sem o FOR UPDATE, cada aprovação leria "50 disponíveis" e todas reservariam 10 (80 > 50)
    assert c.papel.quantidade_reservada == reservado_nos_itens == 50
    assert c.papel.disponivel == 0


def test_a_mesma_requisicao_atendida_duas_vezes_so_baixa_o_estoque_uma() -> None:
    c = montar_cenario()
    r = requisicao_aprovada(c.ana, c.chefe_sti, (c.papel, 10))

    resultados = ao_mesmo_tempo(
        lambda: services.atender(r.pk, c.almox),
        lambda: services.atender(r.pk, c.gestor),
    )

    erros = [x for x in resultados if isinstance(x, Exception)]
    assert len(erros) == 1
    assert isinstance(erros[0], TransicaoInvalidaError)  # quem chegou depois viu "já atendida"
    c.recarregar()
    assert (c.papel.quantidade_em_estoque, c.papel.quantidade_reservada) == (40, 0)
    assert Movimentacao.objects.filter(tipo=TipoMovimentacao.SAIDA).count() == 1
    assert Requisicao.objects.get(pk=r.pk).status == Status.ATENDIDA


def test_atendimentos_simultaneos_de_requisicoes_diferentes_fecham_a_conta() -> None:
    c = montar_cenario()
    requisicoes = [requisicao_aprovada(c.ana, c.gestor, (c.papel, 10)) for _ in range(5)]  # reservam os 50

    resultados = ao_mesmo_tempo(*[lambda r=r: services.atender(r.pk, c.almox) for r in requisicoes])

    assert [r for r in resultados if isinstance(r, Exception)] == []
    c.recarregar()
    assert (c.papel.quantidade_em_estoque, c.papel.quantidade_reservada) == (0, 0)
    # O kardex conta a mesma história: os saldos após cada saída são 40, 30, 20, 10, 0, sem repetir
    saldos = Movimentacao.objects.filter(tipo=TipoMovimentacao.SAIDA).values_list(
        "saldo_quantidade", flat=True
    )
    assert sorted(saldos, reverse=True) == [40, 30, 20, 10, 0]


def test_a_mesma_nota_fiscal_lancada_duas_vezes_ao_mesmo_tempo() -> None:
    c = montar_cenario()

    def lancar() -> Entrada:
        return registrar_entrada(
            fornecedor=c.fornecedor,
            numero_nota="555",
            data_recebimento=timezone.localdate(),
            usuario=c.almox,
            itens=[ItemNota(c.papel.pk, 10, Decimal("20.00"))],
        )

    resultados = ao_mesmo_tempo(lancar, lancar)

    erros = [x for x in resultados if isinstance(x, Exception)]
    assert len(erros) == 1
    assert isinstance(erros[0], RegraNegocioError)  # mensagem amigável, não um erro 500
    c.recarregar()
    assert c.papel.quantidade_em_estoque == 60  # entrou uma vez só
