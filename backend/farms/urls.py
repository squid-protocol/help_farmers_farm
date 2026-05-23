from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path("roster/", views.volunteer_roster_view, name="volunteer_roster"),
    # --- NEW: The Compliance Audit Trail ---
    path(
        "compliance/<int:form_id>/audit/",
        views.compliance_audit_view,
        name="compliance_audit",
    ),
    path(
        "volunteer/<int:volunteer_id>/",
        views.volunteer_detail_view,
        name="volunteer_detail",
    ),
    # The Farm Impact Dashboard
    path("impact/", views.farm_impact_view, name="farm_impact"),
    # The Manager Progress Report
    path("progress-report/", views.progress_report_view, name="progress_report"),
    # --- THE MISSING LINKS: Edit & Toggle Workflows ---
    path("crop/<int:crop_id>/edit/", views.edit_crop_view, name="edit_crop"),
    path(
        "crop/<int:crop_id>/toggle/",
        views.toggle_crop_status_view,
        name="toggle_crop_status",
    ),
    path(
        "volunteer/<int:volunteer_id>/edit/",
        views.edit_volunteer_view,
        name="edit_volunteer",
    ),
    path(
        "volunteer/<int:user_id>/toggle/",
        views.toggle_user_status_view,
        name="toggle_user_status",
    ),
    path(
        "commitment/<int:commitment_id>/edit/",
        views.edit_commitment_view,
        name="edit_commitment",
    ),
    path(
        "compliance/<int:form_id>/toggle/",
        views.toggle_compliance_status_view,
        name="toggle_compliance_status",
    ),
    path("switch-workspace/", views.switch_active_farm, name="switch_active_farm"),
    # --- NEW: ONBOARDING ROUTES ---
    path("invite/<uuid:token>/", views.invite_link_view, name="invite_link"),
    path("search/", views.farm_search_view, name="farm_search"),
    path(
        "request-join/<int:farm_id>/", views.request_join_farm_view, name="request_join"
    ),
    path(
        "approve-join/<int:membership_id>/",
        views.approve_membership_view,
        name="approve_join",
    ),
]
