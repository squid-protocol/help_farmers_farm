from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path(
        "volunteer/<int:volunteer_id>/",
        views.volunteer_detail_view,
        name="volunteer_detail",
    ),
    path("remove-user/<int:user_id>/", views.remove_user_view, name="remove_user"),
    # The Farm Impact Dashboard
    path("impact/", views.farm_impact_view, name="farm_impact"),
    # NEW: The Manager Progress Report
    path("progress-report/", views.progress_report_view, name="progress_report"),
]
