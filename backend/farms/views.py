# --- Django Core & Utility Imports ---
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Q
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone

# --- Local App Imports (Farms) ---
from .models import Farm, Crop, WorkCommitment, ComplianceForm, FarmProfile
from .forms import (
    CropForm,
    VolunteerCreationForm,
    WorkCommitmentForm,
    FarmSettingsForm,
    VolunteerEditForm,
    ComplianceFormSetup,
    FarmProfileForm,
)

# --- Other App Imports ---
from logs.models import LogEntry
from accounts.models import FarmMembership, FormSignature  # <-- UPDATED IMPORT
from farms.tasks import send_volunteer_welcome_email

User = get_user_model()


def is_manager(user):
    return user.is_staff or user.role in ["account_manager", "farm_manager"]


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def manager_dashboard(request):
    my_farm = request.active_farm

    # --- FIX: Catch managers/admins who aren't linked to a farm yet ---
    if not my_farm:
        messages.error(
            request,
            "You are not linked to a farm. Please assign yourself to a farm via a FarmMembership in the Admin panel.",
        )
        return redirect("admin:index" if request.user.is_staff else "/")

    crop_form = CropForm()
    volunteer_form = VolunteerCreationForm(request_user=request.user, farm=my_farm)
    commitment_form = WorkCommitmentForm()
    farm_form = FarmSettingsForm(instance=my_farm)
    compliance_setup_form = ComplianceFormSetup(farm=my_farm)

    profile, _ = FarmProfile.objects.get_or_create(farm=my_farm)
    profile_form = FarmProfileForm(instance=profile)

    if request.method == "POST":
        # --- THE READ-ONLY TOLLBOOTH (Anti-Spam & Security Lock) ---
        if not my_farm.is_active_account:
            messages.error(
                request,
                "🛑 Trial Expired: Your farm's account is in Read-Only mode. "
                "Please upgrade your plan in the Billing portal to make changes or send communications.",
            )
            return redirect("manager_dashboard")
        # --- END TOLLBOOTH ---

        if "submit_crop" in request.POST:
            crop_form = CropForm(request.POST)
            if crop_form.is_valid():
                new_crop = crop_form.save(commit=False)
                new_crop.farm = my_farm
                new_crop.save()
                messages.success(request, "Crop added successfully!")
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

        elif "submit_broadcast" in request.POST:
            from django_q.tasks import async_task

            subject = request.POST.get("broadcast_subject")
            body = request.POST.get("broadcast_body")
            audience = request.POST.get("audience", "all")
            specific_ids = request.POST.getlist("specific_users")

            # Fire and forget: send the heavy lifting to the background worker
            async_task(
                "farms.tasks.send_broadcast_email",
                farm_id=my_farm.id,
                subject=subject,
                custom_body=body,
                audience_value=audience,
                specific_ids=specific_ids,
            )

            messages.success(
                request,
                "Broadcast queued! Emails are being securely dispatched in the background.",
            )
            return redirect("manager_dashboard")

        elif "submit_welcome_email" in request.POST:
            # Handle the Welcome Email update from the Comms tab
            my_farm.welcome_email_subject = request.POST.get(
                "welcome_email_subject", ""
            )
            my_farm.welcome_email_body = request.POST.get("welcome_email_body", "")
            my_farm.save()
            messages.success(request, "Automated Welcome Email template updated!")
            return redirect("manager_dashboard")

        elif "submit_compliance_form" in request.POST:
            # --- NEW: FEATURE FLAG TOLLBOOTH ---
            if not my_farm.can_use_waivers:
                messages.error(
                    request,
                    "🛑 Upgrade Required: Digital Liability Waivers are only available on the Growth plan or higher.",
                )
                return redirect("manager_dashboard")

            compliance_setup_form = ComplianceFormSetup(
                request.POST, farm=my_farm
            )  # Pass farm here!
            if compliance_setup_form.is_valid():
                new_cform = compliance_setup_form.save(commit=False)
                new_cform.farm = my_farm
                new_cform.save()

                # CRITICAL: Save the specific users to the database!
                compliance_setup_form.save_m2m()

                messages.success(
                    request, f"Compliance Form '{new_cform.name}' added successfully!"
                )
                return redirect("manager_dashboard")

        elif "submit_profile" in request.POST:
            profile_form = FarmProfileForm(
                request.POST, request.FILES, instance=profile
            )
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Public Profile updated successfully!")
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

    # --- PROGRESS REPORT MERGE ---
    today = timezone.now().date()
    try:
        current_year = int(request.GET.get("year", today.year))
    except ValueError:
        current_year = today.year

    expected_pct = 0.0
    if my_farm.season_start and my_farm.season_end:
        if current_year < today.year:
            expected_pct = 100.0
        elif current_year == today.year:
            total_season_days = (my_farm.season_end - my_farm.season_start).days
            if total_season_days > 0:
                days_elapsed = (today - my_farm.season_start).days
                days_elapsed = max(0, min(days_elapsed, total_season_days))
                expected_pct = (days_elapsed / total_season_days) * 100.0

    prog_memberships = (
        FarmMembership.objects.filter(farm=my_farm, user__is_active=True)
        .exclude(user__role="friend")
        .select_related("user", "work_commitment")
        .annotate(
            total_hours=Sum(
                "user__logs__duration_hours",
                filter=Q(
                    user__logs__date_logged__year=current_year, user__logs__farm=my_farm
                ),
            )
        )
    )

    requires_waivers = my_farm.can_use_waivers
    active_forms = []

    if requires_waivers:
        all_active = ComplianceForm.objects.filter(
            farm=my_farm, is_active=True
        ).prefetch_related("assigned_users")
        active_forms = [f for f in all_active if f.is_currently_valid()]
        user_signatures = FormSignature.objects.filter(form__farm=my_farm).values_list(
            "user_id", "form_id"
        )
        sig_set = set(user_signatures)
    else:
        sig_set = set()

    grouped_data = {}

    for mem in prog_memberships:
        vol = mem.user
        total_hours = mem.total_hours or 0.0

        target = mem.work_commitment.required_hours if mem.work_commitment else 0
        pct = min((total_hours / target) * 100, 100) if target > 0 else 0
        is_behind = pct < expected_pct if target > 0 else False

        waiver_status = "manual"
        if requires_waivers:
            missing_waiver = False
            for cform in active_forms:
                applies = (
                    cform.assignment_type == "all" or vol in cform.assigned_users.all()
                )
                if applies:
                    if (vol.id, cform.id) not in sig_set:
                        missing_waiver = True
                        break
            waiver_status = "missing" if missing_waiver else "compliant"

        vol_data = {
            "user": vol,
            "total_hours": round(total_hours, 1),
            "target": target,
            "pct": round(pct, 0),
            "is_behind": is_behind,
            "waiver_status": waiver_status,
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
        "farm": my_farm,
        "current_year": current_year,
        "grouped_data": grouped_data,
        "expected_pct": expected_pct,
        "farm_form": farm_form,
        "profile_form": profile_form,
        "crop_form": crop_form,
        "volunteer_form": volunteer_form,
        "commitment_form": commitment_form,
        "compliance_setup_form": compliance_setup_form,
        "compliance_forms": compliance_forms,
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
        .annotate(
            total_hours=Sum(
                "user__logs__duration_hours",
                filter=Q(
                    user__logs__date_logged__year=current_year, user__logs__farm=farm
                ),
            )
        )
    )
    grouped_data = {}

    for mem in memberships:
        vol = mem.user
        total_hours = mem.total_hours or 0.0

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
    return redirect("volunteer_roster")


