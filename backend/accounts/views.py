import base64
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ProfileUpdateForm


# --- 1. THE STANDARD PROFILE VIEW ---
@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect("profile")
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form})


# --- 2. THE NEW AVATAR CROPPER VIEW ---
@login_required
def upload_avatar(request):
    if request.method == "POST":
        image_data = request.POST.get("avatar_base64")

        if image_data:
            # 1. Split the base64 string and decode it
            format, imgstr = image_data.split(";base64,")
            ext = format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr))

            # 2. THE FIX: Call save() directly on the avatar field itself!
            file_name = f"{request.user.username}_avatar.{ext}"
            request.user.avatar.save(file_name, data, save=True)

            # 3. Fire off a success message
            messages.success(request, "Your new avatar looks great!")

    # Bounce them right back to the profile page
    return redirect("profile")
