from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .forms import LogEntryForm
from .models import LogEntry


@login_required
def log_hours_view(request):
    if request.method == "POST":
        form = LogEntryForm(request.POST, user=request.user)
        if form.is_valid():
            log_entry = form.save(commit=False)
            log_entry.volunteer = request.user
            log_entry.farm = request.user.farm
            log_entry.save()
            return redirect("log_hours")
    else:
        form = LogEntryForm(user=request.user)

    # --- THE REWARD ENGINE ---
    # 1. Fetch all logs belonging to the currently logged-in volunteer
    user_logs = LogEntry.objects.filter(volunteer=request.user)

    # 2. Add up all their hours using 'duration_hours'
    total_hours = user_logs.aggregate(Sum("duration_hours"))["duration_hours__sum"] or 0.0

    # 3. Grab their 5 most recent shifts sorted by 'date_logged'
    recent_logs = user_logs.order_by("-date_logged")[:5]

    context = {
        "form": form,
        "total_hours": round(total_hours, 1),
        "recent_logs": recent_logs,
    }

    return render(request, "logs/log_hours.html", context)
