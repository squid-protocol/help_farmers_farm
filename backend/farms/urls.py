from django.urls import path
from . import views

urlpatterns = [
    # This creates the path: yourwebsite.com/farm/dashboard/
    path('dashboard/', views.manager_dashboard, name='manager_dashboard'),
]