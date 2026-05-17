from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Added 'role' so you can see it at a glance in the main list
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "role",
        "farm",
        "work_commitment",
        "is_staff",
    )

    # Added 'role' to the editable fields on the user detail page
    fieldsets = UserAdmin.fieldsets + (
        (
            "Farm & Role Assignment",
            {"fields": ("farm", "role", "work_commitment", "phone_number")},
        ),
    )

    # Added to ensure the fields appear when manually creating a NEW user
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Farm & Role Assignment",
            {"fields": ("farm", "role", "work_commitment", "phone_number")},
        ),
    )
