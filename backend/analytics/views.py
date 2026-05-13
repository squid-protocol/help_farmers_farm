from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
import plotly.graph_objects as go
import pandas as pd
import html

from logs.models import LogEntry


@login_required
def get_impact_chart(request):
    farm = request.user.farm
    logs = LogEntry.objects.filter(farm=farm)

    # 1. CATCH THE HTMX FILTERS
    timeframe = request.GET.get("timeframe", "all")
    crop_id = request.GET.get("crop_id", "all")

    # 2. APPLY THE FILTERS TO THE DATABASE
    if timeframe != "all":
        days_back = int(timeframe)
        cutoff_date = timezone.now().date() - timedelta(days=days_back)
        logs = logs.filter(date_logged__gte=cutoff_date)

    if crop_id != "all":
        logs = logs.filter(crop_id=crop_id)

    # 3. CRUNCH THE NUMBERS
    aggregated_data = (
        logs.values("crop__crop_name", "activity")
        .annotate(total_hours=Sum("duration_hours"))
        .order_by("crop__crop_name")
    )

    # If no data matches the filters, return an empty state
    if not aggregated_data:
        empty_html = (
            '<div class="flex flex-col items-center justify-center py-20 text-gray-400">'
            '<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
            'd="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 '
            "01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 "
            '01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>'
            '<p class="text-xl font-medium">No hours logged for these filters.</p>'
            "</div>"
        )
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    # 4. BUILD THE PLOTLY CHART
    crops = sorted(list(set([item["crop__crop_name"] for item in aggregated_data])))
    activity_colors = {"P": "#10b981", "T": "#f59e0b", "H": "#ef4444", "O": "#94a3b8"}
    activity_labels = dict(LogEntry.ACTIVITY_CHOICES)

    fig = go.Figure()
    for act_code, act_label in activity_labels.items():
        y_values = []
        for crop in crops:
            hours = next(
                (
                    float(item["total_hours"])
                    for item in aggregated_data
                    if item["crop__crop_name"] == crop and item["activity"] == act_code
                ),
                0,
            )
            y_values.append(hours)

        if sum(y_values) > 0:
            fig.add_trace(
                go.Bar(
                    name=act_label,
                    x=crops,
                    y=y_values,
                    marker_color=activity_colors.get(act_code),
                )
            )

    fig.update_layout(
        barmode="stack",
        plot_bgcolor="rgba(250,250,250,1)",
        paper_bgcolor="white",
        margin=dict(
            l=50, r=50, t=40, b=80
        ),  # Reduced top margin since the title is moving to HTML
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="white", font_size=15, font_color="black"),
    )

    chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
    return render(request, "analytics/partials/chart.html", {"chart": chart_html})


