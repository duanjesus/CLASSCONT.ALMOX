"""Carga de demonstração, com datas RELATIVAS a hoje (mês retrasado, passado e atual).

Tudo passa pelos serviços de verdade (entradas, requisições, atendimentos,
fechamento), então o kardex e os saldos ficam coerentes, como em produção.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from contas.models import Perfil, Setor, Usuario
from dominio.cnpj import completar_cnpj
from dominio.competencia import Competencia
from estoque.models import Categoria, Fornecedor, Material, Unidade
from estoque.services import ItemNota, ajustar_inventario, fechar_competencia, registrar_entrada
from requisicoes import services as req
from requisicoes.models import Requisicao

SENHA = "senha123"

MATERIAIS: dict[str, list[tuple[str, str, str, int, int, str]]] = {
    # categoria: [(código, descrição, unidade, mínimo, máximo, custo da 1ª compra)]
    "Material de expediente": [
        ("EXP-001", "Papel A4 75 g (resma com 500 folhas)", Unidade.RESMA, 40, 200, "27.90"),
        ("EXP-002", "Caneta esferográfica azul (caixa com 50)", Unidade.CX, 4, 20, "52.00"),
        ("EXP-003", "Grampeador de mesa 26/6", Unidade.UN, 3, 15, "38.50"),
        ("EXP-004", "Grampos 26/6 (caixa com 5.000)", Unidade.CX, 5, 30, "9.80"),
        ("EXP-005", "Clipes 2/0 (caixa com 500)", Unidade.CX, 5, 30, "6.40"),
        ("EXP-006", "Pasta suspensa kraft", Unidade.UN, 50, 300, "2.35"),
        ("EXP-007", "Envelope pardo A4", Unidade.UN, 100, 500, "0.62"),
        ("EXP-008", "Bloco de notas adesivas 76 × 76 mm", Unidade.PCT, 10, 60, "7.90"),
    ],
    "Informática": [
        ("INF-001", "Toner HP 105A (W1105A)", Unidade.UN, 3, 12, "389.00"),
        ("INF-002", "Mouse óptico USB", Unidade.UN, 5, 25, "29.90"),
        ("INF-003", "Teclado USB ABNT2", Unidade.UN, 3, 15, "54.90"),
        ("INF-004", "Cabo HDMI 2 m", Unidade.UN, 4, 20, "24.50"),
        ("INF-005", "Pen drive 32 GB", Unidade.UN, 5, 25, "36.00"),
    ],
    "Limpeza e higiene": [
        ("LIM-001", "Papel toalha interfolhado (fardo)", Unidade.PCT, 10, 60, "18.70"),
        ("LIM-002", "Sabonete líquido 5 L", Unidade.FR, 4, 20, "32.40"),
        ("LIM-003", "Álcool 70% 1 L", Unidade.FR, 12, 60, "8.90"),
    ],
    "Copa e cozinha": [
        ("COP-001", "Café torrado e moído 500 g", Unidade.PCT, 20, 120, "17.50"),
        ("COP-002", "Açúcar refinado 1 kg", Unidade.PCT, 10, 60, "4.80"),
        ("COP-003", "Copo descartável 180 ml (pacote com 100)", Unidade.PCT, 30, 150, "4.20"),
    ],
}


class Command(BaseCommand):
    help = "Apaga o banco e carrega dados de demonstração (datas relativas a hoje)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--se-vazio", action="store_true", help="Só carrega se não houver usuários.")

    def handle(self, *args: Any, **opcoes: Any) -> None:
        if opcoes["se_vazio"] and Usuario.objects.exists():
            self.stdout.write("Banco já tem dados: carga de demonstração ignorada.")
            return
        call_command("flush", interactive=False, verbosity=0)
        with transaction.atomic():
            self._carregar()
        self.stdout.write(self.style.SUCCESS(f"Dados de demonstração carregados (senha de todos: {SENHA})."))

    # --- datas relativas ---------------------------------------------------------

    def _dia(self, competencia: Competencia, dia: int) -> date:
        ultimo = calendar.monthrange(competencia.ano, competencia.mes)[1]
        d = date(competencia.ano, competencia.mes, min(dia, ultimo))
        return min(d, self.hoje)

    def _quando(self, competencia: Competencia, dia: int, hora: int) -> datetime:
        momento = timezone.make_aware(datetime.combine(self._dia(competencia, dia), time(hora)))
        return min(momento, timezone.now())

    # --- carga ---------------------------------------------------------------------

    def _carregar(self) -> None:
        self.hoje = timezone.localdate()
        m0 = Competencia.de_data(self.hoje)
        m1, m2 = m0.anterior(), m0.anterior().anterior()

        setores = {
            sigla: Setor.objects.create(sigla=sigla, nome=nome, cota_mensal=Decimal(cota) if cota else None)
            for sigla, nome, cota in [
                ("SAD", "Secretaria de Administração", None),
                ("SALM", "Seção de Almoxarifado", None),
                ("STI", "Secretaria de Tecnologia da Informação", "2500"),
                ("SOF", "Secretaria de Orçamento e Finanças", "600"),
                ("SGP", "Secretaria de Gestão de Pessoas", "800"),
            ]
        }

        def usuario(email: str, nome: str, mat: str, setor: str, cargo: str, **extra: Any) -> Usuario:
            return Usuario.objects.create_user(
                f"{email}@classcont.local",
                SENHA,
                nome=nome,
                matricula=mat,
                setor=setores[setor],
                cargo=cargo,
                **extra,
            )

        gestor = usuario(
            "gestor", "Marta Ribeiro", "100001", "SAD", "Secretária de Administração",
            perfil=Perfil.GESTOR, is_staff=True, is_superuser=True,
        )  # fmt: skip
        almox = usuario(
            "almoxarife",
            "Paulo Mendes",
            "100002",
            "SALM",
            "Técnico de almoxarifado",
            perfil=Perfil.ALMOXARIFE,
        )
        chefe_ti = usuario("chefe.ti", "Rafael Costa", "100010", "STI", "Secretário de TI")
        ana = usuario("ana", "Ana Souza", "100011", "STI", "Analista de sistemas")
        bruno = usuario("bruno", "Bruno Lima", "100012", "STI", "Técnico de suporte")
        chefe_fin = usuario("chefe.financeiro", "Helena Duarte", "100020", "SOF", "Secretária de Finanças")
        carla = usuario("carla", "Carla Nunes", "100021", "SOF", "Analista financeira")
        diego = usuario("diego", "Diego Alves", "100030", "SGP", "Assistente administrativo")

        for sigla, chefe in [("SAD", gestor), ("SALM", gestor), ("STI", chefe_ti), ("SOF", chefe_fin)]:
            setores[sigla].chefe = chefe
            setores[sigla].save(update_fields=["chefe"])
        # SGP fica sem chefe: as requisições de lá sobem direto para o gestor

        # Catálogo
        mat: dict[str, Material] = {}
        custo: dict[str, Decimal] = {}
        for nome_categoria, itens in MATERIAIS.items():
            categoria = Categoria.objects.create(nome=nome_categoria)
            for codigo, descricao, unidade, minimo, maximo, preco in itens:
                mat[codigo] = Material.objects.create(
                    codigo=codigo, descricao=descricao, categoria=categoria, unidade=unidade,
                    estoque_minimo=minimo, estoque_maximo=maximo,
                )  # fmt: skip
                custo[codigo] = Decimal(preco)

        fornecedores = {
            chave: Fornecedor.objects.create(
                razao_social=nome, cnpj=completar_cnpj(base), email=f"vendas@{chave}.com.br"
            )
            for chave, nome, base in [
                ("papelaria", "Papelaria Central Ltda", "112223330001"),
                ("infotech", "InfoTech Suprimentos de Informática Ltda", "445556660001"),
                ("limpabem", "Limpa Bem Distribuidora Ltda", "778889990001"),
                ("cafecopa", "Café & Copa Comércio de Alimentos Ltda", "223334440001"),
            ]
        }

        def entrada(
            forn: str, nf: str, dia: date, itens: list[tuple[str, int, str | None]], empenho: str = ""
        ) -> None:
            registrar_entrada(
                fornecedor=fornecedores[forn], numero_nota=nf, data_recebimento=dia,
                usuario=almox, empenho=empenho,
                itens=[ItemNota(mat[c].pk, q, Decimal(p) if p else custo[c]) for c, q, p in itens],
            )  # fmt: skip

        # Mês retrasado: carga inicial do estoque
        entrada("papelaria", "1001", self._dia(m2, 3), [
            ("EXP-001", 150, None), ("EXP-002", 12, None), ("EXP-003", 8, None), ("EXP-004", 15, None),
            ("EXP-005", 12, None), ("EXP-006", 200, None), ("EXP-007", 300, None), ("EXP-008", 30, None),
        ], empenho="2026NE000112")  # fmt: skip
        entrada("infotech", "5501", self._dia(m2, 4), [
            ("INF-001", 6, None), ("INF-002", 15, None), ("INF-003", 8, None),
            ("INF-004", 10, None), ("INF-005", 12, None),
        ], empenho="2026NE000113")  # fmt: skip
        entrada(
            "limpabem",
            "88",
            self._dia(m2, 5),
            [("LIM-001", 40, None), ("LIM-002", 10, None), ("LIM-003", 40, None)],
        )
        entrada(
            "cafecopa",
            "3120",
            self._dia(m2, 5),
            [("COP-001", 60, None), ("COP-002", 30, None), ("COP-003", 100, None)],
        )

        # Mês passado: nova compra de papel mais cara → o custo médio muda
        entrada("papelaria", "1088", self._dia(m1, 8), [("EXP-001", 80, "29.50"), ("EXP-002", 6, "54.00")])

        def fluxo(
            quem: Usuario, itens: list[tuple[str, int]], comp: Competencia, dia: int, finalidade: str = ""
        ) -> Requisicao:
            r = req.criar_requisicao(
                requisitante=quem, itens=[req.ItemPedido(mat[c].pk, q) for c, q in itens],
                finalidade=finalidade, agora=self._quando(comp, dia, 9),
            )  # fmt: skip
            return req.enviar(r.pk, quem, agora=self._quando(comp, dia, 9))

        # --- Mês passado ---
        r = fluxo(
            ana,
            [("EXP-001", 30), ("EXP-002", 2), ("EXP-004", 2), ("INF-001", 2)],
            m1,
            10,
            "Reposição das impressoras do 2º andar",
        )
        req.aprovar(r.pk, chefe_ti, agora=self._quando(m1, 10, 14))
        req.atender(r.pk, almox, agora=self._quando(m1, 11, 10))

        r = fluxo(bruno, [("COP-001", 20), ("COP-003", 40), ("COP-002", 8)], m1, 14, "Copa da STI")
        req.aprovar(r.pk, chefe_ti, agora=self._quando(m1, 14, 15))
        req.atender(r.pk, almox, agora=self._quando(m1, 15, 9))

        # SOF: toner estoura a cota → gestor autoriza → faltou saldo → atendimento parcial
        r = fluxo(carla, [("INF-001", 5)], m1, 12, "Impressoras da SOF")
        req.aprovar(r.pk, chefe_fin, agora=self._quando(m1, 12, 16))
        req.aprovar(
            r.pk, gestor, observacao="Autorizado: fechamento do exercício.", agora=self._quando(m1, 13, 10)
        )
        req.atender(r.pk, almox, agora=self._quando(m1, 14, 11))

        r = fluxo(diego, [("EXP-006", 150), ("EXP-007", 250)], m1, 18, "Recadastramento de servidores")
        req.aprovar(r.pk, gestor, agora=self._quando(m1, 18, 15))
        req.atender(r.pk, almox, agora=self._quando(m1, 19, 10))

        r = fluxo(bruno, [("INF-005", 10)], m1, 20)
        req.recusar(
            r.pk,
            chefe_ti,
            "Pen drives são fornecidos pela STI mediante chamado técnico.",
            agora=self._quando(m1, 20, 17),
        )

        # --- Mês atual ---
        entrada("infotech", "5620", self._dia(m0, 2), [("INF-001", 3, "405.00")], empenho="2026NE000201")

        r = fluxo(bruno, [("COP-001", 10), ("COP-003", 8), ("COP-002", 5)], m0, 1, "Copa da STI")
        req.aprovar(r.pk, chefe_ti, agora=self._quando(m0, 1, 11))
        req.atender(r.pk, almox, agora=self._quando(m0, 2, 9))

        r = fluxo(ana, [("EXP-001", 10), ("EXP-002", 1), ("INF-002", 2)], m0, 3, "Novos estagiários")
        req.aprovar(r.pk, chefe_ti, agora=self._quando(m0, 3, 15))  # → fila de atendimento

        fluxo(
            bruno, [("INF-003", 1), ("INF-004", 2), ("INF-005", 3)], m0, 4, "Sala de reuniões"
        )  # → chefe da STI
        fluxo(chefe_ti, [("INF-001", 1)], m0, 4, "Impressora do gabinete")  # a própria: → gestor
        fluxo(diego, [("LIM-003", 6), ("LIM-002", 1)], m0, 5)  # setor sem chefe → gestor

        r = fluxo(carla, [("EXP-001", 20), ("COP-001", 5)], m0, 5, "Material do trimestre")
        req.aprovar(r.pk, chefe_fin, agora=self._quando(m0, 5, 16))  # estoura a cota da SOF → gestor

        # Rascunho: ainda não enviado
        req.criar_requisicao(
            requisitante=ana, itens=[req.ItemPedido(mat["EXP-006"].pk, 20)], finalidade="Arquivo do setor",
            agora=self._quando(m0, 6, 10),
        )  # fmt: skip

        ajustar_inventario(
            material_id=mat["LIM-003"].pk, quantidade_contada=38, usuario=almox,
            justificativa="Inventário mensal: 2 frascos com lacre violado foram descartados.",
        )  # fmt: skip

        fechar_competencia(m2, gestor)
