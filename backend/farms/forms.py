import json
from django import forms
from django.contrib.auth import get_user_model
from .models import Crop, WorkCommitment, Farm, ComplianceForm, FarmProfile

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


# 1. Custom Widget to bypass Django's ValueError
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


# 2. Custom field to safely handle a list of files
class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            # Clean each file individually
            return [single_file_clean(d, initial) for d in data]
        else:
            return [single_file_clean(data, initial)] if data else []


class FarmProfileForm(forms.ModelForm):
    # These must sit ABOVE the Meta class to override strict validation
    is_public = forms.BooleanField(required=False)
    is_accepting_volunteers = forms.BooleanField(required=False)

    # 3. Use the new custom field and widget (No 'multiple' flag in attrs!)
    gallery_uploads = MultipleFileField(
        widget=MultipleFileInput(
            attrs={
                "class": "bg-white border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2 cursor-pointer focus:outline-none",
            }
        ),
        required=False,
        help_text="Upload up to 5 action shots of your farm. (JPG or PNG)",
    )

    # We use a standard text input for tags, which Tagify will hijack on the frontend
    tags = forms.CharField(
        required=False,
        help_text="Type a tag (e.g., 'USDA Organic') and press Enter.",
        widget=forms.TextInput(
            attrs={
                "class": "tagify-input bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5",
                "placeholder": "Add tags...",
            }
        ),
    )

    # We hide the actual textarea because the Trix editor will write directly into it
    about_us = forms.CharField(
        required=False, widget=forms.HiddenInput(attrs={"id": "id_about_us"})
    )

    class Meta:
        model = FarmProfile
        fields = [
            "is_public",
            "is_accepting_volunteers",
            "short_description",
            "about_us",
            "volunteer_perks",
            "physical_requirements",
            "tags",
            "logo",
            "cover_photo",
            "website_url",
            "facebook_url",
            "instagram_url",
        ]
        widgets = {
            "volunteer_perks": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5 custom-scrollbar",
                    "placeholder": "e.g., Take home a free box of produce every shift...",
                }
            ),
            "physical_requirements": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg block w-full p-2.5 custom-scrollbar",
                    "placeholder": "e.g., Must be able to lift 50 lbs, lots of kneeling...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If the farm already has tags stored as a JSON array, convert them to a
        # comma-separated string so the HTML input can render them properly for Tagify.
        if self.instance and self.instance.pk and self.instance.tags:
            if isinstance(self.instance.tags, list):
                self.initial["tags"] = ",".join(self.instance.tags)

    def clean_tags(self):
        """Extracts the Tagify JSON string back into a clean Python list of strings."""
        tags_data = self.cleaned_data.get("tags", "")
        if not tags_data:
            return []

        # Tagify sends data like: '[{"value":"Organic"},{"value":"No-Till"}]'
        try:
            parsed = json.loads(tags_data)
            return [item["value"] for item in parsed if "value" in item]
        except (ValueError, TypeError):
            # Fallback just in case standard comma-separated text got through
            return [t.strip() for t in tags_data.split(",") if t.strip()]
