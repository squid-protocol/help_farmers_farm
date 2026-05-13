from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # This controls what columns show up in the main list view
    list_display = ('username', 'email', 'first_name', 'last_name', 'farm', 'is_staff')
    
    # This adds the 'farm' dropdown to the user's edit page
    fieldsets = UserAdmin.fieldsets + (
        ('Farm Link', {'fields': ('farm',)}),
    )

admin.site.register(CustomUser, CustomUserAdmin)