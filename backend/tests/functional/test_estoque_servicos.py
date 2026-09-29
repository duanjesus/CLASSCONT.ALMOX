from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import time_machine
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from dominio.competencia import Competencia
from dominio.excecoes import AcessoNegadoError, CompetenciaFechadaError, RegraNegocioError
from estoque.models import Material, Movimentacao, MovimentacaoImutavelError, TipoMovimentacao
from estoque.services import ItemNota, ajustar_inventario, fechar_competencia, registrar_entrada
from tests.fabricas import Cenario

pytestmark = pytest.mark.django_db


def _entrada(c: Cenario, nf: str, qtd: int, valor: str, dia: object = None) -> None:
    registrar_entrada(
        fornecedor=c.fornecedor,
        numero_nota=nf,
        data_recebimento=dia or timezone.localdate(),  # type: ignore[arg-type]
        usuario=c.almox,
        itens=[ItemNota(c.papel.pk, qtd, Decimal(valor))],
    )


def test_entrada_atualiza_saldo_custo_medio_e_kardex(cenario: Cenario) -> None:
    # já havia 50 a R$ 20; entram 50 a R$ 26 → média R$ 23
    _entrada(cenario, "2", 50, "26.00")
    cenario.recarregar()
    assert cenario.papel.quantidade_em_estoque == 100
    assert cenario.papel.custo_medio == Decimal("23.0000")
    ultima = Movimentacao.objects.filter(material=cenario.papel).last()
    assert ultima is not None
    assert (ultima.tipo, ultima.saldo_quantidade, ultima.valor_total) == (
        TipoMovimentacao.ENTRADA,
        100,
        Decimal("1300.00"),
    )


def test_nota_fiscal_nao_se_repete_para_o_mesmo_fornecedor(cenario: Cenario) -> None:
    with pytest.raises(RegraNegocioError, match="já foi registrada"):
        _entrada(cenario, "1", 1, "1.00")


def test_data_de_recebimento_futura_e_recusada(cenario: Cenario) -> None:
    with pytest.raises(RegraNegocioError, match="futura"):
        _entrada(cenario, "9", 1, "1.00", dia=timezone.localdate() + timedelta(days=1))


def test_servidor_nao_movimenta_estoque(cenario: Cenario) -> None:
    with pytest.raises(AcessoNegadoError):
        registrar_entrada(
            fornecedor=cenario.fornecedor,
            numero_nota="X",
            data_recebimento=timezone.localdate(),
            usuario=cenario.ana,
            itens=[ItemNota(cenario.papel.pk, 1, Decimal("1"))],
        )


def test_ajuste_de_inventario_lanca_a_diferenca(cenario: Cenario) -> None:
    mov = ajustar_inventario(
        material_id=cenario.papel.pk,
        quantidade_contada=47,
        justificativa="Três resmas molhadas",
        usuario=cenario.almox,
    )
    assert (mov.tipo, mov.quantidade, mov.saldo_quantidade) == (TipoMovimentacao.AJUSTE_SAIDA, 3, 47)
    assert mov.valor_total == Decimal("60.00")  # 3 × custo médio de R$ 20

    mov = ajustar_inventario(
        material_id=cenario.papel.pk,
        quantidade_contada=49,
        justificativa="Achadas no depósito B",
        usuario=cenario.almox,
    )
    assert (mov.tipo, mov.saldo_quantidade, mov.saldo_custo_medio) == (
        TipoMovimentacao.AJUSTE_ENTRADA,
        49,
        Decimal("20"),
    )


@pytest.mark.parametrize(
    ("contada", "justificativa", "mensagem"),
    [(50, "Contagem de rotina", "confere"), (40, "curta", "motivo"), (-1, "Contagem de rotina", "negativa")],
)
def test_ajustes_invalidos(cenario: Cenario, contada: int, justificativa: str, mensagem: str) -> None:
    with pytest.raises(RegraNegocioError, match=mensagem):
        ajustar_inventario(
            material_id=cenario.papel.pk,
            quantidade_contada=contada,
            justificativa=justificativa,
            usuario=cenario.almox,
        )


def test_kardex_e_imutavel(cenario: Cenario) -> None:
    mov = Movimentacao.objects.first()
    assert mov is not None
    mov.quantidade = 999
    with pytest.raises(MovimentacaoImutavelError):
        mov.save()
    with pytest.raises(MovimentacaoImutavelError):
        mov.delete()


def test_banco_recusa_estoque_negativo_mesmo_com_bug_no_codigo(cenario: Cenario) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Material.objects.filter(pk=cenario.papel.pk).update(quantidade_em_estoque=-1)


def test_fechamento_bloqueia_lancamento_retroativo(cenario: Cenario) -> None:
    hoje = timezone.localdate()
    mes_passado = Competencia.de_data(hoje).anterior()
    _entrada(cenario, "2", 10, "20.00", dia=mes_passado.primeiro_dia)

    fechamento = fechar_competencia(mes_passado, cenario.gestor)
    assert fechamento.valor_entradas == Decimal("200.00")
    assert fechamento.valor_estoque == Decimal("200.00")

    with pytest.raises(CompetenciaFechadaError):
        _entrada(cenario, "3", 1, "20.00", dia=mes_passado.ultimo_dia)
    with pytest.raises(RegraNegocioError, match="já está fechada"):
        fechar_competencia(mes_passado, cenario.gestor)


def test_somente_o_gestor_fecha_e_nunca_o_mes_corrente(cenario: Cenario) -> None:
    atual = Competencia.de_data(timezone.localdate())
    with pytest.raises(AcessoNegadoError):
        fechar_competencia(atual.anterior(), cenario.almox)
    with pytest.raises(RegraNegocioError, match="encerradas"):
        fechar_competencia(atual, cenario.gestor)


def test_fechamento_exige_ordem(cenario: Cenario) -> None:
    hoje = timezone.localdate()
    dois_meses = Competencia.de_data(hoje).anterior().anterior()
    _entrada(cenario, "2", 10, "20.00", dia=dois_meses.primeiro_dia)
    with pytest.raises(RegraNegocioError, match="Feche antes"):
        fechar_competencia(dois_meses.proxima(), cenario.gestor)


def test_conferencia_de_saldos(cenario: Cenario, capsys: pytest.CaptureFixture[str]) -> None:
    call_command("conferir_saldos")
    assert "batem" in capsys.readouterr().out


def test_carga_de_demonstracao_e_coerente(db: None) -> None:
    # A carga passa pelos serviços reais; no fim o kardex precisa bater com os saldos.
    with time_machine.travel(timezone.make_aware(datetime(2026, 9, 29, 15, 0)), tick=False):
        call_command("carregar_demo")
        call_command("conferir_saldos")
    assert Movimentacao.objects.filter(tipo=TipoMovimentacao.SAIDA).exists()
