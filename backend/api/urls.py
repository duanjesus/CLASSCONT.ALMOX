from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from api import views

router = DefaultRouter(trailing_slash=False)
router.register("materiais", views.MaterialViewSet, basename="material")
router.register("categorias", views.CategoriaViewSet, basename="categoria")
router.register("requisicoes", views.RequisicaoViewSet, basename="requisicao")

urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="api-login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="api-refresh"),
    path("auth/logout", TokenBlacklistView.as_view(), name="api-logout"),
    path("me", views.MeView.as_view(), name="api-me"),
    path("resumo", views.ResumoView.as_view(), name="api-resumo"),
    path("setores/<int:pk>/consumo", views.ConsumoSetorView.as_view(), name="api-consumo-setor"),
    path("schema", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("", include(router.urls)),
]
