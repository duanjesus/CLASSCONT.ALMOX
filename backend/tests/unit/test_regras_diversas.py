"""Cota, curva ABC, reposição, CNPJ e formatação de dinheiro."""

from decimal import Decimal

import pytest

from dominio.cnpj import cnpj_valido, completar_cnpj, formatar_cnpj
from dominio.cota import SituacaoCota
from dominio.curva_abc import ItemConsumo, classificar
from dominio.dinheiro import formatar_moeda
from dominio.reposicao import cobertura_em_dias, precisa_repor, quantidade_sugerida

# --- Cota --------------------------------------------------------------------------


def test_setor_sem_cota_comporta_qualquer_valor() -> None:
    cota = SituacaoCota(cota=None, consumido=Decimal("99999"))
    assert cota.comporta(Decimal("1000000"))
    assert cota.disponivel is None
    assert cota.excedente(Decimal("5")) == 0


def test_cota_considera_consumido_mais_comprometido() -> None:
    cota = SituacaoCota(cota=Decimal("1000"), consumido=Decimal("600"), comprometido=Decimal("300"))
    assert cota.disponivel == Decimal("100")
    assert cota.comporta(Decimal("100"))  # bater exatamente na cota é permitido
    assert not cota.comporta(Decimal("100.01"))
    assert cota.excedente(Decimal("150")) == Decimal("50")
    assert cota.percentual_utilizado == Decimal("90.00")


# --- Curva ABC ---------------------------------------------------------------------


def test_curva_abc_classifica_pelo_acumulado() -> None:
    itens = [
        ItemConsumo(1, "Toner", Decimal("700")),
        ItemConsumo(2, "Papel", Decimal("150")),
        ItemConsumo(3, "Caneta", Decimal("100")),
        ItemConsumo(4, "Clipes", Decimal("50")),
    ]
    resultado = {c.item.descricao: c.classe for c in classificar(itens)}
    # acumulado antes de cada um: 0% → A, 70% → A, 85% → B, 95% → C
    assert resultado == {"Toner": "A", "Papel": "A", "Caneta": "B", "Clipes": "C"}


def test_maior_item_e_sempre_a_mesmo_passando_de_80_porcento() -> None:
    resultado = classificar(
        [ItemConsumo(1, "Toner", Decimal("990")), ItemConsumo(2, "Clipes", Decimal("10"))]
    )
    assert [c.classe for c in resultado] == ["A", "C"]
    assert resultado[-1].percentual_acumulado == Decimal(100)


def test_curva_abc_ignora_itens_sem_consumo() -> None:
    assert classificar([ItemConsumo(1, "Parado", Decimal("0"))]) == []


# --- Reposição ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("disponivel", "minimo", "esperado"),
    [(11, 10, False), (10, 10, True), (0, 10, True), (0, 0, False)],
)
def test_ponto_de_reposicao(disponivel: int, minimo: int, esperado: bool) -> None:
    assert precisa_repor(disponivel, minimo) is esperado


def test_quantidade_sugerida_volta_ao_maximo() -> None:
    assert quantidade_sugerida(8, 100) == 92
    assert quantidade_sugerida(120, 100) == 0


def test_cobertura_em_dias() -> None:
    assert cobertura_em_dias(30, consumo_no_periodo=90, dias_do_periodo=90) == 30
    assert cobertura_em_dias(30, consumo_no_periodo=0, dias_do_periodo=90) is None


# --- CNPJ e dinheiro -----------------------------------------------------------------


def test_cnpj() -> None:
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-82")
    assert not cnpj_valido("11111111111111")
    assert completar_cnpj("112223330001") == "11222333000181"
    assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (Decimal("0"), "R$ 0,00"),
        (Decimal("1234.5"), "R$ 1.234,50"),
        (Decimal("1234567.899"), "R$ 1.234.567,90"),
        (Decimal("-50"), "−R$ 50,00"),
        (None, "—"),
    ],
)
def test_formatar_moeda(valor: Decimal | None, texto: str) -> None:
    assert formatar_moeda(valor) == texto
