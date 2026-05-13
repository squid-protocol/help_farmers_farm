from django import forms
from django.contrib.auth import get_user_model
from .models import Crop, WorkCommitment

# Fetch your CustomUser model
User = get_user_model()


class WorkCommitmentForm(forms.ModelForm):
    class Meta:
        model = WorkCommitment
        fields = ["name", "required_hours"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 "
                        "text-sm rounded-lg focus:ring-emerald-500 "
                        "focus:border-emerald-500 block w-full p-2.5"
                    ),
                    "placeholder": "e.g., Full Share",
                }
            ),
            "required_hours": forms.NumberInput(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 "
                        "text-sm rounded-lg focus:ring-emerald-500 "
                        "focus:border-emerald-500 block w-full p-2.5"
                    ),
                    "placeholder": "80",
                }
            ),
        }


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
            # If the user is only a Farm Manager, remove the Manager roles
            if self.request_user.role == "farm_manager":
                self.fields["role"].choices = [
                    choice
                    for choice in self.fields["role"].choices
                    if choice[0] not in ["account_manager", "farm_manager"]
                ]
