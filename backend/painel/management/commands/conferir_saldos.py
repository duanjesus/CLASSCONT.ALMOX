from typing import Any

from django.core.management.base import BaseCommand, CommandError

from estoque.services import divergencias_de_saldo


class Command(BaseCommand):
    help = "Confere se o saldo gravado em cada material bate com o último saldo do kardex."

    def handle(self, *args: Any, **opcoes: Any) -> None:
        divergencias = divergencias_de_saldo()
        for material, gravado, kardex in divergencias:
            self.stderr.write(f"{material.codigo}: material diz {gravado}, kardex diz {kardex}")
        if divergencias:
            raise CommandError(f"{len(divergencias)} material(is) com saldo divergente.")
        self.stdout.write(self.style.SUCCESS("Saldos conferidos: material e kardex batem."))
