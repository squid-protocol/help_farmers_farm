from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from datetime import datetime
from django.utils import timezone
import plotly.graph_objects as go

from .models import LogEntry
from .forms import LogEntryForm

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
import logging

logger = logging.getLogger(__name__)


@login_required
def log_hours_view(request):
    user = request.user
    current_year = datetime.now().year

    # Safely get the active farm (will be None if they are a brand new user)
    active_farm = getattr(request, "active_farm", None)

    # --- NEW: Redirect Unassigned to Profile ---
    if not active_farm:
        return redirect("profile")

    # 1. Handle New Shift Submissions
    if request.method == "POST":
        # --- NEW: Redirect Unassigned to Profile ---
        if not hasattr(request, "active_farm") or not request.active_farm:
            return redirect("profile")

        # --- THE READ-ONLY TOLLBOOTH ---
        if not active_farm.is_active_account:
            messages.error(
                request,
                "🛑 Trial Expired: Your farm's account is in Read-Only mode. "
                "Please contact your Farm Manager to upgrade.",
            )
            return redirect("log_hours")
        # --- END TOLLBOOTH ---

        form = LogEntryForm(request.POST, user=request.user)
        if form.is_valid():
            new_log = form.save(commit=False)
            new_log.volunteer = user
            new_log.farm = active_farm

            # Wrap the database hit in a try/except for stability
            try:
                new_log.save()
                messages.success(request, "Shift logged successfully!")
                return redirect("log_hours")
            except Exception:
                logger.exception("CRITICAL: Database error saving volunteer shift log.")
                messages.error(
                    request,
                    "There was a network issue saving your shift. Our engineering team has been notified.",
                )
    else:
        form = LogEntryForm(user=request.user)

    # 2. Fetch User's Data & Handle Pagination
    all_logs = LogEntry.objects.filter(volunteer=user).order_by("-date_logged")
    season_logs = all_logs.filter(date_logged__year=current_year)

    # --- Year-Based Paginator Logic ---
    try:
        history_year = int(request.GET.get("history_year", current_year))
    except ValueError:
        history_year = current_year

    # Get all distinct years this user has logged hours
    user_log_dates = all_logs.dates("date_logged", "year")
    available_years = sorted(list(set([d.year for d in user_log_dates])))

    # Always ensure the current year is in the list so they can navigate back to "today"
    if current_year not in available_years:
        available_years.append(current_year)
        available_years.sort()

    prev_year = None
    next_year = None

    if history_year in available_years:
        idx = available_years.index(history_year)
        if idx > 0:
            prev_year = available_years[idx - 1]
        if idx < len(available_years) - 1:
            next_year = available_years[idx + 1]

    history_shifts = all_logs.filter(date_logged__year=history_year)

    # 3. Calculate Core Stats
    season_hours = season_logs.aggregate(total=Sum("duration_hours"))["total"] or 0

    # 4. Calculate Commitment Progress & Pacing
    if user.work_commitment:
        target_hours = user.work_commitment.required_hours
        tier_name = user.work_commitment.name
    else:
        target_hours = 0
        tier_name = "Standard Volunteer"

    progress_pct = 0
    remaining_hours = 0
    required_pace = 0

    if target_hours > 0:
        progress_pct = min((season_hours / target_hours) * 100, 100)
        remaining_hours = max(target_hours - season_hours, 0)

        # The Pacing Engine
        if (
            request.active_farm.season_start
            and request.active_farm.season_end
            and remaining_hours > 0
        ):
            today = timezone.now().date()
            season_end = request.active_farm.season_end
            season_start = request.active_farm.season_start

            if today < season_end:
                if today < season_start:
                    days_remaining = (season_end - season_start).days
                else:
                    days_remaining = (season_end - today).days

                weeks_remaining = max(days_remaining / 7.0, 1.0)
                required_pace = remaining_hours / Decimal(str(weeks_remaining))

    # 5. Calculate "Fun Stats" (Based on this Season)
    activity_map = dict(LogEntry.ACTIVITY_CHOICES)

    top_veggie_data = (
        season_logs.exclude(crop__isnull=True)
        .values("crop__crop_name")
        .annotate(total=Sum("duration_hours"))
        .order_by("-total")
        .first()
    )
    top_veggie = top_veggie_data["crop__crop_name"] if top_veggie_data else "N/A"

    top_act_data = (
        season_logs.values("activity")
        .annotate(total=Sum("duration_hours"))
        .order_by("-total")
        .first()
    )
    top_act = (
        activity_map.get(top_act_data["activity"], "N/A") if top_act_data else "N/A"
    )

    # 6. Build Personal Breakdowns (Plotly Charts)
    veggie_chart_html = None
    activity_chart_html = None
    comparison_chart_html = None

    if season_hours > 0:
        # Veggie Chart
        veggie_breakdown = (
            season_logs.exclude(crop__isnull=True)
            .values("crop__crop_name")
            .annotate(total=Sum("duration_hours"))
        )
        v_labels = [item["crop__crop_name"] for item in veggie_breakdown]
        v_values = [item["total"] for item in veggie_breakdown]
        fig_v = go.Figure(
            data=[
                go.Pie(
                    labels=v_labels,
                    values=v_values,
                    hole=0.5,
                    marker_colors=[
                        "#10b981",
                        "#f59e0b",
                        "#3b82f6",
                        "#8b5cf6",
                        "#ef4444",
                    ],
                )
            ]
        )
        fig_v.update_layout(
            margin=dict(t=0, b=0, l=0, r=0), height=250, showlegend=False
        )
        fig_v.update_traces(textposition="inside", textinfo="percent+label")
        veggie_chart_html = fig_v.to_html(full_html=False, include_plotlyjs=False)

        # Activity Chart
        act_breakdown = season_logs.values("activity").annotate(
            total=Sum("duration_hours")
        )
        a_labels = [
            activity_map.get(item["activity"], "Other") for item in act_breakdown
        ]
        a_values = [item["total"] for item in act_breakdown]
        fig_a = go.Figure(
            data=[
                go.Pie(
                    labels=a_labels,
                    values=a_values,
                    hole=0.5,
                    marker_colors=[
                        "#10b981",
                        "#f59e0b",
                        "#ef4444",
                        "#8b5cf6",
                        "#94a3b8",
                        "#78350f",
                    ],
                )
            ]
        )
        fig_a.update_layout(
            margin=dict(t=0, b=0, l=0, r=0), height=250, showlegend=False
        )
        fig_a.update_traces(textposition="inside", textinfo="percent+label")
        activity_chart_html = fig_a.to_html(full_html=False, include_plotlyjs=False)

        # Farm-Wide Comparison Horizontal Bar Chart
        user_crop_hours = (
            season_logs.filter(crop__is_active=True)
            .values("crop__crop_name")
            .annotate(total=Sum("duration_hours"))
        )
        user_crop_dict = {
            item["crop__crop_name"]: float(item["total"] or 0)
            for item in user_crop_hours
        }

        farm_crop_hours = (
            LogEntry.objects.filter(
                farm=request.active_farm,
                date_logged__year=current_year,
                crop__is_active=True,
            )
            .values("crop__crop_name")
            .annotate(total=Sum("duration_hours"))
        )
        farm_crop_dict = {
            item["crop__crop_name"]: float(item["total"] or 0)
            for item in farm_crop_hours
        }

        from farms.models import Crop

        active_crops = list(
            Crop.objects.filter(farm=request.active_farm, is_active=True)
            .values_list("crop_name", flat=True)
            .order_by("-crop_name")
        )

        if active_crops:
            crop_names = []
            my_hours_list = []
            others_hours_list = []

            for crop_name in active_crops:
                my_h = user_crop_dict.get(crop_name, 0.0)
                farm_h = farm_crop_dict.get(crop_name, 0.0)

                crop_names.append(crop_name)
                my_hours_list.append(my_h)
                others_hours_list.append(max(0.0, farm_h - my_h))

            fig_comp = go.Figure(
                data=[
                    go.Bar(
                        name="My Hours",
                        y=crop_names,
                        x=my_hours_list,
                        orientation="h",
                        marker_color="#10b981",
                        hovertemplate="<b>%{y}</b><br>My Hours: %{x} hrs<extra></extra>",
                    ),
                    go.Bar(
                        name="Team Hours",
                        y=crop_names,
                        x=others_hours_list,
                        orientation="h",
                        marker_color="#cbd5e1",
                        hovertemplate="<b>%{y}</b><br>Team Hours: %{x} hrs<extra></extra>",
                    ),
                ]
            )
            fig_comp.update_layout(
                barmode="stack",
                plot_bgcolor="rgba(250,250,250,1)",
                paper_bgcolor="white",
                margin=dict(t=30, b=30, l=10, r=20),
                height=max(300, len(crop_names) * 35 + 100),
                showlegend=True,
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5
                ),
                hoverlabel=dict(bgcolor="white", font_size=13, font_color="black"),
                xaxis=dict(
                    title="Total Farm Hours",
                    showgrid=True,
                    gridcolor="rgba(200,200,200,0.3)",
                ),
                yaxis=dict(title="", tickfont=dict(size=12), automargin=True),
            )
            comparison_chart_html = fig_comp.to_html(
                full_html=False, include_plotlyjs=False
            )

    context = {
        "form": form,
        "current_year": current_year,
        "season_hours": round(season_hours, 1),
        "target_hours": target_hours,
        "tier_name": tier_name,
        "progress_pct": progress_pct,
        "remaining_hours": round(remaining_hours, 1),
        "required_pace": round(required_pace, 1),
        "top_veggie": top_veggie,
        "top_act": top_act,
        "veggie_chart": veggie_chart_html,
        "activity_chart": activity_chart_html,
        "comparison_chart": comparison_chart_html,
        "history_year": history_year,
        "prev_year": prev_year,
        "next_year": next_year,
        "history_shifts": history_shifts,
    }
    return render(request, "logs/log_hours.html", context)


