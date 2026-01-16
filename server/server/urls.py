from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import re_path

from .views import index, login

admin.autodiscover()


urlpatterns = [
    re_path(r"^$", index, name="index"),
    # re_path(r'^admin/', include(admin.site.urls)),
    re_path(r"^login/$", login, name="login"),
    re_path(r"^logout/$", LogoutView.as_view(), name="logout"),
    re_path(r"^reportmanager/", include("reportmanager.urls")),
]

if settings.USE_OIDC:
    urlpatterns.append(re_path(r"^oidc/", include("mozilla_django_oidc.urls")))

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
