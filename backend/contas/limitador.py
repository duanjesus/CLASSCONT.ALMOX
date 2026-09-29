"""Proteção contra força bruta no login (API e painel).

Conta só as tentativas **erradas** por e-mail + IP, numa janela de tempo. Ao
atingir o limite, novas tentativas são recusadas até a janela expirar. Um login
certo zera o contador.
"""

from __future__ import annotations

import hashlib
from typing import cast

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest


def _config() -> tuple[int, int]:
    almox = cast(dict[str, int | str], settings.ALMOX)
    return int(almox["LOGIN_MAX_TENTATIVAS"]), int(almox["LOGIN_JANELA_SEGUNDOS"])


def chave_login(email: str, request: HttpRequest) -> str:
    ip = request.META.get("REMOTE_ADDR", "")
    bruto = f"{email.strip().lower()}|{ip}"
    return "login-falhas:" + hashlib.sha256(bruto.encode()).hexdigest()


def bloqueado(chave: str) -> bool:
    maximo, _ = _config()
    return int(cache.get(chave, 0)) >= maximo


def registrar_falha(chave: str) -> None:
    _, janela = _config()
    # add() só cria se não existir; incr() é atômico no Redis/Memcached
    if not cache.add(chave, 1, timeout=janela):
        try:
            cache.incr(chave)
        except ValueError:  # expirou entre o add e o incr
            cache.set(chave, 1, timeout=janela)


def limpar(chave: str) -> None:
    cache.delete(chave)


MENSAGEM_BLOQUEIO = "Muitas tentativas de login. Aguarde um minuto e tente novamente."
