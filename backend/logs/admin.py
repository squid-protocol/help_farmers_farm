from django.contrib import admin
from .models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "volunteer",
        "crop",
        "activity",
        "duration_hours",
        "date_logged",
        "farm",
    )
    list_filter = ("farm", "activity", "date_logged")
    search_fields = ("volunteer__username", "crop__crop_name")
