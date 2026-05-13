from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')), 
    
    path('farm/', include('farms.urls')), # <-- Add this line!
    
    path('', RedirectView.as_view(pattern_name='log_hours', permanent=False)),
    path('', include('logs.urls')), 
]