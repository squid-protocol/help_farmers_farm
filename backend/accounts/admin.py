from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, FarmMembership


# 1. The Inline Bridge: This lets you manage a user's farms directly inside their User profile!
class FarmMembershipInline(admin.TabularInline):
    model = FarmMembership
    extra = 1  # Provides one blank row to easily add them to a new farm
    fields = ("farm", "work_commitment", "is_approved", "agreed_to_waiver")


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "role",
        "is_active",
    )

    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email")

    # 2. Inject the Inline into the User screen
    inlines = [FarmMembershipInline]

    # 3. Expose all our custom fields
    fieldsets = UserAdmin.fieldsets + (
        (
            "Custom App Details",
            {"fields": ("role", "phone_number", "legacy_years_volunteered", "avatar")},
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Custom App Details",
            {"fields": ("role", "phone_number", "legacy_years_volunteered")},
        ),
    )


# 4. Global Bridge Admin: A dedicated page just to search/filter all memberships globally
@admin.register(FarmMembership)
class FarmMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "farm",
        "work_commitment",
        "is_approved",
        "agreed_to_waiver",
    )
    list_filter = ("farm", "is_approved", "agreed_to_waiver")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "farm__name",
    )
