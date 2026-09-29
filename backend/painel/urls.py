from django.contrib.auth.views import LogoutView
from django.urls import path

from painel.views import cadastros, competencias, entradas, inicio, materiais, relatorios, requisicoes

app_name = "painel"

urlpatterns = [
    path("login/", inicio.EntrarView.as_view(), name="login"),
    path("sair/", LogoutView.as_view(), name="sair"),
    path("", inicio.DashboardView.as_view(), name="dashboard"),
    # Materiais e kardex
    path("materiais/", materiais.MaterialLista.as_view(), name="material_lista"),
    path("materiais/novo/", materiais.MaterialNovo.as_view(), name="material_novo"),
    path("materiais/<int:pk>/", materiais.MaterialDetalhe.as_view(), name="material_detalhe"),
    path("materiais/<int:pk>/editar/", materiais.MaterialEditar.as_view(), name="material_editar"),
    # Entradas
    path("entradas/", entradas.EntradaLista.as_view(), name="entrada_lista"),
    path("entradas/nova/", entradas.EntradaNova.as_view(), name="entrada_nova"),
    path("entradas/<int:pk>/", entradas.EntradaDetalhe.as_view(), name="entrada_detalhe"),
    # Requisições
    path("requisicoes/", requisicoes.RequisicaoLista.as_view(), name="requisicao_lista"),
    path("requisicoes/<int:pk>/", requisicoes.RequisicaoDetalhe.as_view(), name="requisicao_detalhe"),
    path("requisicoes/<int:pk>/atender/", requisicoes.RequisicaoAtender.as_view(), name="requisicao_atender"),
    path("requisicoes/<int:pk>/aprovar/", requisicoes.RequisicaoAprovar.as_view(), name="requisicao_aprovar"),
    path("requisicoes/<int:pk>/recusar/", requisicoes.RequisicaoRecusar.as_view(), name="requisicao_recusar"),
    path(
        "requisicoes/<int:pk>/cancelar/", requisicoes.RequisicaoCancelar.as_view(), name="requisicao_cancelar"
    ),
    path("requisicoes/<int:pk>/guia.pdf", requisicoes.RequisicaoGuia.as_view(), name="requisicao_guia"),
    # Relatórios
    path("relatorios/reposicao/", relatorios.ReposicaoView.as_view(), name="relatorio_reposicao"),
    path("relatorios/curva-abc/", relatorios.CurvaAbcView.as_view(), name="relatorio_abc"),
    path("relatorios/consumo-setores/", relatorios.ConsumoSetoresView.as_view(), name="relatorio_consumo"),
    # Cadastros de apoio
    path("categorias/", cadastros.CategoriaLista.as_view(), name="categoria_lista"),
    path("categorias/nova/", cadastros.CategoriaNova.as_view(), name="categoria_novo"),
    path("categorias/<int:pk>/editar/", cadastros.CategoriaEditar.as_view(), name="categoria_editar"),
    path("fornecedores/", cadastros.FornecedorLista.as_view(), name="fornecedor_lista"),
    path("fornecedores/novo/", cadastros.FornecedorNovo.as_view(), name="fornecedor_novo"),
    path("fornecedores/<int:pk>/editar/", cadastros.FornecedorEditar.as_view(), name="fornecedor_editar"),
    # Somente gestor
    path("setores/", cadastros.SetorLista.as_view(), name="setor_lista"),
    path("setores/novo/", cadastros.SetorNovo.as_view(), name="setor_novo"),
    path("setores/<int:pk>/editar/", cadastros.SetorEditar.as_view(), name="setor_editar"),
    path("usuarios/", cadastros.UsuarioLista.as_view(), name="usuario_lista"),
    path("usuarios/novo/", cadastros.UsuarioNovo.as_view(), name="usuario_novo"),
    path("usuarios/<int:pk>/editar/", cadastros.UsuarioEditar.as_view(), name="usuario_editar"),
    path("usuarios/<int:pk>/ativo/", cadastros.UsuarioAlternarAtivo.as_view(), name="usuario_ativo"),
    path("competencias/", competencias.CompetenciaLista.as_view(), name="competencia_lista"),
    path("competencias/fechar/", competencias.CompetenciaFechar.as_view(), name="competencia_fechar"),
]
