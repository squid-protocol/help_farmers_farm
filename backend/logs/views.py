from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from datetime import datetime
from django.utils import timezone
import plotly.graph_objects as go

from .models import LogEntry
from .forms import LogEntryForm


@login_required
def log_hours_view(request):
    user = request.user
    current_year = datetime.now().year

    # 1. Handle New Shift Submissions
    if request.method == "POST":
        form = LogEntryForm(request.POST, user=request.user)
        if form.is_valid():
            new_log = form.save(commit=False)
            new_log.volunteer = user
            new_log.farm = user.farm
            new_log.save()
            messages.success(request, "Shift logged successfully!")
            return redirect("log_hours")
    else:
        form = LogEntryForm(user=request.user)

    # 2. Fetch User's Data
    all_logs = LogEntry.objects.filter(volunteer=user)
    season_logs = all_logs.filter(date_logged__year=current_year)
    recent_shifts = all_logs.order_by("-date_logged")[:5]

    # 3. Calculate Core Stats & Emoji Badges
    lifetime_hours = all_logs.aggregate(total=Sum("duration_hours"))["total"] or 0
    season_hours = season_logs.aggregate(total=Sum("duration_hours"))["total"] or 0

    # Count distinct years they have logged hours in
    seasons_volunteered = all_logs.dates("date_logged", "year").count() or 1
    # Generate one 🌱 emoji per season
    season_badges = "🌱" * seasons_volunteered

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

        # NEW: The Pacing Engine
        if user.farm.season_start and user.farm.season_end and remaining_hours > 0:
            today = timezone.now().date()
            season_end = user.farm.season_end
            season_start = user.farm.season_start

            # Only calculate if the season isn't over yet
            if today < season_end:
                # If the season hasn't started yet, use the total season length
                if today < season_start:
                    days_remaining = (season_end - season_start).days
                else:
                    days_remaining = (season_end - today).days

                # Convert days to weeks (using max to prevent dividing by zero in the final days)
                weeks_remaining = max(days_remaining / 7.0, 1.0)
                required_pace = remaining_hours / weeks_remaining

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
                    marker_colors=["#10b981", "#f59e0b", "#ef4444", "#94a3b8"],
                )
            ]
        )
        fig_a.update_layout(
            margin=dict(t=0, b=0, l=0, r=0), height=250, showlegend=False
        )
        fig_a.update_traces(textposition="inside", textinfo="percent+label")
        activity_chart_html = fig_a.to_html(full_html=False, include_plotlyjs=False)

    context = {
        "form": form,
        "current_year": current_year,
        "lifetime_hours": round(lifetime_hours, 1),
        "season_hours": round(season_hours, 1),
        "seasons_volunteered": seasons_volunteered,
        "season_badges": season_badges,
        "target_hours": target_hours,
        "tier_name": tier_name,
        "progress_pct": progress_pct,
        "remaining_hours": round(remaining_hours, 1),
        "required_pace": round(required_pace, 1),
        "top_veggie": top_veggie,
        "top_act": top_act,
        "veggie_chart": veggie_chart_html,
        "activity_chart": activity_chart_html,
        "recent_shifts": recent_shifts,
    }
    return render(request, "logs/log_hours.html", context)
