import re
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "farming_motto",
            "phone_number",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "username",
        ]
        widgets = {
            "phone_number": forms.TextInput(attrs={"placeholder": "(555) 123-4567"}),
            "address_line1": forms.TextInput(attrs={"placeholder": "123 Harvest Lane"}),
            "state": forms.TextInput(attrs={"placeholder": "MI"}),
            "postal_code": forms.TextInput(attrs={"placeholder": "48103"}),
        }
        help_texts = {
            "phone_number": "Format: (555) 123-4567 or +15551234567",
            "address_line1": "We require a physical address to legally validate electronic signatures.",
        }

    def clean_state(self):
        """Silently enforce uppercase 2-letter state codes."""
        state = self.cleaned_data.get("state", "")
        if state:
            state = state.strip().upper()
            if len(state) != 2 or not state.isalpha():
                raise forms.ValidationError(
                    "Please enter a valid 2-letter state abbreviation (e.g., MI)."
                )
        return state

    def clean_postal_code(self):
        """Enforce standard 5-digit or 9-digit US ZIP codes."""
        postal_code = self.cleaned_data.get("postal_code", "")
        if postal_code:
            postal_code = postal_code.strip()
            if not re.match(r"^\d{5}(-\d{4})?$", postal_code):
                raise forms.ValidationError(
                    "Please enter a valid 5-digit ZIP code (e.g., 49302)."
                )
        return postal_code

    def clean_city(self):
        """Silently enforce Title Case for cities."""
        city = self.cleaned_data.get("city", "")
        if city:
            return city.strip().title()
        return city


# --- Update the standard Login Form label ---
class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or Email"


# --- The Form for claiming a legacy account ---
class AccountClaimForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Create a secure password"})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm your password"})
    )

    class Meta:
        model = User
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "Enter your email address"})
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


# --- REGISTRATION PIPELINE FORMS ---


class VolunteerSignUpForm(UserCreationForm):
    """Lightweight registration for unattached volunteers."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email", "phone_number")
        # Notice: 'address' is explicitly omitted


class FarmSignUpForm(UserCreationForm):
    """Heavy registration that requires address and provisions a new farm workspace."""

    # Manager Specific Fields (Address is mandatory here)
    address_line1 = forms.CharField(
        max_length=255, required=True, label="Street Address"
    )
    address_line2 = forms.CharField(
        max_length=255, required=False, label="Apt / Suite / Other"
    )
    city = forms.CharField(max_length=100, required=True, label="City")
    state = forms.CharField(max_length=2, required=True, label="State (e.g., MI)")
    postal_code = forms.CharField(
        max_length=20, required=True, label="ZIP / Postal Code"
    )

    # Farm Workspace Fields
    farm_name = forms.CharField(max_length=255, required=True, label="Farm Name")
    farm_phone = forms.CharField(
        max_length=20, required=True, label="Farm Phone Number"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
        )

    def clean_state(self):
        """Silently enforce uppercase 2-letter state codes."""
        state = self.cleaned_data.get("state", "")
        if state:
            state = state.strip().upper()
            if len(state) != 2 or not state.isalpha():
                raise forms.ValidationError(
                    "Please enter a valid 2-letter state abbreviation (e.g., MI)."
                )
        return state

    def clean_postal_code(self):
        """Enforce standard 5-digit or 9-digit US ZIP codes."""
        postal_code = self.cleaned_data.get("postal_code", "")
        if postal_code:
            postal_code = postal_code.strip()
            if not re.match(r"^\d{5}(-\d{4})?$", postal_code):
                raise forms.ValidationError(
                    "Please enter a valid 5-digit ZIP code (e.g., 49302)."
                )
        return postal_code

    def clean_city(self):
        """Silently enforce Title Case for cities."""
        city = self.cleaned_data.get("city", "")
        if city:
            return city.strip().title()
        return city
