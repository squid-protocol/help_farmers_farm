import base64
import uuid
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from datetime import datetime
import plotly.graph_objects as go

from logs.models import LogEntry
from .forms import ProfileUpdateForm


@login_required
def profile_view(request):
    user = request.user
    current_year = datetime.now().year

    # 1. Profile Form Logic
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("profile")
    else:
        form = ProfileUpdateForm(instance=user)

    # 2. Fetch User's Logs for the Year
    logs = LogEntry.objects.filter(volunteer=user, date_logged__year=current_year)

    # 3. Calculate Commitment Progress
    total_hours = logs.aggregate(total=Sum("duration_hours"))["total"] or 0

    # Safely pull data from the new CommitmentTier relationship
    if user.work_commitment:
        target_hours = user.work_commitment.required_hours
        tier_name = user.work_commitment.name
    else:
        target_hours = 0
        tier_name = "Standard Volunteer"

    progress_pct = 0
    remaining_hours = 0
    if target_hours > 0:
        progress_pct = min((total_hours / target_hours) * 100, 100)  # Cap at 100%
        remaining_hours = max(target_hours - total_hours, 0)

    # 4. Calculate "Fun Stats"
    activity_map = dict(LogEntry.ACTIVITY_CHOICES)

    top_veggie_data = (
        logs.exclude(crop__isnull=True)
        .values("crop__crop_name")
        .annotate(total=Sum("duration_hours"))
        .order_by("-total")
        .first()
    )
    top_veggie = top_veggie_data["crop__crop_name"] if top_veggie_data else "N/A"

    top_act_data = (
        logs.values("activity")
        .annotate(total=Sum("duration_hours"))
        .order_by("-total")
        .first()
    )
    top_act = (
        activity_map.get(top_act_data["activity"], "N/A") if top_act_data else "N/A"
    )

    # 5. Build Personal Breakdowns (Plotly Donut Charts)
    veggie_chart_html = None
    activity_chart_html = None

    if total_hours > 0:
        # Veggie Breakdown Chart
        veggie_breakdown = (
            logs.exclude(crop__isnull=True)
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

        # Activity Breakdown Chart
        act_breakdown = logs.values("activity").annotate(total=Sum("duration_hours"))
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

    # 6. Pass everything to the template
    context = {
        "form": form,
        "current_year": current_year,
        "total_hours": total_hours,
        "target_hours": target_hours,
        "tier_name": tier_name,
        "progress_pct": progress_pct,
        "remaining_hours": remaining_hours,
        "top_veggie": top_veggie,
        "top_act": top_act,
        "veggie_chart": veggie_chart_html,
        "activity_chart": activity_chart_html,
    }
    return render(request, "accounts/profile.html", context)


@login_required
def upload_avatar(request):
    """Handles the base64 image string sent by Cropper.js and saves it to the user's profile."""
    if request.method == "POST":
        avatar_base64 = request.POST.get("avatar_base64")
        if avatar_base64:
            try:
                # The string looks like "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
                # We need to split it to get just the extension and the raw data
                format_header, img_str = avatar_base64.split(";base64,")
                ext = format_header.split("/")[-1]

                # Generate a unique filename so browsers don't cache old avatars
                filename = f"avatar_{request.user.id}_{uuid.uuid4().hex[:8]}.{ext}"

                # Decode the base64 string into actual image bytes
                data = ContentFile(base64.b64decode(img_str), name=filename)

                # Save it to the user object (this will automatically delete the old one if configured)
                request.user.avatar.save(filename, data, save=True)
                messages.success(request, "Avatar updated successfully!")

            except Exception as e:
                messages.error(request, f"There was an error updating your avatar: {e}")
        else:
            messages.error(request, "No image data was received. Please try again.")

    return redirect("profile")
