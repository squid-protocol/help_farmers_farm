from django import forms
from django.contrib.auth import get_user_model
from .models import Crop, WorkCommitment, Farm, ComplianceForm

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
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Provide a temporary password.",
    )
    work_commitment = forms.ModelChoiceField(
        queryset=WorkCommitment.objects.none(),
        required=False,
        empty_label="Standard Volunteer (No specific tier)",
        widget=forms.Select(
            attrs={
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-emerald-500 focus:border-emerald-500 block w-full p-2.5"
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "work_commitment",
            "legacy_years_volunteered",
            "role",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "off"}),
            "email": forms.EmailInput(attrs={"autocomplete": "off"}),
            "legacy_years_volunteered": forms.NumberInput(
                attrs={"placeholder": "e.g., 5"}
            ),
            "phone_number": forms.TextInput(attrs={"placeholder": "(555) 123-4567"}),
        }
        help_texts = {
            "phone_number": "Format: (555) 123-4567 or +15551234567",
        }

    field_order = [
        "username",
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "work_commitment",
        "legacy_years_volunteered",
        "role",
        "password",
    ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        self.farm = kwargs.pop("farm", None)
        super().__init__(*args, **kwargs)

        if self.farm:
            self.fields["work_commitment"].queryset = WorkCommitment.objects.filter(
                farm=self.farm
            )

        if self.request_user:
            if (
                not self.request_user.is_staff
                and self.request_user.role == "farm_manager"
            ):
                self.fields["role"].choices = [
                    choice
                    for choice in self.fields["role"].choices
                    if choice[0] not in ["account_manager", "farm_manager"]
                ]


class VolunteerEditForm(forms.ModelForm):
    work_commitment = forms.ModelChoiceField(
        queryset=WorkCommitment.objects.none(),
        required=False,
        empty_label="Standard Volunteer (No specific tier)",
        widget=forms.Select(
            attrs={
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-emerald-500 focus:border-emerald-500 block w-full p-2.5"
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "work_commitment",
            "role",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        self.farm = kwargs.pop("farm", None)
        super().__init__(*args, **kwargs)

        if self.farm:
            self.fields["work_commitment"].queryset = WorkCommitment.objects.filter(
                farm=self.farm
            )

        if self.request_user:
            # Prevent farm managers from granting account_manager privileges
            if (
                not self.request_user.is_staff
                and self.request_user.role == "farm_manager"
            ):
                self.fields["role"].choices = [
                    choice
                    for choice in self.fields["role"].choices
                    if choice[0] not in ["account_manager", "farm_manager"]
                ]


class FarmSettingsForm(forms.ModelForm):
    class Meta:
        model = Farm
        # THE FIX: Removed liability_waiver_text, added the new contact fields!
        fields = [
            "name",
            "address",
            "contact_email",
            "phone_number",
            "welcome_email_subject",
            "welcome_email_body",
            "season_start",
            "season_end",
            "allows_joint_accounts",
        ]
        help_texts = {
            "phone_number": "Format: (555) 123-4567 or +15551234567",
            "allows_joint_accounts": (
                "⚠️ LIABILITY WARNING: Enabling this disables strict WORM-compliant waiver tracking "
                "so multiple people can share one account. Do not use if you require legally binding "
                "digital signatures."
            ),
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5 custom-scrollbar"
                    ),
                    "placeholder": "123 Harvest Lane\nFarmingville, MI 48103",
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                    "placeholder": "info@schulerfarms.com",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                    "placeholder": "(555) 123-4567",
                }
            ),
            "season_start": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                }
            ),
            "season_end": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                }
            ),
            "welcome_email_subject": forms.TextInput(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                    "placeholder": "Welcome to the farm!",
                }
            ),
            "welcome_email_body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5 custom-scrollbar"
                    ),
                }
            ),
        }


class ComplianceFormSetup(forms.ModelForm):
    class Meta:
        model = ComplianceForm
        fields = [
            "name",
            "body_text",
            "assignment_type",
            "assigned_users",
            "is_active",
            "does_expire",
            "expiration_date",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                    "placeholder": "e.g., Tractor Operation Waiver",
                }
            ),
            "body_text": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5 custom-scrollbar"
                    ),
                    "placeholder": "Paste the legal text here...",
                }
            ),
            "assignment_type": forms.Select(
                attrs={
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                }
            ),
            "assigned_users": forms.CheckboxSelectMultiple(
                attrs={
                    "class": "sr-only peer",
                }
            ),
            "expiration_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": (
                        "bg-gray-50 border border-gray-300 text-gray-900 text-sm "
                        "rounded-lg block w-full p-2.5"
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        # Extract the farm instance before passing to super
        farm = kwargs.pop("farm", None)
        super().__init__(*args, **kwargs)

        if farm:
            # Dynamically filter the users list to only show active standard volunteers on THIS farm
            valid_users = (
                User.objects.filter(
                    memberships__farm=farm,
                    is_active=True,
                )
                .exclude(role__in=["friend", "account_manager"])
                .distinct()
            )

            self.fields["assigned_users"].queryset = valid_users
