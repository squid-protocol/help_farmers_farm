from django.contrib import admin
from .models import Farm, Crop, WorkCommitment


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("crop_name", "variety", "farm", "category", "is_active")
    list_filter = ("farm", "is_active", "category")  # Adds a handy filter sidebar
    search_fields = ("crop_name", "variety")


@admin.register(WorkCommitment)
class WorkCommitmentAdmin(admin.ModelAdmin):
    list_display = ("name", "required_hours", "farm")
    list_filter = ("farm",)
    search_fields = ("name",)
