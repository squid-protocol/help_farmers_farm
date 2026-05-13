from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings             # <-- NEW: Needed for avatars
from django.conf.urls.static import static   # <-- NEW: Needed for avatars

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("accounts.urls")),  
    path("", TemplateView.as_view(template_name="landing.html"), name="home"),
    path("", include("logs.urls")),
    path("farm/", include("farms.urls")),
    path("analytics/", include("analytics.urls")), # <-- Add this!
]

# THE FIX: Tell the development server how to serve uploaded media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)