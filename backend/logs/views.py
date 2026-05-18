from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from datetime import datetime
from django.utils import timezone
import plotly.graph_objects as go

from .models import LogEntry
from .forms import LogEntryForm

from decimal import Decimal


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

            # Wrap the database hit in a try/except for stability
            try:
                new_log.save()
                messages.success(request, "Shift logged successfully!")
                return redirect("log_hours")
            except Exception as e:
                # Log the real error to Sentry/Console in the background, but show a clean message
                import logging

                logging.getLogger("django").error(f"Database error logging shift: {e}")
                messages.error(
                    request,
                    "There was a network issue saving your shift. Please try again.",
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

    # 3. Calculate Core Stats & Emoji Badges
    lifetime_hours = all_logs.aggregate(total=Sum("duration_hours"))["total"] or 0
    season_hours = season_logs.aggregate(total=Sum("duration_hours"))["total"] or 0

    # Count distinct years they have logged hours in the database
    active_seasons = all_logs.dates("date_logged", "year").count()

    # Calculate Total Seasons = Legacy Offset + Active Database Seasons
    total_seasons = max(user.legacy_years_volunteered + active_seasons, 1)

    # Generate the Star Badges with Overflow Protection
    if total_seasons <= 5:
        season_badges = "⭐" * total_seasons
    else:
        season_badges = f"{total_seasons}x ⭐"

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
        if user.farm.season_start and user.farm.season_end and remaining_hours > 0:
            today = timezone.now().date()
            season_end = user.farm.season_end
            season_start = user.farm.season_start

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
    lifetime_crop_chart_html = None  # <-- NEW: Lifetime Mastery Chart

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
                farm=user.farm, date_logged__year=current_year, crop__is_active=True
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
            Crop.objects.filter(farm=user.farm, is_active=True)
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

    # --- NEW: Lifetime Crop Mastery Chart ---
    if lifetime_hours > 0:
        lifetime_crop_data = (
            all_logs.exclude(crop__isnull=True)
            .values("crop__crop_name")
            .annotate(total=Sum("duration_hours"))
            .order_by(
                "total"
            )  # Ascending so Plotly puts the largest at the top of the Y-axis
        )

        if lifetime_crop_data:
            lt_crop_names = [item["crop__crop_name"] for item in lifetime_crop_data]
            lt_hours_list = [float(item["total"] or 0) for item in lifetime_crop_data]

            fig_lt = go.Figure(
                data=[
                    go.Bar(
                        name="Lifetime Hours",
                        y=lt_crop_names,
                        x=lt_hours_list,
                        orientation="h",
                        marker_color="#10b981",  # Emerald green leveling up bar
                        hovertemplate="<b>%{y}</b><br>Lifetime Hours: %{x} hrs<extra></extra>",
                    )
                ]
            )
            fig_lt.update_layout(
                plot_bgcolor="rgba(250,250,250,1)",
                paper_bgcolor="white",
                margin=dict(t=30, b=30, l=10, r=20),
                height=max(300, len(lt_crop_names) * 35 + 100),
                showlegend=False,
                hoverlabel=dict(bgcolor="white", font_size=13, font_color="black"),
                xaxis=dict(
                    title="Lifetime Hours",
                    showgrid=True,
                    gridcolor="rgba(200,200,200,0.3)",
                ),
                yaxis=dict(title="", tickfont=dict(size=12), automargin=True),
            )
            lifetime_crop_chart_html = fig_lt.to_html(
                full_html=False, include_plotlyjs=False
            )

    context = {
        "form": form,
        "current_year": current_year,
        "lifetime_hours": round(lifetime_hours, 1),
        "season_hours": round(season_hours, 1),
        "seasons_volunteered": total_seasons,
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
        "comparison_chart": comparison_chart_html,
        "lifetime_crop_chart": lifetime_crop_chart_html,  # Added to context
        "history_year": history_year,
        "prev_year": prev_year,
        "next_year": next_year,
        "history_shifts": history_shifts,
    }
    return render(request, "logs/log_hours.html", context)
