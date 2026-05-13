from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('volunteer/<int:volunteer_id>/', views.volunteer_detail_view, name='volunteer_detail'),
    
    # NEW: The path to securely delete a user
    path('remove-user/<int:user_id>/', views.remove_user_view, name='remove_user'),
]