@login_required
def get_activity_heatmap(request):
    farm = request.user.farm
    year = request.GET.get("year", "all")

    # 1. FETCH DATA
    logs = LogEntry.objects.filter(farm=farm).exclude(crop__isnull=True)
    if year != "all":
        logs = logs.filter(date_logged__year=int(year))

    data = list(
        logs.values("date_logged", "crop__crop_name", "crop__category", "activity")
    )

    if not data:
        empty_html = """
        <div class="flex flex-col items-center justify-center py-20 text-gray-400">
            <svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>
            <p class="text-xl font-medium">No activity data found for this timeframe.</p>
        </div>
        """
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    df = pd.DataFrame(data)

    # 2. CLEAN AND PREPARE DATA
    df["WeekOfYear"] = (
        pd.to_datetime(df["date_logged"]).dt.isocalendar().week.astype(int)
    )

    # THE FIX: Force empty strings to become proper nulls before filling
    df["Display_Veggie"] = (
        df["crop__category"].replace("", pd.NA).fillna(df["crop__crop_name"])
    )

    activity_priority = {"O": 0, "T": 1, "P": 2, "H": 3}
    activity_names = dict(LogEntry.ACTIVITY_CHOICES)

    df["Activity_Num"] = df["activity"].map(activity_priority)

    # 3. AGGREGATE
    agg_df = (
        df.groupby(["Display_Veggie", "WeekOfYear"])
        .agg(Dominant_Activity=("Activity_Num", "max"))
        .reset_index()
    )

    veggies = sorted(agg_df["Display_Veggie"].unique())
    weeks = list(range(1, 53))

    pivot_z = agg_df.pivot(
        index="Display_Veggie", columns="WeekOfYear", values="Dominant_Activity"
    ).reindex(index=veggies, columns=weeks)

    # THE FIX: Explicitly cast NaNs to None so the JSON parser doesn't swallow them
    z_matrix = pivot_z.where(pd.notnull(pivot_z), None).values.tolist()

    # 4. BUILD THE PLOTLY FIGURE
    fig = go.Figure()

    # THE FIX: Create a sharp "stepped" colorscale so Plotly doesn't blend colors
    discrete_colorscale = [
        [0.00, "#94a3b8"],
        [0.25, "#94a3b8"],  # 0: Off-Season (Slate)
        [0.25, "#f59e0b"],
        [0.50, "#f59e0b"],  # 1: Tending (Amber)
        [0.50, "#10b981"],
        [0.75, "#10b981"],  # 2: Planting (Emerald)
        [0.75, "#ef4444"],
        [1.00, "#ef4444"],  # 3: Harvesting (Red)
    ]

    # Main Heatmap Trace
    fig.add_trace(
        go.Heatmap(
            z=z_matrix,
            x=weeks,
            y=veggies,
            colorscale=discrete_colorscale,  # <-- Use the new stepped colorscale
            zmin=-0.5,
            zmax=3.5,  # <-- Offset min/max so our 0,1,2,3 values sit perfectly in the center of the color blocks
            xgap=2,
            ygap=2,
            hovertemplate="<b>Week:</b> %{x}<br><b>Veggie:</b> %{y}<extra></extra>",
            showscale=True,
            colorbar=dict(
                title="",
                orientation="h",
                x=0.5,
                y=-0.15,
                tickvals=[0, 1, 2, 3],
                ticktext=[
                    activity_names.get("O"),
                    activity_names.get("T"),
                    activity_names.get("P"),
                    activity_names.get("H"),
                ],
                tickfont=dict(size=14),
            ),
        )
    )

    # The Ghost Trace (Mirrors labels to the right side of the screen)
    fig.add_trace(
        go.Heatmap(
            z=[[None] * len(weeks)] * len(veggies),
            x=weeks,
            y=veggies,
            yaxis="y2",
            showscale=False,
            hoverinfo="skip",
        )
    )

    # 5. USER-FRIENDLY AXES
    xaxis_config = dict(
        title="Week of Year",
        tickmode="linear",
        dtick=4,
        showgrid=True,
        gridcolor="rgba(200,200,200,0.3)",
    )
    if year != "all":
        xaxis_config = dict(
            tickmode="array",
            tickvals=[1, 5, 9, 14, 18, 22, 27, 31, 36, 40, 44, 48],
            ticktext=[
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ],
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
        )

    fig.update_layout(
        plot_bgcolor="rgba(250,250,250,1)",
        paper_bgcolor="white",
        margin=dict(l=150, r=150, t=20, b=80),
        height=max(400, len(veggies) * 35 + 150),
        xaxis=xaxis_config,
        yaxis=dict(title="", tickfont=dict(size=13), automargin=True),
        yaxis2=dict(
            overlaying="y",
            side="right",
            matches="y",
            showgrid=False,
            tickfont=dict(size=13),
        ),
        hoverlabel=dict(bgcolor="white", font_size=13, font_color="black"),
    )

    chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
    return render(request, "analytics/partials/chart.html", {"chart": chart_html})


