import base64
import uuid
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import ProfileUpdateForm


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