from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path(
        "volunteer/<int:volunteer_id>/",
        views.volunteer_detail_view,
        name="volunteer_detail",
    ),
    # NEW: Toggle Endpoints
    path(
        "toggle-user/<int:user_id>/",
        views.toggle_user_status_view,
        name="toggle_user_status",
    ),
    path(
        "toggle-crop/<int:crop_id>/",
        views.toggle_crop_status_view,
        name="toggle_crop_status",
    ),
    # The Farm Impact Dashboard
    path("impact/", views.farm_impact_view, name="farm_impact"),
    # The Manager Progress Report
    path("progress-report/", views.progress_report_view, name="progress_report"),
    # Edit Endpoints
    path("edit-crop/<int:crop_id>/", views.edit_crop_view, name="edit_crop"),
    path(
        "edit-volunteer/<int:volunteer_id>/",
        views.edit_volunteer_view,
        name="edit_volunteer",
    ),
    path(
        "edit-commitment/<int:commitment_id>/",
        views.edit_commitment_view,
        name="edit_commitment",
    ),
]
