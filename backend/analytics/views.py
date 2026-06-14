from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
import plotly.graph_objects as go
import pandas as pd
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser, Farm
import csv
from logs.models import LogEntry


@login_required
def get_impact_chart(request):
    farm = request.active_farm
    year = request.GET.get("year", "all")

    # --- PART 1: THE GLOBAL PROGRESS BAR DATA ---
    global_logs = LogEntry.objects.filter(farm=farm)
    if year and year != "all":
        try:
            global_logs = global_logs.filter(date_logged__year=int(year))
        except ValueError:
            pass

    global_totals = global_logs.values("activity").annotate(total=Sum("duration_hours"))

    total_hours = 0
    p_hours = t_hours = h_hours = o_hours = 0

    for item in global_totals:
        hours = float(item["total"] or 0)
        total_hours += hours
        if item["activity"] == "P":
            p_hours = hours
        elif item["activity"] == "T":
            t_hours = hours
        elif item["activity"] == "H":
            h_hours = hours
        elif item["activity"] == "O":
            o_hours = hours

    # Calculate percentages for the CSS widths
    p_pct = (p_hours / total_hours * 100) if total_hours > 0 else 0
    t_pct = (t_hours / total_hours * 100) if total_hours > 0 else 0
    h_pct = (h_hours / total_hours * 100) if total_hours > 0 else 0
    o_pct = (o_hours / total_hours * 100) if total_hours > 0 else 0

    # Build the Fancy Tailwind KPI Dashboard
    stats_html = f"""
    <div class="mb-8 p-6 md:p-8 bg-white rounded-2xl border border-gray-200
                shadow-sm flex flex-col items-center text-center">

        <h3 class="text-sm font-bold text-gray-400 uppercase tracking-widest mb-2">Total Farm Labor</h3>
        <p class="text-5xl md:text-6xl font-black text-gray-900 mb-8 tracking-tight">
            {int(round(total_hours)):,} <span class="text-2xl text-gray-400 font-bold tracking-normal">Hours</span>
        </p>

        <div class="w-full max-w-4xl flex h-4 overflow-hidden rounded-full bg-gray-100 mb-8 shadow-inner">
            <div style="width: {p_pct}%" class="bg-emerald-500 transition-all duration-500" title="Planting"></div>
            <div style="width: {t_pct}%" class="bg-amber-500 transition-all duration-500" title="Tending"></div>
            <div style="width: {h_pct}%" class="bg-red-500 transition-all duration-500" title="Harvesting"></div>
            <div style="width: {o_pct}%" class="bg-slate-400 transition-all duration-500"
                 title="Off-Season / Other"></div>
        </div>

        <div class="w-full max-w-4xl grid grid-cols-2 md:grid-cols-4 gap-4">

            <div class="flex flex-col items-center justify-center p-4 rounded-xl
                        bg-emerald-50 border border-emerald-100">
                <span class="text-3xl font-extrabold text-emerald-600 mb-1">{int(round(p_hours)):,}</span>
                <span class="text-xs font-bold text-emerald-800 uppercase tracking-wide">Planting</span>
            </div>

            <div class="flex flex-col items-center justify-center p-4 rounded-xl
                        bg-amber-50 border border-amber-100">
                <span class="text-3xl font-extrabold text-amber-600 mb-1">{int(round(t_hours)):,}</span>
                <span class="text-xs font-bold text-amber-800 uppercase tracking-wide">Tending</span>
            </div>

            <div class="flex flex-col items-center justify-center p-4 rounded-xl
                        bg-red-50 border border-red-100">
                <span class="text-3xl font-extrabold text-red-600 mb-1">{int(round(h_hours)):,}</span>
                <span class="text-xs font-bold text-red-800 uppercase tracking-wide">Harvesting</span>
            </div>

            <div class="flex flex-col items-center justify-center p-4 rounded-xl
                        bg-slate-50 border border-slate-200">
                <span class="text-3xl font-extrabold text-slate-600 mb-1">{int(round(o_hours)):,}</span>
                <span class="text-xs font-bold text-slate-800 uppercase tracking-wide">Other Maint.</span>
            </div>

        </div>
    </div>
    """

    # --- PART 2: THE CROP BAR CHART DATA ---
    # Exclude null crops and generic placeholders so non-veggie activities
    # (like Move Dirt) don't skew the visual graph.
    aggregated_data = list(
        global_logs.exclude(crop__isnull=True)
        .exclude(crop__crop_name__iexact="General / Deleted")
        .values("crop__crop_name", "activity")
        .annotate(total_hours=Sum("duration_hours"))
    )

    if not aggregated_data and total_hours == 0:
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

    crops = sorted(list(set([item["crop__crop_name"] for item in aggregated_data])))
    activity_colors = {
        "P": "#10b981",
        "T": "#f59e0b",
        "H": "#ef4444",
        "C": "#8b5cf6",
        "O": "#94a3b8",
        "M": "#78350f",
    }
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
        margin=dict(l=50, r=50, t=20, b=80),
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="white", font_size=15, font_color="black"),
    )

    plotly_html = fig.to_html(full_html=False, include_plotlyjs=False)
    combined_html = stats_html + plotly_html

    return render(request, "analytics/partials/chart.html", {"chart": combined_html})


