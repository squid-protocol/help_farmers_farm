from django import forms
from .models import LogEntry
from farms.models import Crop


class LogEntryForm(forms.ModelForm):
    class Meta:
        model = LogEntry
        fields = ["date_logged", "crop", "activity", "duration_hours"]
        widgets = {
            "date_logged": forms.DateInput(attrs={"type": "date"}),
            "duration_hours": forms.NumberInput(attrs={"step": "0.25", "min": "0.25"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(LogEntryForm, self).__init__(*args, **kwargs)

        if self.user and self.user.farm:
            self.fields["crop"].queryset = Crop.objects.filter(farm=self.user.farm)
        else:
            self.fields["crop"].queryset = Crop.objects.none()

        # 1. Change the default '---------' to 'None/Generic'
        self.fields["crop"].empty_label = "None/Generic"

        # 2. Make it completely optional at the base form level
        # so our custom clean() method below can handle the strict logic
        self.fields["crop"].required = False

    def clean(self):
        cleaned_data = super().clean()
        activity = cleaned_data.get("activity")
        crop = cleaned_data.get("crop")

        # 3. The Conditional Logic
        if activity in ["O", "M"]:  # Off Season Work, Move Dirt
            # If they accidentally selected a crop, silently clear it out for them
            cleaned_data["crop"] = None

        elif activity in [
            "P",
            "T",
            "H",
            "C",
        ]:  # Planting, Tending, Harvesting, Cultivating
            # If they didn't select a crop, throw an error
            if not crop:
                self.add_error("crop", "A specific crop is required for this activity.")

        return cleaned_data
