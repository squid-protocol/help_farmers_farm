import base64
import uuid
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db.models import Q

from .forms import ProfileUpdateForm, AccountClaimForm

# Formally load the CustomUser model
User = get_user_model()


@login_required
def profile_view(request):
    user = request.user

    # 1. Profile Form Logic
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("profile")
    else:
        form = ProfileUpdateForm(instance=user)

    context = {
        "form": form,
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


@login_required
def update_email_view(request):
    if request.method == "POST":
        new_email = request.POST.get("email")

        # Ensure they actually typed something
        if new_email and new_email.strip():
            # Save the new email to their CustomUser profile
            request.user.email = new_email.strip()
            request.user.save()

            # Send them to the main dashboard now that the tollbooth is cleared
            messages.success(request, "Your email has been successfully updated!")
            return redirect("/")
        else:
            messages.error(request, "Please provide a valid email address.")

    return render(request, "accounts/update_email.html")


# --- THE NEW CLAIM VIEWS ---

def claim_account_search(request):
    """Step 1: Search for an unclaimed legacy account."""
    matches = None
    if request.method == "POST":
        search_name = request.POST.get("search_name", "").strip()
        
        if search_name:
            # Only look for users who DO NOT have an email address yet (unclaimed)
            unclaimed_users = User.objects.filter(email="")
            
            # Try to match their search against first name, last name, or the raw username
            matches = unclaimed_users.filter(
                Q(first_name__icontains=search_name) | 
                Q(last_name__icontains=search_name) |
                Q(username__icontains=search_name)
            )
            
            if not matches.exists():
                messages.error(request, "We couldn't find an unclaimed account matching that name. Please try again or contact a manager.")

    return render(request, "accounts/claim_search.html", {"matches": matches})


def claim_account_setup(request, user_id):
    """Step 2: Lock in the email and password."""
    # Ensure they are only claiming an account that lacks an email!
    user_to_claim = get_object_or_404(User, id=user_id, email="")

    if request.method == "POST":
        form = AccountClaimForm(request.POST, instance=user_to_claim)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            
            # Log them in automatically
            login(request, user, backend="accounts.backends.EmailOrUsernameModelBackend")
            messages.success(request, f"Welcome to the system, {user.first_name}! Your account is securely set up.")
            return redirect("log_hours")
    else:
        form = AccountClaimForm(instance=user_to_claim)

    return render(request, "accounts/claim_setup.html", {
        "form": form, 
        "claim_user": user_to_claim
    })