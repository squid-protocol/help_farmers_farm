from django.urls import path
from . import views

urlpatterns = [
    path("api/chart/impact/", views.get_impact_chart, name="get_impact_chart"),
    path("api/chart/heatmap/", views.get_activity_heatmap, name="get_activity_heatmap"),
    path(
        "api/chart/terms/", views.get_term_heatmap, name="get_term_heatmap"
    ),  # <-- ADD THIS
]
