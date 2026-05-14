from django import forms
from .models import LogEntry
from farms.models import Crop


class LogEntryForm(forms.ModelForm):
    class Meta:
        model = LogEntry
        fields = ["date_logged", "crop", "activity", "duration_hours"]
        widgets = {
            "date_logged": forms.DateInput(attrs={"type": "date"}),
            # THE FIX: Force the browser spinner to step by quarter-hours
            "duration_hours": forms.NumberInput(attrs={"step": "0.25", "min": "0.25"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(LogEntryForm, self).__init__(*args, **kwargs)

        if self.user and self.user.farm:
            self.fields["crop"].queryset = Crop.objects.filter(farm=self.user.farm)
        else:
            self.fields["crop"].queryset = Crop.objects.none()