@login_required
def master_log_directory(request):
    """The Master Ledger for Farm Managers."""
    is_manager = request.user.is_staff or request.user.role in [
        "account_manager",
        "farm_manager",
    ]
    if not is_manager:
        raise PermissionDenied("Only managers can view the master ledger.")

    # Fetch all logs for this farm, newest first, optimizing the database hit
    all_logs = (
        LogEntry.objects.filter(farm=request.active_farm)
        .select_related("volunteer", "crop")
        .order_by("-date_logged", "-created_at")
    )

    # Paginate by 50 rows per page to keep the UI lightning fast
    paginator = Paginator(all_logs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "logs/master_directory.html", {"page_obj": page_obj})


@login_required
def edit_log_view(request, log_id):
    """Universal Edit Router: Routes Managers and Volunteers safely."""
    # 1. Fetch the log, strictly isolated to the current active farm
    log = get_object_or_404(LogEntry, id=log_id, farm=request.active_farm)

    is_manager = request.user.is_staff or request.user.role in [
        "account_manager",
        "farm_manager",
    ]

    # 2. The Security Gate: Are they allowed to touch this?
    if not is_manager and log.volunteer != request.user:
        raise PermissionDenied("You do not have permission to edit someone else's log.")

    if request.method == "POST":
        form = LogEntryForm(request.POST, instance=log, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Shift updated successfully!")

            # Smart Routing: Send managers back to the directory, volunteers back to their dashboard
            if is_manager and log.volunteer != request.user:
                return redirect("master_log_directory")
            return redirect("log_hours")
    else:
        form = LogEntryForm(instance=log, user=request.user)

    return render(
        request,
        "logs/edit_log.html",
        {"form": form, "log": log, "is_manager": is_manager},
    )


@login_required
@require_POST
def delete_log_view(request, log_id):
    """Safely destroys a log entry, routing the user back to where they came from."""
    # 1. Fetch the log, strictly isolated to the active farm
    log = get_object_or_404(LogEntry, id=log_id, farm=request.active_farm)

    is_manager = request.user.is_staff or request.user.role in [
        "account_manager",
        "farm_manager",
    ]

    # 2. Security Gate: Only the owner OR a manager can delete it
    if not is_manager and log.volunteer != request.user:
        raise PermissionDenied(
            "You do not have permission to delete someone else's log."
        )

    # 3. Store the owner before we destroy the object so we know where to route
    was_my_log = log.volunteer == request.user

    # 4. Annihilate the record
    log.delete()
    messages.success(request, "Shift deleted successfully.")

    # 5. Smart Routing
    if is_manager and not was_my_log:
        return redirect("master_log_directory")
    return redirect("log_hours")
