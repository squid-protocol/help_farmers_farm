from django import forms
from .models import LogEntry
from farms.models import Crop # Make sure to import Crop!

class LogEntryForm(forms.ModelForm):
    class Meta:
        model = LogEntry
        fields = ['date_logged', 'crop', 'activity', 'duration_hours']
        widgets = {
            'date_logged': forms.DateInput(attrs={'type': 'date'}),
        }

    # THE FIX: Add the user parameter to the initialization
    def __init__(self, *args, **kwargs):
        # Pop the user out of the kwargs before we initialize the standard form
        self.user = kwargs.pop('user', None)
        super(LogEntryForm, self).__init__(*args, **kwargs)

        # If a user is provided, and they belong to a farm, filter the crop dropdown
        if self.user and self.user.farm:
            self.fields['crop'].queryset = Crop.objects.filter(farm=self.user.farm)
        else:
            # If they don't belong to a farm, show them an empty list so they can't see other farms' crops
            self.fields['crop'].queryset = Crop.objects.none()