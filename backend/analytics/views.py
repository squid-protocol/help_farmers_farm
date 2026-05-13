from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
import plotly.graph_objects as go

from logs.models import LogEntry

@login_required
def get_impact_chart(request):
    farm = request.user.farm
    logs = LogEntry.objects.filter(farm=farm)

    # 1. CATCH THE HTMX FILTERS
    timeframe = request.GET.get('timeframe', 'all')
    crop_id = request.GET.get('crop_id', 'all')

    # 2. APPLY THE FILTERS TO THE DATABASE
    if timeframe != 'all':
        days_back = int(timeframe)
        cutoff_date = timezone.now().date() - timedelta(days=days_back)
        logs = logs.filter(date_logged__gte=cutoff_date)

    if crop_id != 'all':
        logs = logs.filter(crop_id=crop_id)

    # 3. CRUNCH THE NUMBERS
    aggregated_data = (
        logs.values("crop__crop_name", "activity")
        .annotate(total_hours=Sum("duration_hours"))
        .order_by("crop__crop_name")
    )

    # If no data matches the filters, return an empty state
    if not aggregated_data:
        empty_html = """
        <div class="flex flex-col items-center justify-center py-20 text-gray-400">
            <svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>
            <p class="text-xl font-medium">No hours logged for these filters.</p>
        </div>
        """
        return render(request, "analytics/partials/chart.html", {"chart": empty_html})

    # 4. BUILD THE PLOTLY CHART
    crops = sorted(list(set([item["crop__crop_name"] for item in aggregated_data])))
    activity_colors = {"P": "#10b981", "T": "#f59e0b", "H": "#ef4444", "O": "#94a3b8"}
    activity_labels = dict(LogEntry.ACTIVITY_CHOICES)

    fig = go.Figure()
    for act_code, act_label in activity_labels.items():
        y_values = []
        for crop in crops:
            hours = next((float(item["total_hours"]) for item in aggregated_data if item["crop__crop_name"] == crop and item["activity"] == act_code), 0)
            y_values.append(hours)

        if sum(y_values) > 0:
            fig.add_trace(go.Bar(name=act_label, x=crops, y=y_values, marker_color=activity_colors.get(act_code)))

    fig.update_layout(
        barmode="stack",
        plot_bgcolor="rgba(250,250,250,1)",
        paper_bgcolor="white",
        margin=dict(l=50, r=50, t=40, b=80), # Reduced top margin since the title is moving to HTML
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="white", font_size=15, font_color="black"),
    )

    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    return render(request, "analytics/partials/chart.html", {"chart": chart_html})