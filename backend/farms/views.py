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
from .models import Crop, WorkCommitment, ComplianceForm  # <-- ADDED ComplianceForm
from .forms import (
    CropForm,
    VolunteerCreationForm,
    WorkCommitmentForm,
    FarmSettingsForm,
    VolunteerEditForm,
    ComplianceFormSetup,  # <-- ADDED ComplianceFormSetup
)

# --- Other App Imports ---
from logs.models import LogEntry
from accounts.models import FarmMembership  # <-- ADDED IMPORT

User = get_user_model()


def is_manager(user):
    return user.is_staff or user.role in ["account_manager", "farm_manager"]


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def manager_dashboard(request):
    my_farm = request.active_farm

    crop_form = CropForm()
    volunteer_form = VolunteerCreationForm(request_user=request.user)
    commitment_form = WorkCommitmentForm()
    farm_form = FarmSettingsForm(instance=my_farm)
    compliance_setup_form = ComplianceFormSetup()

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
            # --- THE CAPACITY TOLLBOOTH ---
            # 1. Count how many active standard volunteers this farm currently has
            current_volunteers = User.objects.filter(
                farmmembership__farm=my_farm,
                is_active=True,
                role="volunteer",  # Only count standard volunteers, managers are free
            ).count()

            # 2. Check the capacity limits based on their Stripe tier
            tier = getattr(
                my_farm, "subscription_tier", "starter"
            )  # Default to starter if missing
            capacity_reached = False
            limit = 0

            if tier == "starter" and current_volunteers >= 50:
                capacity_reached = True
                limit = 50
            elif tier == "growth" and current_volunteers >= 200:
                capacity_reached = True
                limit = 200

            # 3. Drop the gate if they are full
            if capacity_reached:
                messages.error(
                    request,
                    f"🛑 Limit Reached: The {tier.title()} plan allows a maximum of {limit} "
                    "active volunteers. Please archive old volunteers or upgrade your "
                    "plan in the Billing portal.",
                )
                return redirect("manager_dashboard")

            # If they pass the tollbooth, process the form...
            volunteer_form = VolunteerCreationForm(
                request.POST, request_user=request.user
            )
            if volunteer_form.is_valid():
                new_user = volunteer_form.save(commit=False)
                new_user.set_password(volunteer_form.cleaned_data["password"])
                # Ensure they are saved as a volunteer
                new_user.role = "volunteer"
                new_user.save()

                # --- NEW: Create the Bridge Record! ---
                FarmMembership.objects.create(
                    user=new_user,
                    farm=my_farm,
                    is_approved=True,
                    agreed_to_waiver=True,
                    work_commitment=volunteer_form.cleaned_data.get("work_commitment"),
                )

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

        elif "submit_compliance_form" in request.POST:
            compliance_setup_form = ComplianceFormSetup(request.POST)
            if compliance_setup_form.is_valid():
                new_cform = compliance_setup_form.save(commit=False)
                new_cform.farm = my_farm
                new_cform.save()
                messages.success(
                    request, f"Compliance Form '{new_cform.name}' added successfully!"
                )
                return redirect("manager_dashboard")

    # Fetch data using the membership bridge
    crops = Crop.objects.filter(farm=my_farm).order_by("-is_active", "crop_name")

    # We now get volunteers by looking through the FarmMembership bridge
    memberships = FarmMembership.objects.filter(farm=my_farm).select_related(
        "user", "work_commitment"
    )
    volunteers = [m.user for m in memberships]

    commitments = WorkCommitment.objects.filter(farm=my_farm)

    # --- THE MISSING QUERY ---
    compliance_forms = ComplianceForm.objects.filter(farm=my_farm).order_by(
        "-is_active", "name"
    )

    active_crop_count = crops.filter(is_active=True).count()

    commitment_summary = []
    for c in commitments:
        commitment_summary.append(
            {
                "name": c.name,
                "symbol": getattr(c, "symbol", "⏱️"),
                "count": sum(
                    1
                    for m in memberships
                    if m.work_commitment == c
                    and m.user.is_active
                    and m.user.role != "friend"
                ),
            }
        )

    standard_vol_count = sum(
        1
        for m in memberships
        if m.work_commitment is None and m.user.is_active and m.user.role != "friend"
    )

    recent_notes = (
        LogEntry.objects.filter(farm=my_farm)
        .exclude(notes__isnull=True)
        .exclude(notes__exact="")
        .select_related("volunteer", "crop")
        .order_by("-date_logged")
    )

    context = {
        "farm": my_farm,
        "farm_form": farm_form,
        "crop_form": crop_form,
        "volunteer_form": volunteer_form,
        "commitment_form": commitment_form,
        "compliance_setup_form": compliance_setup_form,  # <-- NEW
        "compliance_forms": compliance_forms,  # <-- NEW
        "crops": crops,
        "volunteers": volunteers,
        "commitments": commitments,
        "active_crop_count": active_crop_count,
        "commitment_summary": commitment_summary,
        "standard_vol_count": standard_vol_count,
        "recent_notes": recent_notes,
    }
    return render(request, "farms/manager_dashboard.html", context)


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def volunteer_detail_view(request, volunteer_id):
    volunteer = get_object_or_404(User, id=volunteer_id)

    # Check if they have a membership to the manager's farm
    if not FarmMembership.objects.filter(
        user=volunteer, farm=request.active_farm
    ).exists():
        if not request.user.is_staff:
            raise PermissionDenied(
                "You do not have permission to view volunteers outside your farm."
            )

    user_logs = LogEntry.objects.filter(volunteer=volunteer, farm=request.active_farm)
    total_hours = (
        user_logs.aggregate(Sum("duration_hours"))["duration_hours__sum"] or 0.0
    )
    recent_logs = user_logs.order_by("-date_logged")[:15]

    context = {
        "volunteer": volunteer,
        "total_hours": round(total_hours, 1),
        "recent_logs": recent_logs,
    }
    return render(request, "farms/volunteer_detail.html", context)


