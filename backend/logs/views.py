from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import LogEntryForm

@login_required
def log_hours_view(request):
    if request.method == 'POST':
        # If the user clicked Submit, load their data into the form
        form = LogEntryForm(request.POST, user=request.user)
        
        if form.is_valid():
            # Save the form, but don't commit to the database quite yet
            log_entry = form.save(commit=False)
            
            # Attach the logged-in volunteer and their farm
            log_entry.volunteer = request.user
            log_entry.farm = request.user.farm
            
            # Lock it into the database
            log_entry.save()
            
            # Refresh the page so they can log another chore
            return redirect('log_hours') 
    else:
        # If they just navigated to the page, give them a blank form
        form = LogEntryForm(user=request.user)

    # Render the HTML template
    return render(request, 'logs/log_hours.html', {'form': form})