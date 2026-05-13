from django import forms
from .models import Crop
from django.contrib.auth import get_user_model

# Fetch your CustomUser model
User = get_user_model()

class CropForm(forms.ModelForm):
    class Meta:
        model = Crop
        fields = ['crop_name', 'variety', 'category', 'is_active']

class VolunteerCreationForm(forms.ModelForm):
    # We must explicitly add a password field so it can be hashed securely
    password = forms.CharField(widget=forms.PasswordInput(), help_text="Provide a temporary password.")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'role']