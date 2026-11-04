from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve as servir_estatico
from django.urls import path, include, re_path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVIR_ARQUIVOS_ESTATICOS:
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", servir_estatico, {"insecure": True}),
    ]
