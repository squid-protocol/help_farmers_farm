# --- Django Core & Utility Imports ---
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.views.decorators.http import require_POST
from django.contrib import messages

# --- Local App Imports (Farms) ---
from .models import Crop, WorkCommitment
from .forms import CropForm, VolunteerCreationForm, WorkCommitmentForm

# --- Other App Imports ---
from logs.models import LogEntry

User = get_user_model()


# --- Security Check ---
def is_manager(user):
    return user.is_staff or user.role in ["account_manager", "farm_manager"]


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def manager_dashboard(request):
    my_farm = request.user.farm

    # Instantiate all three empty forms
    crop_form = CropForm()
    volunteer_form = VolunteerCreationForm(request_user=request.user)
    commitment_form = WorkCommitmentForm()  # <-- NEW

    if request.method == "POST":
        if "submit_crop" in request.POST:
            crop_form = CropForm(request.POST)
            if crop_form.is_valid():
                new_crop = crop_form.save(commit=False)
                new_crop.farm = my_farm
                new_crop.save()
                messages.success(request, "Crop added successfully!")
                return redirect("manager_dashboard")

        elif "submit_volunteer" in request.POST:
            volunteer_form = VolunteerCreationForm(
                request.POST, request_user=request.user
            )
            if volunteer_form.is_valid():
                new_user = volunteer_form.save(commit=False)
                new_user.farm = my_farm
                new_user.set_password(volunteer_form.cleaned_data["password"])
                new_user.save()
                messages.success(request, "Volunteer created successfully!")
                return redirect("manager_dashboard")

        # <-- NEW: Handle Work Commitment Submission -->
        elif "submit_commitment" in request.POST:
            commitment_form = WorkCommitmentForm(request.POST)
            if commitment_form.is_valid():
                new_commitment = commitment_form.save(commit=False)
                new_commitment.farm = my_farm
                new_commitment.save()
                messages.success(request, "Work commitment added successfully!")
                return redirect("manager_dashboard")

    # Fetch all the data to display in the lists
    crops = Crop.objects.filter(farm=my_farm).order_by("-is_active", "crop_name")
    volunteers = User.objects.filter(farm=my_farm).order_by("role", "username")
    commitments = WorkCommitment.objects.filter(farm=my_farm)  # <-- NEW

    context = {
        "farm": my_farm,
        "crop_form": crop_form,
        "volunteer_form": volunteer_form,
        "commitment_form": commitment_form,  # <-- NEW
        "crops": crops,
        "volunteers": volunteers,
        "commitments": commitments,  # <-- NEW
    }
    return render(request, "farms/manager_dashboard.html", context)


# --- The Volunteer Detail View ---
@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def volunteer_detail_view(request, volunteer_id):
    # SECURE: Forces the requested user to belong to the manager's farm
    volunteer = get_object_or_404(User, id=volunteer_id, farm=request.user.farm)

    # SECURITY: Ensure the manager is looking at a volunteer from their OWN farm
    if not request.user.is_staff and volunteer.farm != request.user.farm:
        raise PermissionDenied(
            "You do not have permission to view volunteers outside your farm."
        )

    # Fetch logs and crunch the numbers
    user_logs = LogEntry.objects.filter(volunteer=volunteer)
    total_hours = (
        user_logs.aggregate(Sum("duration_hours"))["duration_hours__sum"] or 0.0
    )

    # Grab their 15 most recent shifts so the manager has good visibility
    recent_logs = user_logs.order_by("-date_logged")[:15]

    context = {
        "volunteer": volunteer,
        "total_hours": round(total_hours, 1),
        "recent_logs": recent_logs,
    }
    return render(request, "farms/volunteer_detail.html", context)


@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def remove_user_view(request, user_id):
    user_to_remove = get_object_or_404(User, id=user_id)

    # RULE 1: Must be in the same farm
    if not request.user.is_staff and user_to_remove.farm != request.user.farm:
        raise PermissionDenied("Cannot remove users outside your farm.")

    # RULE 2: Farm Managers cannot delete Account Managers or other Farm Managers
    if request.user.role == "farm_manager" and user_to_remove.role in [
        "account_manager",
        "farm_manager",
    ]:
        raise PermissionDenied(
            "Farm Managers do not have permission to remove other managers."
        )

    # RULE 3: You can't delete yourself
    if request.user == user_to_remove:
        raise PermissionDenied("You cannot remove yourself.")

    # If they pass all security checks, delete the user and reload the dashboard
    user_to_remove.delete()
    return redirect("manager_dashboard")


@login_required
def farm_impact_view(request):
    farm = request.user.farm
    # Just grab the active crops so we can populate the dropdown menu
    crops = Crop.objects.filter(farm=farm, is_active=True).order_by("crop_name")

    return render(request, "farms/farm_impact.html", {"farm": farm, "crops": crops})


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def manage_work_commitments(request):
    farm = request.user.farm
    commitments = WorkCommitment.objects.filter(farm=farm)

    if request.method == "POST":
        form = WorkCommitmentForm(request.POST)
        if form.is_valid():
            # FIXED: commitFalse=True is now commit=False
            new_commitment = form.save(commit=False)
            new_commitment.farm = farm
            new_commitment.save()
            messages.success(request, "Work commitment added successfully!")
            return redirect("manage_work_commitments")
    else:
        form = WorkCommitmentForm()

    return render(
        request,
        "farms/manage_commitments.html",
        {"form": form, "commitments": commitments, "farm": farm},
    )
