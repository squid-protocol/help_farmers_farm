# --- Django Core & Utility Imports ---
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone

# --- Local App Imports (Farms) ---
from .models import Crop, WorkCommitment
from .forms import CropForm, VolunteerCreationForm, WorkCommitmentForm, FarmSettingsForm, VolunteerEditForm

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

    # Instantiate all forms
    crop_form = CropForm()
    volunteer_form = VolunteerCreationForm(request_user=request.user)
    commitment_form = WorkCommitmentForm()

    # The Farm Settings form (pre-filled with the current farm's data)
    farm_form = FarmSettingsForm(instance=my_farm)

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

        elif "submit_commitment" in request.POST:
            commitment_form = WorkCommitmentForm(request.POST)
            if commitment_form.is_valid():
                new_commitment = commitment_form.save(commit=False)
                new_commitment.farm = my_farm
                new_commitment.save()
                messages.success(request, "Work commitment added successfully!")
                return redirect("manager_dashboard")

        elif "submit_farm_settings" in request.POST:
            farm_form = FarmSettingsForm(request.POST, instance=my_farm)
            if farm_form.is_valid():
                farm_form.save()
                messages.success(request, "Farm settings updated successfully!")
                return redirect("manager_dashboard")

    # Fetch all the data to display in the lists
    crops = Crop.objects.filter(farm=my_farm).order_by("-is_active", "crop_name")
    volunteers = User.objects.filter(farm=my_farm).order_by("role", "username")
    commitments = WorkCommitment.objects.filter(farm=my_farm)

    context = {
        "farm": my_farm,
        "farm_form": farm_form,
        "crop_form": crop_form,
        "volunteer_form": volunteer_form,
        "commitment_form": commitment_form,
        "crops": crops,
        "volunteers": volunteers,
        "commitments": commitments,
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


# --- User & Crop Soft Deletes (Toggles) ---
@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def toggle_user_status_view(request, user_id):
    user_to_toggle = get_object_or_404(User, id=user_id)

    # RULE 1: Must be in the same farm
    if not request.user.is_staff and user_to_toggle.farm != request.user.farm:
        raise PermissionDenied("Cannot modify users outside your farm.")

    # RULE 2: Farm Managers cannot modify Account Managers or other Farm Managers
    if request.user.role == "farm_manager" and user_to_toggle.role in [
        "account_manager",
        "farm_manager",
    ]:
        raise PermissionDenied(
            "Farm Managers do not have permission to modify other managers."
        )

    # RULE 3: You can't deactivate yourself
    if request.user == user_to_toggle:
        raise PermissionDenied("You cannot deactivate yourself.")

    # The Soft Delete / Restore
    user_to_toggle.is_active = not user_to_toggle.is_active
    user_to_toggle.save()
    return redirect("manager_dashboard")


@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def toggle_crop_status_view(request, crop_id):
    crop_to_toggle = get_object_or_404(Crop, id=crop_id, farm=request.user.farm)

    crop_to_toggle.is_active = not crop_to_toggle.is_active
    crop_to_toggle.save()
    return redirect("manager_dashboard")


@login_required
def farm_impact_view(request):
    farm = request.user.farm
    # Just grab the active crops so we can populate the dropdown menu
    crops = Crop.objects.filter(farm=farm, is_active=True).order_by("crop_name")

    return render(request, "farms/farm_impact.html", {"farm": farm, "crops": crops})


# --- Volunteer Progress Report ---
@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def progress_report_view(request):
    farm = request.user.farm
    current_year = timezone.now().year

    # Grab all active volunteers on this farm
    volunteers = User.objects.filter(farm=farm).exclude(role="friend")

    # We will build a dictionary to group users by their commitment tier
    grouped_data = {}

    for vol in volunteers:
        # Calculate their total hours for the year
        logs = LogEntry.objects.filter(volunteer=vol, date_logged__year=current_year)
        total_hours = logs.aggregate(total=Sum("duration_hours"))["total"] or 0.0

        target = vol.work_commitment.required_hours if vol.work_commitment else 0
        pct = min((total_hours / target) * 100, 100) if target > 0 else 0

        vol_data = {
            "user": vol,
            "total_hours": round(total_hours, 1),
            "target": target,
            "pct": round(pct, 0),
        }

        # Use the commitment name as the group key, or 'Standard Volunteers'
        group_key = (
            vol.work_commitment.name if vol.work_commitment else "Standard Volunteers"
        )

        if group_key not in grouped_data:
            grouped_data[group_key] = []

        grouped_data[group_key].append(vol_data)

    # Sort each group so the volunteers with the LOWEST progress are at the top
    for key in grouped_data:
        grouped_data[key].sort(key=lambda x: x["total_hours"])

    context = {
        "farm": farm,
        "current_year": current_year,
        "grouped_data": grouped_data,
    }
    return render(request, "farms/progress_report.html", context)




@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def edit_crop_view(request, crop_id):
    crop = get_object_or_404(Crop, id=crop_id, farm=request.user.farm)
    if request.method == "POST":
        form = CropForm(request.POST, instance=crop)
        if form.is_valid():
            form.save()
            messages.success(request, f"{crop.crop_name} updated successfully!")
            return redirect("manager_dashboard")
    else:
        form = CropForm(instance=crop)
    return render(
        request,
        "farms/edit_item.html",
        {"form": form, "title": f"Edit Crop: {crop.crop_name}"},
    )


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def edit_volunteer_view(request, volunteer_id):
    volunteer = get_object_or_404(User, id=volunteer_id, farm=request.user.farm)

    # Prevent editing of higher-tier admins
    if request.user.role == "farm_manager" and volunteer.role in [
        "account_manager",
        "farm_manager",
    ]:
        if (
            request.user != volunteer
        ):  # They can edit themselves, but not other managers
            raise PermissionDenied("You cannot edit other managers.")

    if request.method == "POST":
        form = VolunteerEditForm(
            request.POST, instance=volunteer, request_user=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, f"{volunteer.username} updated successfully!")
            return redirect("manager_dashboard")
    else:
        form = VolunteerEditForm(instance=volunteer, request_user=request.user)
    return render(
        request,
        "farms/edit_item.html",
        {"form": form, "title": f"Edit Volunteer: {volunteer.username}"},
    )


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def edit_commitment_view(request, commitment_id):
    commitment = get_object_or_404(
        WorkCommitment, id=commitment_id, farm=request.user.farm
    )
    if request.method == "POST":
        form = WorkCommitmentForm(request.POST, instance=commitment)
        if form.is_valid():
            form.save()
            messages.success(request, "Work commitment updated successfully!")
            return redirect("manager_dashboard")
    else:
        form = WorkCommitmentForm(instance=commitment)
    return render(
        request,
        "farms/edit_item.html",
        {"form": form, "title": f"Edit Commitment: {commitment.name}"},
    )
