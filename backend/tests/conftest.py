from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from tests.fabricas import Cenario, montar_cenario


@pytest.fixture(autouse=True)
def _hash_rapido(settings: pytest.FixtureRequest) -> None:
    # PBKDF2 é lento de propósito; nos testes não precisamos disso
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _cache_limpo() -> Iterator[None]:
    # O limitador de login guarda tentativas no cache: cada teste começa zerado
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def cenario(db: None) -> Cenario:
    return montar_cenario()


@pytest.fixture
def api() -> APIClient:
    return APIClient()
