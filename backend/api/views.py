from __future__ import annotations

from typing import Any

import django_filters
from django.db.models import Count, Q, QuerySet, Sum
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from api import serializers as s
from contas import limitador
from contas.models import Setor, Usuario
from dominio.competencia import Competencia
from dominio.requisicao import STATUS_EM_AVALIACAO, Status
from estoque.models import Categoria, Material, Movimentacao, TipoMovimentacao
from requisicoes import permissoes, services
from requisicoes.models import Requisicao
from requisicoes.pdf import gerar_guia_saida


def usuario_de(request: Request) -> Usuario:
    usuario = request.user
    assert isinstance(usuario, Usuario)  # garantido por IsAuthenticated
    return usuario


# --- Autenticação ---------------------------------------------------------------


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        attrs[self.username_field] = str(attrs[self.username_field]).strip().lower()
        return super().validate(attrs)


class LoginView(TokenObtainPairView):
    """POST {email, password} → {access, refresh}. Limita tentativas erradas por e-mail+IP."""

    serializer_class = LoginSerializer

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        chave = limitador.chave_login(str(request.data.get("email", "")), request)
        if limitador.bloqueado(chave):
            return Response({"erro": limitador.MENSAGEM_BLOQUEIO}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            resposta = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            limitador.registrar_falha(chave)
            raise AuthenticationFailed("E-mail ou senha inválidos.") from None
        limitador.limpar(chave)
        return resposta


class MeView(APIView):
    @extend_schema(responses=s.UsuarioSerializer)
    def get(self, request: Request) -> Response:
        return Response(s.UsuarioSerializer(usuario_de(request)).data)


class ResumoView(APIView):
    """Números da tela inicial e do contador de pendências no menu."""

    def get(self, request: Request) -> Response:
        usuario = usuario_de(request)
        por_status = dict(
            Requisicao.objects.filter(requisitante=usuario).values_list("status").annotate(total=Count("id"))
        )
        return Response(
            {
                "minhas_por_status": por_status,
                "pendentes_avaliacao": services.pendentes_de_avaliacao(usuario).count(),
            }
        )


# --- Catálogo -------------------------------------------------------------------


class MaterialFiltro(django_filters.FilterSet):  # type: ignore[misc]
    busca = django_filters.CharFilter(method="filtrar_busca")
    categoria = django_filters.NumberFilter(field_name="categoria_id")

    class Meta:
        model = Material
        fields = ["busca", "categoria"]

    def filtrar_busca(self, queryset: QuerySet[Material], nome: str, valor: str) -> QuerySet[Material]:
        return queryset.filter(Q(descricao__icontains=valor) | Q(codigo__icontains=valor))


class MaterialViewSet(viewsets.ReadOnlyModelViewSet[Material]):
    """Catálogo de materiais ativos, com o saldo disponível para requisição."""

    queryset = Material.objects.filter(ativo=True).select_related("categoria")
    serializer_class = s.MaterialSerializer
    filterset_class = MaterialFiltro


class CategoriaViewSet(viewsets.ReadOnlyModelViewSet[Categoria]):
    queryset = Categoria.objects.all()
    serializer_class = s.CategoriaSerializer
    pagination_class = None


# --- Requisições ----------------------------------------------------------------


class PodeVerRequisicao(permissions.BasePermission):
    message = "Você não tem acesso a esta requisição."

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        return permissoes.pode_ver(usuario_de(request), obj)


class Paginacao(PageNumberPagination):
    page_size = 20


class RequisicaoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet[Requisicao],
):
    permission_classes = [permissions.IsAuthenticated, PodeVerRequisicao]
    pagination_class = Paginacao

    def get_queryset(self) -> QuerySet[Requisicao]:
        base = Requisicao.objects.select_related("setor", "requisitante").prefetch_related(
            "itens__material", "historico__usuario"
        )
        if self.action != "list":
            return base  # o acesso ao objeto é conferido por PodeVerRequisicao

        usuario = usuario_de(self.request)
        filtro = s.FiltroRequisicaoSerializer(data=self.request.query_params)
        filtro.is_valid(raise_exception=True)
        escopo = filtro.validated_data["escopo"]
        if escopo == "pendentes":
            qs = base.filter(pk__in=services.pendentes_de_avaliacao(usuario).values("pk"))
        elif escopo == "setor":
            visiveis = base.exclude(status=Status.RASCUNHO)  # rascunho é privado do requisitante
            qs = (
                visiveis
                if usuario.acessa_painel
                else visiveis.filter(setor_id__in=usuario.ids_setores_chefiados)
            )
        else:
            qs = base.filter(requisitante=usuario)
        if "status" in filtro.validated_data:
            qs = qs.filter(status=filtro.validated_data["status"])
        return qs

    def get_serializer_class(self) -> type[BaseSerializer[Requisicao]]:
        return s.RequisicaoListaSerializer if self.action == "list" else s.RequisicaoDetalheSerializer

    def _detalhe(self, pk: int, codigo: int = status.HTTP_200_OK) -> Response:
        requisicao = self.get_queryset().get(pk=pk)
        return Response(
            s.RequisicaoDetalheSerializer(requisicao, context={"request": self.request}).data, status=codigo
        )

    @extend_schema(parameters=[OpenApiParameter("escopo", enum=["minhas", "pendentes", "setor"])])
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(request=s.RequisicaoEscritaSerializer, responses={201: s.RequisicaoDetalheSerializer})
    def create(self, request: Request) -> Response:
        entrada = s.RequisicaoEscritaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        requisicao = services.criar_requisicao(
            requisitante=usuario_de(request),
            itens=[services.ItemPedido(**i) for i in entrada.validated_data["itens"]],
            finalidade=entrada.validated_data["finalidade"],
        )
        return self._detalhe(requisicao.pk, status.HTTP_201_CREATED)

    @extend_schema(request=s.RequisicaoEscritaSerializer, responses=s.RequisicaoDetalheSerializer)
    def update(self, request: Request, pk: str) -> Response:
        requisicao = self.get_object()
        entrada = s.RequisicaoEscritaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        services.atualizar_rascunho(
            requisicao.pk,
            usuario_de(request),
            [services.ItemPedido(**i) for i in entrada.validated_data["itens"]],
            entrada.validated_data["finalidade"],
        )
        return self._detalhe(requisicao.pk)

    @extend_schema(request=None, responses=s.RequisicaoDetalheSerializer)
    @action(detail=True, methods=["post"])
    def enviar(self, request: Request, pk: str) -> Response:
        requisicao = self.get_object()
        services.enviar(requisicao.pk, usuario_de(request))
        return self._detalhe(requisicao.pk)

    @extend_schema(request=s.AprovarSerializer, responses=s.RequisicaoDetalheSerializer)
    @action(detail=True, methods=["post"])
    def aprovar(self, request: Request, pk: str) -> Response:
        requisicao = self.get_object()
        entrada = s.AprovarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        quantidades = {i["id"]: i["quantidade"] for i in entrada.validated_data.get("itens", [])}
        services.aprovar(
            requisicao.pk, usuario_de(request), quantidades, entrada.validated_data["observacao"]
        )
        return self._detalhe(requisicao.pk)

    @extend_schema(request=s.RecusarSerializer, responses=s.RequisicaoDetalheSerializer)
    @action(detail=True, methods=["post"])
    def recusar(self, request: Request, pk: str) -> Response:
        requisicao = self.get_object()
        entrada = s.RecusarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        services.recusar(requisicao.pk, usuario_de(request), entrada.validated_data["motivo"])
        return self._detalhe(requisicao.pk)

    @extend_schema(request=s.CancelarSerializer, responses=s.RequisicaoDetalheSerializer)
    @action(detail=True, methods=["post"])
    def cancelar(self, request: Request, pk: str) -> Response:
        requisicao = self.get_object()
        entrada = s.CancelarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        services.cancelar(requisicao.pk, usuario_de(request), entrada.validated_data["motivo"])
        return self._detalhe(requisicao.pk)

    @extend_schema(responses={(200, "application/pdf"): bytes})
    @action(detail=True, methods=["get"])
    def guia(self, request: Request, pk: str) -> HttpResponse:
        """Guia de saída em PDF (somente requisições atendidas)."""
        requisicao = self.get_object()
        if not permissoes.pode_baixar_guia(usuario_de(request), requisicao):
            return Response({"erro": "A guia só existe para requisições atendidas."}, status=422)
        resposta = HttpResponse(gerar_guia_saida(requisicao), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="guia-{requisicao.pk}.pdf"'
        return resposta


# --- Consumo do setor (chefia) ----------------------------------------------------


class ConsumoSetorView(APIView):
    """Cota, consumo por material e requisições do mês de um setor."""

    @extend_schema(
        parameters=[OpenApiParameter("competencia", str, description="AAAA-MM (padrão: mês atual)")]
    )
    def get(self, request: Request, pk: int) -> Response:
        usuario = usuario_de(request)
        setor = Setor.objects.get(pk=pk)
        if not (usuario.chefia_setor(setor.pk) or usuario.acessa_painel):
            return Response({"erro": "Somente a chefia do setor consulta o consumo."}, status=403)

        texto = request.query_params.get("competencia")
        competencia = Competencia.de_texto(texto) if texto else Competencia.de_data(timezone.localdate())
        periodo = (competencia.primeiro_dia, competencia.ultimo_dia)
        materiais = (
            Movimentacao.objects.filter(tipo=TipoMovimentacao.SAIDA, setor=setor, data__range=periodo)
            .values("material__codigo", "material__descricao", "material__unidade")
            .annotate(quantidade=Sum("quantidade"), valor=Sum("valor_total"))
            .order_by("-valor")
        )
        requisicoes = dict(
            Requisicao.objects.filter(setor=setor, criado_em__date__range=periodo)
            .values_list("status")
            .annotate(total=Count("id"))
        )
        cota = services.situacao_cota(setor, competencia)
        return Response(
            {
                "setor": s.SetorResumoSerializer(setor).data,
                "competencia": str(competencia),
                "cota": s.SituacaoCotaSerializer(cota).data,
                "materiais": [
                    {
                        "codigo": m["material__codigo"],
                        "descricao": m["material__descricao"],
                        "unidade": m["material__unidade"],
                        "quantidade": m["quantidade"],
                        "valor": f"{m['valor']:.2f}",
                    }
                    for m in materiais
                ],
                "requisicoes_por_status": requisicoes,
                "aguardando_avaliacao": sum(requisicoes.get(st.value, 0) for st in STATUS_EM_AVALIACAO),
                "atendidas": requisicoes.get(Status.ATENDIDA.value, 0)
                + requisicoes.get(Status.ATENDIDA_PARCIALMENTE.value, 0),
            }
        )