@login_required
def farm_impact_view(request):
    farm = request.active_farm
    crops = Crop.objects.filter(farm=farm, is_active=True).order_by("crop_name")
    return render(request, "farms/farm_impact.html", {"farm": farm, "crops": crops})


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def progress_report_view(request):
    farm = request.active_farm
    today = timezone.now().date()

    try:
        current_year = int(request.GET.get("year", today.year))
    except ValueError:
        current_year = today.year

    expected_pct = 0.0
    if farm.season_start and farm.season_end:
        if current_year < today.year:
            expected_pct = 100.0
        elif current_year == today.year:
            total_season_days = (farm.season_end - farm.season_start).days
            if total_season_days > 0:
                days_elapsed = (today - farm.season_start).days
                days_elapsed = max(0, min(days_elapsed, total_season_days))
                expected_pct = (days_elapsed / total_season_days) * 100.0

    memberships = (
        FarmMembership.objects.filter(farm=farm, user__is_active=True)
        .exclude(user__role="friend")
        .select_related("user", "work_commitment")
    )
    grouped_data = {}

    for mem in memberships:
        vol = mem.user
        logs = LogEntry.objects.filter(
            volunteer=vol, date_logged__year=current_year, farm=farm
        )
        total_hours = logs.aggregate(total=Sum("duration_hours"))["total"] or 0.0

        target = mem.work_commitment.required_hours if mem.work_commitment else 0
        pct = min((total_hours / target) * 100, 100) if target > 0 else 0
        is_behind = pct < expected_pct if target > 0 else False

        vol_data = {
            "user": vol,
            "total_hours": round(total_hours, 1),
            "target": target,
            "pct": round(pct, 0),
            "is_behind": is_behind,
        }

        group_key = (
            mem.work_commitment.name if mem.work_commitment else "Standard Volunteers"
        )

        if group_key not in grouped_data:
            grouped_data[group_key] = []
        grouped_data[group_key].append(vol_data)

    for key in grouped_data:
        grouped_data[key].sort(key=lambda x: x["total_hours"])

    context = {
        "farm": farm,
        "current_year": current_year,
        "grouped_data": grouped_data,
        "expected_pct": expected_pct,
    }
    return render(request, "farms/progress_report.html", context)


@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def toggle_user_status_view(request, user_id):
    user_to_toggle = get_object_or_404(User, id=user_id)

    if not FarmMembership.objects.filter(
        user=user_to_toggle, farm=request.active_farm
    ).exists():
        if not request.user.is_staff:
            raise PermissionDenied("Cannot modify users outside your farm.")

    if request.user.role == "farm_manager" and user_to_toggle.role in [
        "account_manager",
        "farm_manager",
    ]:
        raise PermissionDenied(
            "Farm Managers do not have permission to modify other managers."
        )

    if request.user == user_to_toggle:
        raise PermissionDenied("You cannot deactivate yourself.")

    user_to_toggle.is_active = not user_to_toggle.is_active
    user_to_toggle.save()
    return redirect("manager_dashboard")


@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def toggle_crop_status_view(request, crop_id):
    crop_to_toggle = get_object_or_404(Crop, id=crop_id, farm=request.active_farm)
    crop_to_toggle.is_active = not crop_to_toggle.is_active
    crop_to_toggle.save()
    return redirect("manager_dashboard")


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def edit_crop_view(request, crop_id):
    crop = get_object_or_404(Crop, id=crop_id, farm=request.active_farm)
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
    volunteer = get_object_or_404(User, id=volunteer_id)

    if not FarmMembership.objects.filter(
        user=volunteer, farm=request.active_farm
    ).exists():
        if not request.user.is_staff:
            raise PermissionDenied("Cannot edit users outside your farm.")

    if request.user.role == "farm_manager" and volunteer.role in [
        "account_manager",
        "farm_manager",
    ]:
        if request.user != volunteer:
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
        WorkCommitment, id=commitment_id, farm=request.active_farm
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


@login_required
@require_POST
def switch_active_farm(request):
    farm_id = request.POST.get("farm_id")
    if farm_id:
        # Security check: Prove they are actually a member before switching
        from accounts.models import FarmMembership

        is_member = FarmMembership.objects.filter(
            user=request.user, farm_id=farm_id, is_approved=True
        ).exists()

        if is_member:
            request.session["active_farm_id"] = int(farm_id)
            messages.success(request, "Switched workspaces successfully.")

    # Send them back to the exact page they were just looking at
    next_url = request.POST.get("next", "/log-hours/")
    return redirect(next_url)
