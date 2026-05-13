from django.urls import path
from . import views

urlpatterns = [
    # This creates the path: yourwebsite.com/log-hours/
    path("log-hours/", views.log_hours_view, name="log_hours"),
]
