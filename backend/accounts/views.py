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
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import logout
from django.views.decorators.http import require_POST
import logging

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

    # 1. HARD BLOCK: Enforce full profile completion before viewing legal docs
    if (
        not request.user.first_name
        or not request.user.last_name
        or not request.user.phone_number
        or not request.user.address
    ):
        messages.warning(
            request,
            (
                "⚠️ Legal Requirement: You must provide your First Name, Last Name, "
                "Phone Number, and Physical Address before signing documents."
            ),
        )
        return redirect("profile")

    # 2. EMAIL VERIFICATION HANDLING
    if request.method == "POST" and "send_verification" in request.POST:
        signer = TimestampSigner()
        token = signer.sign(request.user.id)
        verify_url = request.build_absolute_uri(
            reverse("verify_email_link", args=[token])
        )

        send_mail(
            subject=f"Verify your signature account for {farm.name}",
            message=(
                f"Please click the following link to verify your email address "
                f"and unlock your compliance documents: {verify_url}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
        )
        messages.success(
            request,
            "Verification email sent! Please check your inbox and click the link.",
        )
        return redirect("sign_waiver")

    # 3. Standard Waiver Logic
    valid_forms = ComplianceForm.objects.filter(farm=farm, is_active=True).exclude(
        does_expire=True, expiration_date__lt=today
    )
    signed_form_ids = FormSignature.objects.filter(
        user=request.user, form__in=valid_forms
    ).values_list("form_id", flat=True)

    pending_forms = valid_forms.exclude(id__in=signed_form_ids)

    if not pending_forms.exists():
        return redirect("log_hours")

    form_to_sign = pending_forms.first()
    remaining_count = pending_forms.count()

    if request.method == "POST" and (
        "sign_document" in request.POST or "digital_signature" in request.POST
    ):
        # Security check: don't let them hack the form if they aren't verified
        if not request.user.is_email_verified:
            messages.error(request, "You must verify your email before signing.")
            return redirect("sign_waiver")

        # --- SECURITY FIX 1: IDOR & Cross-Tenant Pollution Prevention ---
        submitted_form_id = request.POST.get("form_id")
        if submitted_form_id and str(form_to_sign.id) != str(submitted_form_id):
            raise PermissionDenied(
                "Security Exception: You cannot sign a document belonging to another farm."
            )

        # --- SECURITY FIX 2: Strict Signature Payload Validation ---
        # Fallback to 'digital_signature' to catch automated DOM bypass attacks
        signature = request.POST.get(
            "digital_signature", request.POST.get("signature", "")
        ).strip()
        expected_name = f"{request.user.first_name} {request.user.last_name}".strip()

        is_guardian = request.POST.get("is_guardian") == "on"
        guardian_relationship = request.POST.get("guardian_relationship", "").strip()

        is_valid = False
        error_message = ""

        # Fail instantly if the signature is blank or just whitespace
        if not signature:
            error_message = "A valid digital signature is legally required."
        elif is_guardian:
            if not guardian_relationship:
                error_message = "Please specify your relationship to the minor (e.g., Parent, Legal Guardian)."
            elif len(signature) < 2:
                error_message = "Please type your full legal name as the guardian."
            else:
                is_valid = True
        else:
            if expected_name and signature.lower() == expected_name.lower():
                is_valid = True
            elif signature.lower() == request.user.username.lower():
                is_valid = True
            else:
                error_message = (
                    "Your signature must match your first and last name exactly."
                )

        if is_valid:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(",")[0]
            else:
                ip_address = request.META.get("REMOTE_ADDR")

            sig_record = FormSignature.objects.create(
                user=request.user,
                form=form_to_sign,
                digital_signature=signature,
                is_guardian_signature=is_guardian,
                guardian_relationship=guardian_relationship if is_guardian else None,
                signer_ip_address=ip_address,
            )

            from django_q.tasks import async_task

            async_task(
                "accounts.tasks.generate_pdf_receipt",
                sig_record.id,
                request.user.id,
                form_to_sign.id,
                farm.id,
                ip_address,
            )

            if remaining_count > 1:
                messages.success(
                    request, f"'{form_to_sign.name}' signed and is being secured."
                )
                return redirect("sign_waiver")
            else:
                messages.success(
                    request, f"All forms signed and secured. Welcome to {farm.name}!"
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


@login_required
def verify_email_link_view(request, token):
    """Decodes the cryptographically signed email link."""
    signer = TimestampSigner()
    try:
        # Token is valid for 48 hours (172800 seconds)
        user_id = signer.unsign(token, max_age=172800)

        # Security check: Ensure they are verifying the account they are logged into
        if int(user_id) == request.user.id:
            request.user.is_email_verified = True
            request.user.save()
            messages.success(
                request,
                "✅ Your email is verified! You may now sign your legal documents.",
            )
        else:
            messages.error(
                request, "That verification link belongs to a different account."
            )

    except (BadSignature, SignatureExpired):
        messages.error(
            request,
            "The verification link was invalid or has expired. Please request a new one.",
        )

    return redirect("sign_waiver")


@login_required
@require_POST
def delete_account_view(request):
    """Triggers the CCPA/GDPR anonymization protocol."""
    user = request.user
    
    # Log the event for the farm's audit trail before destroying the identity
    logger = logging.getLogger("audit")
    logger.info(f"User {user.id} ({user.username}) requested account anonymization.")

    # Fire the protocol
    user.anonymize_and_archive()
    
    # Destroy their active browser session
    logout(request)
    
    messages.success(request, "Your account has been permanently anonymized and deleted.")
    return redirect("home")
