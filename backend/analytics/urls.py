from django.urls import path
from . import views

urlpatterns = [
    path("api/chart/impact/", views.get_impact_chart, name="get_impact_chart"),
    path("api/chart/heatmap/", views.get_activity_heatmap, name="get_activity_heatmap"),
    path("api/chart/terms/", views.get_term_heatmap, name="get_term_heatmap"),
    path(
        "api/chart/timeline/", views.get_seasonal_timeline, name="get_seasonal_timeline"
    ),
    path(
        "api/chart/volunteer-heatmap/",
        views.get_volunteer_heatmap,
        name="get_volunteer_heatmap",
    ),
    path(
        "api/chart/adoption-report/",
        views.get_adoption_report,
        name="get_adoption_report",
    ),
    path(
        "admin-dashboard/",
        views.admin_adoption_dashboard,
        name="admin_adoption_dashboard",
    ),
]
