from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Crop
from .forms import CropForm, VolunteerCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

def is_manager(user):
    return user.is_staff or user.role in ['account_manager', 'farm_manager']

@login_required
@user_passes_test(is_manager, login_url='/log-hours/')
def manager_dashboard(request):
    my_farm = request.user.farm

    # Initialize empty forms
    crop_form = CropForm()
    volunteer_form = VolunteerCreationForm()

    if request.method == 'POST':
        # Check if the manager submitted the Crop form
        if 'submit_crop' in request.POST:
            crop_form = CropForm(request.POST)
            if crop_form.is_valid():
                new_crop = crop_form.save(commit=False)
                new_crop.farm = my_farm
                new_crop.save()
                return redirect('manager_dashboard')
        
        # Check if the manager submitted the Volunteer form
        elif 'submit_volunteer' in request.POST:
            volunteer_form = VolunteerCreationForm(request.POST)
            if volunteer_form.is_valid():
                new_user = volunteer_form.save(commit=False)
                new_user.farm = my_farm
                # CRITICAL: We must use set_password to securely hash it!
                new_user.set_password(volunteer_form.cleaned_data['password'])
                new_user.save()
                return redirect('manager_dashboard')

    # Fetch data for the lists
    crops = Crop.objects.filter(farm=my_farm).order_by('-is_active', 'crop_name')
    volunteers = User.objects.filter(farm=my_farm).order_by('role', 'username')

    context = {
        'farm': my_farm,
        'crop_form': crop_form,
        'volunteer_form': volunteer_form,
        'crops': crops,
        'volunteers': volunteers,
    }
    return render(request, 'farms/manager_dashboard.html', context)