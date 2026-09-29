"""Fábricas (factory_boy) e montagem de cenários para os testes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import factory
from django.utils import timezone

from contas.models import Perfil, Setor, Usuario
from dominio.cnpj import completar_cnpj
from estoque.models import Categoria, Fornecedor, Material
from estoque.services import ItemNota, registrar_entrada
from requisicoes import services
from requisicoes.models import Requisicao

SENHA = "senha123"


class SetorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Setor

    sigla = factory.Sequence(lambda n: f"S{n:02d}")
    nome = factory.LazyAttribute(lambda o: f"Setor {o.sigla}")


class UsuarioFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Usuario
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"usuario{n}@classcont.local")
    nome = factory.Sequence(lambda n: f"Servidor {n}")
    matricula = factory.Sequence(lambda n: f"{900000 + n}")
    setor = factory.SubFactory(SetorFactory)
    password = factory.PostGenerationMethodCall("set_password", SENHA)

    @factory.post_generation
    def salvar(obj: Usuario, create: bool, extracted: object, **kwargs: object) -> None:
        if create:
            obj.save()


class CategoriaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Categoria
        django_get_or_create = ("nome",)

    nome = "Expediente"


class FornecedorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Fornecedor

    razao_social = factory.Sequence(lambda n: f"Fornecedor {n} Ltda")
    cnpj = factory.Sequence(lambda n: completar_cnpj(f"{10000000 + n:08d}0001"))


class MaterialFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Material

    codigo = factory.Sequence(lambda n: f"MAT-{n:03d}")
    descricao = factory.Sequence(lambda n: f"Material {n}")
    categoria = factory.SubFactory(CategoriaFactory)
    estoque_minimo = 5
    estoque_maximo = 100


@dataclass
class Cenario:
    """Dois setores com chefia, servidores, almoxarife, gestor e dois materiais com saldo.

    - STI: cota R$ 1.000 (chefe_sti; ana e bruno)
    - SOF: cota R$ 100  (chefe_sof; carla)
    - papel: 50 unidades a R$ 20,00 (mín. 10, máx. 100)
    - toner: 4 unidades a R$ 300,00 (mín. 2, máx. 10)
    """

    gestor: Usuario
    almox: Usuario
    chefe_sti: Usuario
    ana: Usuario
    bruno: Usuario
    chefe_sof: Usuario
    carla: Usuario
    sti: Setor
    sof: Setor
    papel: Material
    toner: Material
    fornecedor: Fornecedor

    def recarregar(self) -> None:
        self.papel.refresh_from_db()
        self.toner.refresh_from_db()


def montar_cenario() -> Cenario:
    sad = SetorFactory(sigla="SAD", nome="Administração")
    sti = SetorFactory(sigla="STI", nome="Tecnologia da Informação", cota_mensal=Decimal("1000"))
    sof = SetorFactory(sigla="SOF", nome="Orçamento e Finanças", cota_mensal=Decimal("100"))
    gestor = UsuarioFactory(email="gestor@classcont.local", nome="Gestora", setor=sad, perfil=Perfil.GESTOR)
    almox = UsuarioFactory(
        email="almox@classcont.local", nome="Almoxarife", setor=sad, perfil=Perfil.ALMOXARIFE
    )
    chefe_sti = UsuarioFactory(email="chefe.sti@classcont.local", nome="Chefe STI", setor=sti)
    ana = UsuarioFactory(email="ana@classcont.local", nome="Ana", setor=sti)
    bruno = UsuarioFactory(email="bruno@classcont.local", nome="Bruno", setor=sti)
    chefe_sof = UsuarioFactory(email="chefe.sof@classcont.local", nome="Chefe SOF", setor=sof)
    carla = UsuarioFactory(email="carla@classcont.local", nome="Carla", setor=sof)
    sad.chefe, sti.chefe, sof.chefe = gestor, chefe_sti, chefe_sof
    for setor in (sad, sti, sof):
        setor.save()

    papel = MaterialFactory(codigo="EXP-001", descricao="Papel A4", estoque_minimo=10, estoque_maximo=100)
    toner = MaterialFactory(codigo="INF-001", descricao="Toner", estoque_minimo=2, estoque_maximo=10)
    fornecedor = FornecedorFactory()
    registrar_entrada(
        fornecedor=fornecedor,
        numero_nota="1",
        data_recebimento=timezone.localdate(),
        usuario=almox,
        itens=[ItemNota(papel.pk, 50, Decimal("20.00")), ItemNota(toner.pk, 4, Decimal("300.00"))],
    )
    papel.refresh_from_db()
    toner.refresh_from_db()
    return Cenario(gestor, almox, chefe_sti, ana, bruno, chefe_sof, carla, sti, sof, papel, toner, fornecedor)


def requisicao_enviada(quem: Usuario, *itens: tuple[Material, int]) -> Requisicao:
    r = services.criar_requisicao(
        requisitante=quem, itens=[services.ItemPedido(m.pk, q) for m, q in itens], finalidade="Teste"
    )
    return services.enviar(r.pk, quem)


def requisicao_aprovada(quem: Usuario, aprovador: Usuario, *itens: tuple[Material, int]) -> Requisicao:
    r = requisicao_enviada(quem, *itens)
    return services.aprovar(r.pk, aprovador)
