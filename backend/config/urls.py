from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="painel:dashboard", permanent=False)),
    path("api/", include("api.urls")),
    path("painel/", include("painel.urls")),
    # Django Admin "cru": útil para suporte, mas o dia a dia usa o painel próprio
    path("django-admin/", admin.site.urls),
]

admin.site.site_header = "CLASSCONT.ALMOX · Django Admin"
