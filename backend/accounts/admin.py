from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Added 'role' so you can see it at a glance in the main list
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'farm', 'is_staff')
    
    # Added 'role' to the editable fields on the user detail page
    fieldsets = UserAdmin.fieldsets + (
        ('Farm & Role Assignment', {'fields': ('farm', 'role')}),
    )