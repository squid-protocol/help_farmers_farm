from django.urls import path
from . import views

urlpatterns = [
    path("log-hours/", views.log_hours_view, name="log_hours"),
    path("directory/", views.master_log_directory, name="master_log_directory"),
    path("edit/<int:log_id>/", views.edit_log_view, name="edit_log"),
    path("delete/<int:log_id>/", views.delete_log_view, name="delete_log"),
]