@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def toggle_crop_status_view(request, crop_id):
    crop_to_toggle = get_object_or_404(Crop, id=crop_id, farm=request.active_farm)
    crop_to_toggle.is_active = not crop_to_toggle.is_active
    crop_to_toggle.save()
    return redirect("manager_dashboard")


@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def toggle_compliance_status_view(request, form_id):
    """Allows managers to archive old waivers so new volunteers don't have to sign them."""
    compliance_form = get_object_or_404(
        ComplianceForm, id=form_id, farm=request.active_farm
    )
    compliance_form.is_active = not compliance_form.is_active
    compliance_form.save()
    messages.success(
        request,
        f"Compliance Form '{compliance_form.name}' is now {'Active' if compliance_form.is_active else 'Archived'}.",
    )
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

    # Fetch the membership bridge to get/set the current work commitment
    membership = FarmMembership.objects.get(user=volunteer, farm=request.active_farm)

    if request.method == "POST":
        form = VolunteerEditForm(
            request.POST,
            instance=volunteer,
            request_user=request.user,
            farm=request.active_farm,
        )
        if form.is_valid():
            form.save()

            # Save the new work commitment to the bridge table
            membership.work_commitment = form.cleaned_data.get("work_commitment")
            membership.save()

            messages.success(request, f"{volunteer.username} updated successfully!")
            return redirect("volunteer_roster")
    else:
        form = VolunteerEditForm(
            instance=volunteer,
            request_user=request.user,
            farm=request.active_farm,
            initial={"work_commitment": membership.work_commitment},
        )
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


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def compliance_audit_view(request, form_id):
    farm = request.active_farm

    # 1. Securely fetch the form, proving it belongs to this specific farm
    compliance_form = get_object_or_404(ComplianceForm, id=form_id, farm=farm)

    # 2. Fetch every signature for this specific form, ordered by newest first
    signatures = (
        FormSignature.objects.filter(form=compliance_form)
        .select_related("user")
        .order_by("-signed_at")
    )

    context = {
        "farm": farm,
        "compliance_form": compliance_form,
        "signatures": signatures,
    }
    return render(request, "farms/compliance_audit.html", context)


