from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Turns on Django's built-in login, logout, and password reset URLs!
    path('accounts/', include('django.contrib.auth.urls')), 
    
    path('', RedirectView.as_view(pattern_name='log_hours', permanent=False)),
    path('', include('logs.urls')), 
]