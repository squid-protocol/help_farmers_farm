import base64
import uuid
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db.models import Q
from django.utils import timezone
from accounts.models import FormSignature
from farms.models import ComplianceForm

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

    # --- NEW: Fetch their signed legal documents ---
    signatures = (
        FormSignature.objects.filter(user=user)
        .select_related("form")
        .order_by("-signed_at")
    )

    context = {
        "form": form,
        "signatures": signatures,
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
                Q(first_name__icontains=search_name)
                | Q(last_name__icontains=search_name)
                | Q(username__icontains=search_name)
            )

            if not matches.exists():
                messages.error(
                    request,
                    "We couldn't find an unclaimed account matching that name. Please try again or contact a manager.",
                )

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
            login(
                request, user, backend="accounts.backends.EmailOrUsernameModelBackend"
            )
            messages.success(
                request,
                f"Welcome to the system, {user.first_name}! Your account is securely set up.",
            )
            return redirect("log_hours")
    else:
        form = AccountClaimForm(instance=user_to_claim)

    return render(
        request,
        "accounts/claim_setup.html",
        {"form": form, "claim_user": user_to_claim},
    )


@login_required
def sign_waiver_view(request):
    farm = request.active_farm
    today = timezone.now().date()

    # Get all active, unexpired forms for the farm
    valid_forms = ComplianceForm.objects.filter(farm=farm, is_active=True).exclude(
        does_expire=True, expiration_date__lt=today
    )

    # Get the IDs of the forms this user has already signed
    signed_form_ids = FormSignature.objects.filter(
        user=request.user, form__in=valid_forms
    ).values_list("form_id", flat=True)

    # Filter down to only the forms they haven't signed yet
    pending_forms = valid_forms.exclude(id__in=signed_form_ids)

    # If they've signed everything, let them into the app!
    if not pending_forms.exists():
        return redirect("log_hours")

    # Grab the first pending form to show them
    form_to_sign = pending_forms.first()
    remaining_count = pending_forms.count()

    if request.method == "POST":
        signature = request.POST.get("signature", "").strip()
        expected_name = f"{request.user.first_name} {request.user.last_name}".strip()

        # --- NEW: Guardian Logic ---
        is_guardian = request.POST.get("is_guardian") == "on"
        guardian_relationship = request.POST.get("guardian_relationship", "").strip()

        is_valid = False
        error_message = ""

        if is_guardian:
            # If a parent is signing, we just ensure they provided a relationship and a name
            if not guardian_relationship:
                error_message = "Please specify your relationship to the minor (e.g., Parent, Legal Guardian)."
            elif len(signature) < 2:
                error_message = "Please type your full legal name as the guardian."
            else:
                is_valid = True
        else:
            # Standard strict name matching for adults
            if (
                signature.lower() == expected_name.lower()
                or signature.lower() == request.user.username.lower()
            ):
                is_valid = True
            else:
                error_message = (
                    "Your signature must match your first and last name exactly."
                )

        if is_valid:
            # Create the immutable ESIGN audit record with the new fields
            FormSignature.objects.create(
                user=request.user,
                form=form_to_sign,
                digital_signature=signature,
                is_guardian_signature=is_guardian,
                guardian_relationship=guardian_relationship if is_guardian else None,
            )

            if remaining_count > 1:
                messages.success(
                    request,
                    f"'{form_to_sign.name}' signed successfully. Please sign the next document.",
                )
                return redirect("sign_waiver")
            else:
                messages.success(
                    request,
                    f"All required compliance forms signed. Welcome to {farm.name}!",
                )
                return redirect("log_hours")
        else:
            messages.error(request, error_message)

    context = {
        "farm": farm,
        "compliance_form": form_to_sign,
        "remaining_count": remaining_count,
    }
    return render(request, "accounts/sign_waiver.html", context)
