class RegraNegocioError(Exception):
    """Violação de regra de negócio. A mensagem é segura para exibir ao usuário (API → 422)."""


class SaldoInsuficienteError(RegraNegocioError):
    pass


class TransicaoInvalidaError(RegraNegocioError):
    pass


class CompetenciaInvalidaError(RegraNegocioError):
    pass


class CompetenciaFechadaError(RegraNegocioError):
    pass


class AcessoNegadoError(Exception):
    """O usuário está autenticado, mas o perfil dele não permite a ação (API → 403)."""

    def __init__(self, mensagem: str = "Você não tem permissão para esta ação.") -> None:
        super().__init__(mensagem)
