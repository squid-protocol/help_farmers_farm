from django import forms
from .models import Crop
from django.contrib.auth import get_user_model

# Fetch your CustomUser model
User = get_user_model()


class CropForm(forms.ModelForm):
    class Meta:
        model = Crop
        fields = ["crop_name", "variety", "category", "is_active"]


class VolunteerCreationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(), help_text="Provide a temporary password."
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "role"]

    # --- NEW: Intercept the form creation to check the user's role ---
    def __init__(self, *args, **kwargs):
        # Extract the user requesting the form before Django processes it
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        if self.request_user and not self.request_user.is_staff:
            # If the user is only a Farm Manager, remove the Manager roles from the dropdown
            if self.request_user.role == "farm_manager":
                self.fields["role"].choices = [
                    choice
                    for choice in self.fields["role"].choices
                    if choice[0] not in ["account_manager", "farm_manager"]
                ]
