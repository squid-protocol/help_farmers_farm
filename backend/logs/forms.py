from django import forms
from .models import LogEntry
from farms.models import Crop

class LogEntryForm(forms.ModelForm):
    class Meta:
        model = LogEntry
        # We DO NOT include 'volunteer' or 'farm' here. 
        # The user shouldn't choose those; the server will assign them automatically!
        fields = ['date_logged', 'crop', 'activity', 'duration_hours']
        
        # This tells Django to render a nice calendar picker for the date
        widgets = {
            'date_logged': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # We extract the user from the kwargs before initializing the form
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # CRITICAL MULTI-TENANCY LOGIC: 
        # Filter the crop dropdown to ONLY show active crops from this specific volunteer's farm.
        if user and user.farm:
            self.fields['crop'].queryset = Crop.objects.filter(farm=user.farm, is_active=True)
        else:
            self.fields['crop'].queryset = Crop.objects.none()