@login_required
def get_term_heatmap(request):
    farm = request.user.farm
    year = request.GET.get("year", "all")

    # 1. FETCH DATA
    logs = LogEntry.objects.filter(farm=farm).exclude(crop__isnull=True)
    if year != "all":
        logs = logs.filter(date_logged__year=int(year))

    data = list(logs.values("date_logged", "crop__crop_name", "activity"))

    if not data:
        empty_html = """
        <div class="flex flex-col items-center justify-center py-20 text-gray-400">
            <p class="text-xl font-medium">No term occurrence data found for this timeframe.</p>
        </div>
        """
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    df = pd.DataFrame(data)

    # 2. PREPARE DATA
    df["WeekOfYear"] = (
        pd.to_datetime(df["date_logged"]).dt.isocalendar().week.astype(int)
    )
    activity_names = dict(LogEntry.ACTIVITY_CHOICES)
    df["Activity_Label"] = df["activity"].map(activity_names)

    # 3. SPLIT AND STACK (The Magic Trick)
    # Count every log entry as an occurrence for its Crop...
    df_veggies = df[["WeekOfYear", "crop__crop_name"]].rename(
        columns={"crop__crop_name": "Term"}
    )
    # ...AND as an occurrence for its Activity
    df_activities = df[["WeekOfYear", "Activity_Label"]].rename(
        columns={"Activity_Label": "Term"}
    )

    # Stack them together
    df_terms = pd.concat([df_veggies, df_activities]).dropna(subset=["Term"])

    # 4. AGGREGATE
    # Count how many times each term appeared in each week
    agg_df = (
        df_terms.groupby(["Term", "WeekOfYear"]).size().reset_index(name="Occurrences")
    )

    # Organize the Y-Axis so Activities are at the top, Veggies at the bottom
    all_unique_terms = agg_df["Term"].unique().tolist()
    activity_list = sorted(
        [name for code, name in activity_names.items() if name in all_unique_terms]
    )
    veggie_list = sorted([t for t in all_unique_terms if t not in activity_list])
    ordered_terms = activity_list + veggie_list

    weeks = list(range(1, 53))

    # Pivot to create the grid (Fill missing weeks with 0)
    pivot_z = agg_df.pivot(
        index="Term", columns="WeekOfYear", values="Occurrences"
    ).reindex(index=ordered_terms, columns=weeks, fill_value=0)

    # Convert to standard Python list for Plotly JSON serialization
    z_matrix = pivot_z.values.tolist()

    # 5. BUILD THE PLOTLY FIGURE
    fig = go.Figure()

    # Main Heatmap Trace
    fig.add_trace(
        go.Heatmap(
            z=z_matrix,
            x=weeks,
            y=ordered_terms,
            colorscale="Teal",
            xgap=1,
            ygap=1,
            hovertemplate="<b>Week:</b> %{x}<br><b>Term:</b> %{y}<br><b>Occurrences:</b> %{z} logs<extra></extra>",
            showscale=True,
            colorbar=dict(title="Occurrences", thickness=15),  # <--- Cleaned up!
        )
    )

    # The Ghost Trace (Mirrors labels to the right side of the screen)
    fig.add_trace(
        go.Heatmap(
            z=[[None] * len(weeks)] * len(ordered_terms),
            x=weeks,
            y=ordered_terms,
            yaxis="y2",
            showscale=False,
            hoverinfo="skip",
        )
    )

    # 6. USER-FRIENDLY AXES
    xaxis_config = dict(
        title="Week of Year",
        tickmode="linear",
        dtick=4,
        showgrid=True,
        gridcolor="rgba(200,200,200,0.3)",
    )
    if year != "all":
        xaxis_config = dict(
            tickmode="array",
            tickvals=[1, 5, 9, 14, 18, 22, 27, 31, 36, 40, 44, 48],
            ticktext=[
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ],
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
        )

    fig.update_layout(
        plot_bgcolor="rgba(250,250,250,1)",
        paper_bgcolor="white",
        margin=dict(l=150, r=150, t=20, b=80),
        height=max(400, len(ordered_terms) * 25 + 150),
        xaxis=xaxis_config,
        yaxis=dict(title="", tickfont=dict(size=13), automargin=True),
        yaxis2=dict(
            overlaying="y",
            side="right",
            matches="y",
            showgrid=False,
            tickfont=dict(size=13),
        ),
        hoverlabel=dict(bgcolor="white", font_size=13, font_color="black"),
    )

    chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
    return render(request, "analytics/partials/chart.html", {"chart": chart_html})
