from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("accounts.urls")),
    path("", TemplateView.as_view(template_name="landing.html"), name="home"),
    
    # --- ADD THESE THREE LINES ---
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
    path("faq/", TemplateView.as_view(template_name="faq.html"), name="faq"),
    path("contact/", TemplateView.as_view(template_name="contact.html"), name="contact"),
    # -----------------------------
    
    path("", include("logs.urls")),
    path("farm/", include("farms.urls")),
    path("analytics/", include("analytics.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)