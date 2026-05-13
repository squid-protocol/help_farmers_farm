from django.urls import path
from . import views

urlpatterns = [
    path("api/chart/", views.get_impact_chart, name="get_impact_chart"),
]