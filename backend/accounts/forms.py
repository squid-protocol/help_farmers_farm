from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "address",
            "username",
        ]
        widgets = {
            "phone_number": forms.TextInput(attrs={"placeholder": "(555) 123-4567"}),
            "address": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "123 Harvest Lane\nFarmingville, MI 48103",
                }
            ),
        }
        help_texts = {
            "phone_number": "Format: (555) 123-4567 or +15551234567",
            "address": "We require a physical address to legally validate your electronic signature.",
        }


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
