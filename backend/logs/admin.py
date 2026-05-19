from django.contrib import admin
from .models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "volunteer",
        "date_logged",
        "duration_hours",
        "activity",
        "crop",
        "farm",
        "created_at",  # Shows when the form was actually submitted
    )
    list_filter = ("farm", "activity", "date_logged")

    # NEW: Allow searching by volunteer's real name AND their shift notes
    search_fields = (
        "volunteer__username",
        "volunteer__first_name",
        "volunteer__last_name",
        "crop__crop_name",
        "notes",
    )

    # NEW: Expose the auto-generated timestamp
    readonly_fields = ("created_at",)
