from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "role",
        "is_staff",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Role Assignment",
            {"fields": ("role", "phone_number")},
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Role Assignment",
            {"fields": ("role", "phone_number")},
        ),
    )
