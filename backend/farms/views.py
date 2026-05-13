from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.views.decorators.http import require_POST


from .models import Crop
from .forms import CropForm, VolunteerCreationForm
from logs.models import LogEntry  # Pulls the logs so we can calculate hours
import plotly.graph_objects as go

User = get_user_model()


# --- Security Check ---
def is_manager(user):
    return user.is_staff or user.role in ["account_manager", "farm_manager"]


@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def manager_dashboard(request):
    my_farm = request.user.farm

    crop_form = CropForm()
    # 1. Pass the logged-in user to the empty form
    volunteer_form = VolunteerCreationForm(request_user=request.user)

    if request.method == "POST":
        if "submit_crop" in request.POST:
            crop_form = CropForm(request.POST)
            if crop_form.is_valid():
                new_crop = crop_form.save(commit=False)
                new_crop.farm = my_farm
                new_crop.save()
                return redirect("manager_dashboard")

        elif "submit_volunteer" in request.POST:
            # 2. Pass the logged-in user to the submitted form
            volunteer_form = VolunteerCreationForm(
                request.POST, request_user=request.user
            )
            if volunteer_form.is_valid():
                new_user = volunteer_form.save(commit=False)
                new_user.farm = my_farm
                new_user.set_password(volunteer_form.cleaned_data["password"])
                new_user.save()
                return redirect("manager_dashboard")

    crops = Crop.objects.filter(farm=my_farm).order_by("-is_active", "crop_name")
    volunteers = User.objects.filter(farm=my_farm).order_by("role", "username")

    context = {
        "farm": my_farm,
        "crop_form": crop_form,
        "volunteer_form": volunteer_form,
        "crops": crops,
        "volunteers": volunteers,
    }
    return render(request, "farms/manager_dashboard.html", context)


# --- The New Volunteer Detail View ---
@login_required
@user_passes_test(is_manager, login_url="/log-hours/")
def volunteer_detail_view(request, volunteer_id):
    # SECURE: Forces the requested user to belong to the manager's farm
    volunteer = get_object_or_404(User, id=volunteer_id, farm=request.user.farm)

    # 2. SECURITY: Ensure the manager is looking at a volunteer from their OWN farm
    if not request.user.is_staff and volunteer.farm != request.user.farm:
        raise PermissionDenied(
            "You do not have permission to view volunteers outside your farm."
        )

    # 3. Fetch logs and crunch the numbers
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

    # 1. THE MAGIC ORM QUERY: PostgreSQL groups by crop & activity, and sums the hours instantly.
    aggregated_data = (
        LogEntry.objects.filter(farm=farm)
        .values("crop__crop_name", "activity")
        .annotate(total_hours=Sum("duration_hours"))
        .order_by("crop__crop_name")
    )

    # 2. Extract the unique crop names for our X-axis
    crops = sorted(list(set([item["crop__crop_name"] for item in aggregated_data])))

    # 3. Define your colors (Semantic, modern SaaS palette)
    activity_colors = {
        "P": "#10b981",  # Planting (Emerald Green - Growth)
        "T": "#f59e0b",  # Tending (Warm Amber/Yellow - Sun/Maintenance)
        "H": "#ef4444",  # Harvesting (Ripe Red - Yield/Action)
        "O": "#94a3b8",  # Off-Season (Dormant Slate Grey - Rest)
    }

    # We grab the readable labels from your models.py choices
    activity_labels = dict(LogEntry.ACTIVITY_CHOICES)

    # 4. Build the Plotly Figure
    fig = go.Figure()

    for act_code, act_label in activity_labels.items():
        y_values = []
        for crop in crops:
            # Find the total hours for this specific crop + activity combo. Default to 0.
            hours = next(
                (
                    float(item["total_hours"])
                    for item in aggregated_data
                    if item["crop__crop_name"] == crop and item["activity"] == act_code
                ),
                0,
            )
            y_values.append(hours)

        # Only draw the bar if there is actually data for this activity
        if sum(y_values) > 0:
            fig.add_trace(
                go.Bar(
                    name=act_label,
                    x=crops,
                    y=y_values,
                    marker_color=activity_colors.get(act_code),
                )
            )

    # 5. Make it look beautiful and responsive
    fig.update_layout(
        barmode="stack",
        title=dict(
            text=f"Seasonal Labor Hours: {farm.name}", font=dict(size=22), x=0.5
        ),
        plot_bgcolor="rgba(250,250,250,1)",
        paper_bgcolor="white",
        margin=dict(l=50, r=50, t=80, b=100),
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="white", font_size=15, font_color="black"),
    )

    # 6. Convert the interactive graph to a safe HTML string so Tailwind can render it
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    return render(
        request, "farms/farm_impact.html", {"chart": chart_html, "farm": farm}
    )
