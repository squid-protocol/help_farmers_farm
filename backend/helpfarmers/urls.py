from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView  # <-- Add this import

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("accounts.urls")),  # <-- NEW: Includes your profile URL
    path("", TemplateView.as_view(template_name="landing.html"), name="home"),
    path("", include("logs.urls")),
    path("farm/", include("farms.urls")),
]