@login_required
def invite_link_view(request, token):
    """Path 1: The Magic Link (Zero Friction)"""
    farm = get_object_or_404(Farm, invite_token=token)

    # Create the bridge record. If they are already pending, this updates them to approved.
    membership, created = FarmMembership.objects.get_or_create(
        user=request.user, farm=farm
    )

    if created or not membership.is_approved:
        membership.is_approved = True
        membership.save()
        messages.success(request, f"You have successfully joined {farm.name}!")
    else:
        messages.info(request, f"You are already on the roster for {farm.name}.")

    # Set this farm as their active dashboard context
    request.session["active_farm_id"] = farm.id
    return redirect("log_hours")


@login_required
def farm_search_view(request):
    """Path 3: The Public Search Directory"""
    query = request.GET.get("q", "").strip()

    # 1. Base Query: ONLY show farms that have actively opted into the public directory
    farms = Farm.objects.filter(profile__is_public=True).select_related("profile")

    if query:
        farms = farms.filter(name__icontains=query)

    farms = farms[:15]  # Limit results to keep UI fast

    # 2. Get a list of IDs for farms they've already requested to join
    pending_requests = FarmMembership.objects.filter(
        user=request.user, is_approved=False
    ).values_list("farm_id", flat=True)

    return render(
        request,
        "farms/farm_search.html",
        {"farms": farms, "query": query, "pending_requests": pending_requests},
    )


@login_required
@require_POST
def request_join_farm_view(request, farm_id):
    """Path 3: Submit the Join Request with a Message"""
    farm = get_object_or_404(Farm, id=farm_id)
    message = request.POST.get("applicant_message", "").strip()

    membership, created = FarmMembership.objects.get_or_create(
        user=request.user,
        farm=farm,
        defaults={"is_approved": False, "applicant_message": message},
    )

    # If they somehow request again while pending, update their message
    if not created and not membership.is_approved and message:
        membership.applicant_message = message
        membership.save()

    messages.success(
        request, f"Your application to join {farm.name} has been sent to the manager!"
    )
    return redirect("farm_search")


