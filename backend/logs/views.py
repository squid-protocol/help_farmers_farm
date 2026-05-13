from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import LogEntryForm 
from .models import LogEntry

@login_required
def log_hours_view(request):
    if request.method == "POST":
        # THE FIX: Pass the user into the POST form
        form = LogEntryForm(request.POST, user=request.user) 
        if form.is_valid():
            log = form.save(commit=False)
            log.volunteer = request.user
            if request.user.farm:
                log.farm = request.user.farm
            log.save()

            if request.headers.get('HX-Request'):
                response = render(request, "logs/partials/shift_row.html", {"log": log})
                response['HX-Trigger'] = 'showToast'
                return response

            return redirect("log_hours")
    else:
        # THE FIX: Pass the user into the empty GET form
        form = LogEntryForm(user=request.user) 

    recent_logs = LogEntry.objects.filter(volunteer=request.user).order_by('-date_logged')[:5]
    return render(request, "logs/log_hours.html", {"form": form, "recent_logs": recent_logs})