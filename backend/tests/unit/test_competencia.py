from datetime import date

import pytest

from dominio.competencia import Competencia, validar_fechamento, validar_lancamento
from dominio.excecoes import CompetenciaFechadaError, CompetenciaInvalidaError, RegraNegocioError

SET_2026 = Competencia(2026, 9)


def test_parse_e_formatacao() -> None:
    assert Competencia.de_texto("2026-09") == SET_2026
    assert str(SET_2026) == "2026-09"
    assert SET_2026.nome == "setembro de 2026"


@pytest.mark.parametrize("texto", ["2026-13", "2026-9", "setembro", "1999-01"])
def test_competencia_invalida(texto: str) -> None:
    with pytest.raises(CompetenciaInvalidaError):
        Competencia.de_texto(texto)


def test_navegacao_vira_o_ano() -> None:
    assert Competencia(2026, 1).anterior() == Competencia(2025, 12)
    assert Competencia(2025, 12).proxima() == Competencia(2026, 1)


def test_limites_do_mes_inclusive_ano_bissexto() -> None:
    assert Competencia(2028, 2).ultimo_dia == date(2028, 2, 29)
    assert Competencia(2026, 2).ultimo_dia == date(2026, 2, 28)
    assert SET_2026.contem(date(2026, 9, 30))
    assert not SET_2026.contem(date(2026, 10, 1))


def test_value_object_e_comparavel() -> None:
    assert Competencia(2026, 8) < SET_2026 < Competencia(2027, 1)
    assert len({Competencia(2026, 9), Competencia.de_texto("2026-09")}) == 1


def test_lancamento_em_mes_fechado_e_bloqueado() -> None:
    validar_lancamento(date(2026, 9, 10), fechadas={Competencia(2026, 8)})
    with pytest.raises(CompetenciaFechadaError, match="agosto de 2026"):
        validar_lancamento(date(2026, 8, 31), fechadas={Competencia(2026, 8)})


HOJE = date(2026, 9, 29)


def test_fecha_mes_encerrado() -> None:
    validar_fechamento(
        Competencia(2026, 8), HOJE, fechadas=set(), primeira_com_movimento=Competencia(2026, 8)
    )


def test_nao_fecha_mes_corrente_nem_futuro() -> None:
    for alvo in (SET_2026, Competencia(2026, 10)):
        with pytest.raises(RegraNegocioError, match="encerradas"):
            validar_fechamento(alvo, HOJE, set(), None)


def test_fecha_em_ordem() -> None:
    with pytest.raises(RegraNegocioError, match="julho de 2026"):
        validar_fechamento(Competencia(2026, 8), HOJE, set(), primeira_com_movimento=Competencia(2026, 6))
    validar_fechamento(
        Competencia(2026, 8), HOJE, {Competencia(2026, 6), Competencia(2026, 7)}, Competencia(2026, 6)
    )


def test_nao_fecha_duas_vezes() -> None:
    with pytest.raises(RegraNegocioError, match="já está fechada"):
        validar_fechamento(Competencia(2026, 8), HOJE, {Competencia(2026, 8)}, Competencia(2026, 8))