@login_required
@require_POST
@user_passes_test(is_manager, login_url="/log-hours/")
def approve_membership_view(request, membership_id):
    """Manager Control: Approve or Deny pending volunteers"""
    membership = get_object_or_404(
        FarmMembership, id=membership_id, farm=request.active_farm
    )
    action = request.POST.get("action")

    if action == "approve":
        membership.is_approved = True
        membership.save()
        messages.success(
            request,
            f"Approved {membership.user.first_name}'s request to join the farm.",
        )

        # Fire the automated welcome email since they are now officially on the roster
        send_volunteer_welcome_email(
            membership.user.id, request.active_farm.id, raw_password="Set during signup"
        )

    elif action == "deny":
        membership.delete()
        messages.success(request, "Request denied and removed from the queue.")

    return redirect("volunteer_roster")


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def volunteer_roster_view(request):
    my_farm = request.active_farm
    volunteer_form = VolunteerCreationForm(request_user=request.user, farm=my_farm)

    if request.method == "POST":
        # --- THE READ-ONLY TOLLBOOTH ---
        if not my_farm.is_active_account:
            messages.error(
                request,
                "🛑 Trial Expired: Your farm's account is in Read-Only mode. "
                "Please upgrade your plan in the Billing portal to make changes.",
            )
            return redirect("volunteer_roster")

        if "submit_volunteer" in request.POST:
            current_volunteers = User.objects.filter(
                memberships__farm=my_farm,
                is_active=True,
            ).count()

            tier = getattr(my_farm, "subscription_tier", "starter")
            capacity_reached = False
            limit = 0

            if tier == "starter" and current_volunteers >= 50:
                capacity_reached = True
                limit = 50
            elif tier == "growth" and current_volunteers >= 200:
                capacity_reached = True
                limit = 200

            if capacity_reached:
                messages.error(
                    request,
                    f"🛑 Limit Reached: The {tier.title()} plan allows a maximum of {limit} "
                    "active volunteers. Please archive old volunteers or upgrade.",
                )
                return redirect("volunteer_roster")

            volunteer_form = VolunteerCreationForm(
                request.POST, request_user=request.user, farm=my_farm
            )
            if volunteer_form.is_valid():
                new_user = volunteer_form.save(commit=False)
                new_user.set_password(volunteer_form.cleaned_data["password"])
                new_user.role = "volunteer"
                new_user.is_email_verified = (
                    True  # Auto-verify manager-created accounts
                )
                new_user.save()

                FarmMembership.objects.create(
                    user=new_user,
                    farm=my_farm,
                    is_approved=True,
                    agreed_to_waiver=True,
                    work_commitment=volunteer_form.cleaned_data.get("work_commitment"),
                )

                email_status = send_volunteer_welcome_email(
                    user_id=new_user.id,
                    farm_id=my_farm.id,
                    raw_password=volunteer_form.cleaned_data["password"],
                )

                messages.success(
                    request, f"Volunteer created successfully! {email_status}"
                )
                return redirect("volunteer_roster")

    # Fetch all memberships in one optimized query
    all_memberships = (
        FarmMembership.objects.filter(farm=my_farm)
        .select_related("user", "work_commitment")
        .order_by("user__first_name", "user__username")
    )

    applicants = []
    active_vols = []
    past_vols = []

    # Sort them into their respective tabs
    for m in all_memberships:
        if not m.is_approved:
            applicants.append(m)
        else:
            if m.user.is_active and m.user.role != "friend":
                active_vols.append(m)
            else:
                past_vols.append(m)

    context = {
        "farm": my_farm,
        "applicants": applicants,
        "active_vols": active_vols,
        "past_vols": past_vols,
        "volunteer_form": volunteer_form,
    }
    return render(request, "farms/volunteer_roster.html", context)
