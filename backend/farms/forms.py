from django import forms
from django.contrib.auth import get_user_model
from .models import Crop, WorkCommitment, Farm

# Fetch your CustomUser model
User = get_user_model()


class WorkCommitmentForm(forms.ModelForm):
    class Meta:
        model = WorkCommitment
        fields = ["name", "required_hours", "symbol"]
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

        # ADDED: "email"
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "phone_number",
        ]

    # ADDED: "email" to the forced layout order
    field_order = [
        "username",
        "first_name",
        "last_name",
        "email",
        "role",
        "phone_number",
        "password",
    ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        if self.request_user and not self.request_user.is_staff:
            if self.request_user.role == "farm_manager":
                self.fields["role"].choices = [
                    choice
                    for choice in self.fields["role"].choices
                    if choice[0] not in ["account_manager", "farm_manager"]
                ]


# --- THE MISSING FORM: For inline editing existing users ---
class VolunteerEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "work_commitment",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        if self.request_user:
            # Only show commitments that belong to this specific farm
            if self.request_user.farm:
                self.fields["work_commitment"].queryset = WorkCommitment.objects.filter(
                    farm=self.request_user.farm
                )

            # Prevent farm managers from granting account_manager privileges
            if not self.request_user.is_staff and self.request_user.role == "farm_manager":
                self.fields["role"].choices = [
                    choice
                    for choice in self.fields["role"].choices
                    if choice[0] not in ["account_manager", "farm_manager"]
                ]


class FarmSettingsForm(forms.ModelForm):
    class Meta:
        model = Farm
        fields = ["name", "season_start", "season_end"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5",
                }
            ),
            "season_start": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5",
                }
            ),
            "season_end": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5",
                }
            ),
<<<<<<< HEAD
        }
=======
        }


class VolunteerEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "username",
            "email",
            "phone_number",
            "role",
            "work_commitment",
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        # Restrict the work commitment dropdown to ONLY this farm's commitments
        if self.request_user and self.request_user.farm:
            self.fields["work_commitment"].queryset = WorkCommitment.objects.filter(
                farm=self.request_user.farm
            )

        # Prevent Farm Managers from elevating people to Account Managers
        if self.request_user and not self.request_user.is_staff:
            if self.request_user.role == "farm_manager":
                self.fields["role"].choices = [
                    choice
                    for choice in self.fields["role"].choices
                    if choice[0] not in ["account_manager", "farm_manager"]
                ]
>>>>>>> 70798caa5d7630676a1222b342ae8578ff3943dc