@login_required
def get_activity_heatmap(request):
    farm = request.active_farm
    year = request.GET.get("year", "all")

    # 1. FETCH DATA
    logs = LogEntry.objects.filter(farm=farm)
    if year != "all":
        logs = logs.filter(date_logged__year=int(year))

    data = list(logs.values("date_logged", "crop", "activity"))

    if not data:
        empty_html = (
            '<div class="flex flex-col items-center justify-center py-20 text-gray-400">'
            '<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
            'd="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 '
            "01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 "
            '01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>'
            '<p class="text-xl font-medium">No activity data found for this timeframe.</p>'
            "</div>"
        )
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    # Secure dictionary mapping
    from farms.models import Crop

    crop_dict = {
        c.id: (c.crop_name, c.category) for c in Crop.objects.filter(farm=farm)
    }
    for item in data:
        crop_id = item.pop("crop", None)
        if crop_id and crop_id in crop_dict:
            item["crop_name"], item["crop_category"] = crop_dict[crop_id]
        else:
            item["crop_name"] = "General / Deleted"
            item["crop_category"] = None

    df = pd.DataFrame(data)

    # 2. CLEAN AND PREPARE DATA
    df["WeekOfYear"] = (
        pd.to_datetime(df["date_logged"]).dt.isocalendar().week.astype(int)
    )
    df["Display_Veggie"] = (
        df["crop_category"]
        .replace("", pd.NA)
        .fillna(df["crop_name"])
        .fillna("General / Deleted")
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
            colorscale=discrete_colorscale,
            zmin=-0.5,
            zmax=3.5,
            # xgap=2, <-- DELETE THIS LINE
            # ygap=2, <-- DELETE THIS LINE
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
    farm = request.active_farm
    year = request.GET.get("year", "all")

    # 1. FETCH DATA
    # THE FIX: Allow null crops to pass through
    logs = LogEntry.objects.filter(farm=farm)
    if year != "all":
        logs = logs.filter(date_logged__year=int(year))

    data = list(logs.values("date_logged", "crop", "activity"))

    if not data:
        empty_html = """
        <div class="flex flex-col items-center justify-center py-20 text-gray-400">
            <p class="text-xl font-medium">No term occurrence data found for this timeframe.</p>
        </div>
        """
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    from farms.models import Crop

    crop_dict = {c.id: c.crop_name for c in Crop.objects.filter(farm=farm)}
    for item in data:
        crop_id = item.pop("crop", None)
        item["crop_name"] = (
            crop_dict.get(crop_id, "General / Deleted")
            if crop_id
            else "General / Deleted"
        )

    df = pd.DataFrame(data)

    # 2. PREPARE DATA
    df["WeekOfYear"] = (
        pd.to_datetime(df["date_logged"]).dt.isocalendar().week.astype(int)
    )
    activity_names = dict(LogEntry.ACTIVITY_CHOICES)
    df["Activity_Label"] = df["activity"].map(activity_names)

    # 3. SPLIT AND STACK
    df_veggies = df[["WeekOfYear", "crop_name"]].rename(columns={"crop_name": "Term"})
    df_activities = df[["WeekOfYear", "Activity_Label"]].rename(
        columns={"Activity_Label": "Term"}
    )
    df_terms = pd.concat([df_veggies, df_activities]).dropna(subset=["Term"])

    # 4. AGGREGATE
    agg_df = (
        df_terms.groupby(["Term", "WeekOfYear"]).size().reset_index(name="Occurrences")
    )

    all_unique_terms = agg_df["Term"].unique().tolist()
    activity_list = sorted(
        [name for code, name in activity_names.items() if name in all_unique_terms]
    )
    veggie_list = sorted([t for t in all_unique_terms if t not in activity_list])
    ordered_terms = activity_list + veggie_list

    weeks = list(range(1, 53))

    pivot_z = (
        agg_df.pivot(index="Term", columns="WeekOfYear", values="Occurrences")
        .reindex(index=ordered_terms, columns=weeks)
        .fillna(0)
    )

    z_matrix = pivot_z.values.tolist()

    # 5. BUILD THE PLOTLY FIGURE
    fig = go.Figure()

    # Main Heatmap Trace
    fig.add_trace(
        go.Heatmap(
            z=z_matrix,
            x=weeks,
            y=ordered_terms,
            colorscale="YlGnBu",
            hovertemplate="<b>Week:</b> %{x}<br><b>Term:</b> %{y}<br><b>Occurrences:</b> %{z} logs<extra></extra>",
            showscale=True,
            colorbar=dict(
                title="Occurrences",
                thickness=15,
                orientation="h",  # THE FIX: Lay it flat
                x=0.5,  # Center it horizontally
                y=-0.25,  # Push it down below the x-axis labels
            ),
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
        # THE FIX: Increased the bottom margin (b=120) to make room for the horizontal colorbar
        margin=dict(l=150, r=150, t=20, b=120),
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


@login_required
def get_seasonal_timeline(request):
    farm = request.active_farm
    year = request.GET.get("year", "all")

    # 1. FETCH DATA
    # THE FIX: Allow null crops to pass through
    logs = LogEntry.objects.filter(farm=farm)
    if year != "all":
        logs = logs.filter(date_logged__year=int(year))

    data = list(logs.values("date_logged", "crop", "activity"))

    if not data:
        empty_html = (
            '<div class="flex flex-col items-center justify-center py-20 text-gray-400">'
            '<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
            'd="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 '
            "01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 "
            '01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>'
            '<p class="text-xl font-medium">No timeline data available for this timeframe.</p>'
            "</div>"
        )
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    from farms.models import Crop

    crop_dict = {c.id: c.crop_name for c in Crop.objects.filter(farm=farm)}
    for item in data:
        crop_id = item.pop("crop", None)
        item["crop_name"] = (
            crop_dict.get(crop_id, "General / Deleted")
            if crop_id
            else "General / Deleted"
        )

    df = pd.DataFrame(data)

    # 2. CALCULATE START AND END WEEKS
    df["WeekOfYear"] = (
        pd.to_datetime(df["date_logged"]).dt.isocalendar().week.astype(int)
    )
    activity_names = dict(LogEntry.ACTIVITY_CHOICES)

    # Group by crop and activity to find the absolute min and max week
    agg_df = (
        df.groupby(["crop_name", "activity"])
        .agg(StartWeek=("WeekOfYear", "min"), EndWeek=("WeekOfYear", "max"))
        .reset_index()
    )

    # To draw a Plotly bar from Start to End, the X value must be the duration
    agg_df["Duration"] = agg_df["EndWeek"] - agg_df["StartWeek"] + 1

    # Sort crops alphabetically for the Y-axis
    unique_crops = sorted(agg_df["crop_name"].unique().tolist(), reverse=True)

    # 3. BUILD THE PLOTLY GANTT CHART
    fig = go.Figure()
    activity_colors = {"P": "#10b981", "T": "#f59e0b", "H": "#ef4444", "O": "#94a3b8"}

    for act_code, act_label in activity_names.items():
        act_data = agg_df[agg_df["activity"] == act_code]
        if not act_data.empty:
            fig.add_trace(
                go.Bar(
                    name=act_label,
                    x=act_data["Duration"],
                    y=act_data["crop_name"],
                    base=act_data[
                        "StartWeek"
                    ],  # This is the magic trick! Pushes the bar to the Start Week
                    orientation="h",
                    marker_color=activity_colors.get(act_code, "#94a3b8"),
                    hovertemplate="<b>%{y}</b><br>"
                    + act_label
                    + "<br>Start Week: %{base}<br>End Week: %{customdata}<extra></extra>",
                    customdata=act_data["EndWeek"],
                )
            )

    # 4. USER-FRIENDLY AXES
    xaxis_config = dict(
        title="Week of Year",
        tickmode="linear",
        dtick=4,
        range=[0, 53],  # Lock the view to 52 weeks
        showgrid=True,
        gridcolor="rgba(200,200,200,0.3)",
    )
    if year != "all":
        xaxis_config.update(
            dict(
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
            )
        )

    fig.update_layout(
        barmode="group",  # If activities overlap weeks, this stacks them neatly side-by-side!
        plot_bgcolor="rgba(250,250,250,1)",
        paper_bgcolor="white",
        margin=dict(l=150, r=50, t=20, b=80),
        height=max(400, len(unique_crops) * 60 + 150),
        xaxis=xaxis_config,
        yaxis=dict(
            title="",
            tickfont=dict(size=13),
            automargin=True,
            categoryorder="array",
            categoryarray=unique_crops,
        ),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="white", font_size=13, font_color="black"),
    )

    chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
    return render(request, "analytics/partials/chart.html", {"chart": chart_html})


@login_required
def get_volunteer_heatmap(request):
    farm = request.active_farm
    year = request.GET.get("year", "all")

    # 1. FETCH DATA
    logs = LogEntry.objects.filter(farm=farm).select_related("volunteer")
    if year != "all":
        try:
            logs = logs.filter(date_logged__year=int(year))
        except ValueError:
            pass

    data = list(
        logs.values(
            "date_logged",
            "volunteer__first_name",
            "volunteer__last_name",
            "volunteer__username",
            "duration_hours",
        )
    )

    if not data:
        empty_html = """
        <div class="flex flex-col items-center justify-center py-20 text-gray-400">
            <p class="text-xl font-medium">No volunteer activity found for this timeframe.</p>
        </div>
        """
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    df = pd.DataFrame(data)

    # 2. PREPARE DATA
    df["WeekOfYear"] = (
        pd.to_datetime(df["date_logged"]).dt.isocalendar().week.astype(int)
    )
    df["duration_hours"] = df["duration_hours"].astype(float)

    # Create a clean display name for the Y-Axis
    def make_name(row):
        first = row.get("volunteer__first_name") or ""
        last = row.get("volunteer__last_name") or ""
        full_name = f"{first} {last}".strip()
        return full_name if full_name else row.get("volunteer__username", "Unknown")

    df["Volunteer"] = df.apply(make_name, axis=1)

    # 3. AGGREGATE HOURS PER WEEK
    agg_df = (
        df.groupby(["Volunteer", "WeekOfYear"])["duration_hours"].sum().reset_index()
    )

    # Sort volunteers alphabetically (reverse so A is at the top of the Plotly Y-axis)
    volunteers = sorted(agg_df["Volunteer"].unique().tolist(), reverse=True)
    weeks = list(range(1, 53))

    pivot_z = (
        agg_df.pivot(index="Volunteer", columns="WeekOfYear", values="duration_hours")
        .reindex(index=volunteers, columns=weeks)
        .fillna(0)
    )

    z_matrix = pivot_z.values.tolist()

    # 4. BUILD THE PLOTLY FIGURE
    fig = go.Figure()

    # Create a custom colorscale where exactly 0 is white, and >0 starts the rainbow
    custom_rainbow = [
        [0.0, "#ffffff"],  # 0 hours = Pure White
        [0.001, "#ffffff"],  # Sharp cutoff just below the 0.25hr minimum log
        [0.001, "#8b5cf6"],  # Start the rainbow (Purple) immediately after 0
        [0.2, "#3b82f6"],  # Blue
        [0.4, "#10b981"],  # Green
        [0.6, "#f59e0b"],  # Yellow
        [0.8, "#ea580c"],  # Orange
        [1.0, "#ef4444"],  # Red
    ]

    # Main Heatmap Trace
    fig.add_trace(
        go.Heatmap(
            z=z_matrix,
            x=weeks,
            y=volunteers,
            colorscale=custom_rainbow,
            zmin=0,
            zmax=40,
            hovertemplate=(
                "<b>Week:</b> %{x}<br><b>Volunteer:</b> %{y}<br><b>Hours Logged:</b> %{z} hrs<extra></extra>"
            ),
            showscale=True,
            colorbar=dict(
                title="Total Hours",
                thickness=15,
                orientation="h",
                x=0.5,
                y=-0.25,
            ),
        )
    )

    # The Ghost Trace (Mirrors labels to the right side of the screen)
    fig.add_trace(
        go.Heatmap(
            z=[[None] * len(weeks)] * len(volunteers),
            x=weeks,
            y=volunteers,
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

    fig.update_layout(
        plot_bgcolor="white",  # Pure white background to make the rainbow pop
        paper_bgcolor="white",
        margin=dict(l=150, r=150, t=20, b=120),
        height=max(400, len(volunteers) * 25 + 150),
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
def get_adoption_report(request):
    if not request.user.is_staff:
        return HttpResponse(status=403)

    farms = Farm.objects.all()
    one_week_ago = timezone.now() - timedelta(days=7)
    report_html = '<div class="space-y-6">'

    for farm in farms:
        # 1. Volunteer Participation %
        # Math: (Volunteers with logs in 7 days / Total active volunteers) * 100
        all_volunteers = CustomUser.objects.filter(
            memberships__farm=farm, is_active=True
        ).exclude(role__in=["account_manager", "farm_manager"])
        active_volunteers = all_volunteers.filter(
            logs__date_logged__gte=one_week_ago.date()
        ).distinct()

        total_vol_count = all_volunteers.count()
        active_vol_count = active_volunteers.count()

        participation_pct = (
            (active_vol_count / total_vol_count * 100) if total_vol_count > 0 else 0
        )

        # 2. Manager Engagement (Last Login)
        manager = CustomUser.objects.filter(
            memberships__farm=farm, role="farm_manager"
        ).first()
        last_seen = manager.last_login if manager and manager.last_login else None
        is_engaged = last_seen and last_seen >= one_week_ago

        # Build the HTML snippet
        report_html += f"""
        <div class="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-bold text-gray-900">{farm.name}</h3>
                <span class="text-xs font-bold uppercase tracking-widest {"text-emerald-600" if is_engaged else "text-gray-400"}">
                    {"Manager Active" if is_engaged else "Manager Inactive"}
                </span>
            </div>
            <div class="space-y-2">
                <div class="flex justify-between text-sm text-gray-600 font-bold">
                    <span>Volunteer Participation</span>
                    <span>{int(participation_pct)}%</span>
                </div>
                <div class="w-full bg-gray-100 h-4 rounded-full overflow-hidden">
                    <div style="width: {participation_pct}%" class="h-4 bg-emerald-500"></div>
                </div>
                <p class="text-xs text-gray-400">
                    {active_vol_count} / {total_vol_count} volunteers active this week
                </p>
            </div>
        </div>
        """

    report_html += "</div>"
    return render(request, "analytics/partials/chart.html", {"chart": report_html})


@login_required
def admin_adoption_dashboard(request):
    if not request.user.is_staff:
        raise PermissionDenied("You are not authorized to view this page.")
    return render(request, "analytics/admin_dashboard.html")


@login_required
def export_grant_report_csv(request):
    farm = request.active_farm

    # 1. THE ENTERPRISE TOLLBOOTH
    # Only Institutional/Enterprise tier (or comped/staff) can download raw data
    if (
        farm.subscription_tier != "institutional"
        and not farm.is_comped
        and not request.user.is_staff
    ):
        messages.error(request, "Data Export is only available on the Enterprise tier.")
        return redirect("manager_dashboard")

    # 2. Setup the HTTP Response to trigger a file download
    response = HttpResponse(
        content_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{farm.name}_Grant_Report.csv"'
        },
    )

    writer = csv.writer(response)

    # 3. Write the Header Row
    writer.writerow(
        [
            "Date Logged",
            "Volunteer Name",
            "Email",
            "Activity Type",
            "Crop/Category",
            "Hours Logged",
            "Field Notes",
        ]
    )

    # 4. Fetch and Write the Data
    # Optimize the query with select_related so we don't hit the DB 10,000 times
    logs = (
        LogEntry.objects.filter(farm=farm)
        .select_related("volunteer", "crop")
        .order_by("-date_logged")
    )

    for log in logs:
        vol_name = (
            f"{log.volunteer.first_name} {log.volunteer.last_name}".strip()
            if log.volunteer
            else "Deleted User"
        )
        vol_email = log.volunteer.email if log.volunteer else "N/A"
        crop_name = log.crop.crop_name if log.crop else "General/Deleted"

        writer.writerow(
            [
                log.date_logged,
                vol_name,
                vol_email,
                log.get_activity_display(),
                crop_name,
                log.duration_hours,
                log.notes or "",
            ]
        )

    return response
