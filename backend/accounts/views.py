import base64
import requests
import uuid
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.db.models import Q, Sum
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
from django.db import transaction
from .forms import VolunteerSignUpForm, FarmSignUpForm
from .models import FarmMembership
from farms.models import Farm
import logging
import plotly.graph_objects as go
from logs.models import LogEntry

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

    # 2. Fetch their signed legal documents
    signatures = (
        FormSignature.objects.filter(user=user)
        .select_related("form")
        .order_by("-signed_at")
    )

    # 3. Generate Trading Card Stats
    all_logs = LogEntry.objects.filter(volunteer=user)
    lifetime_hours = all_logs.aggregate(total=Sum("duration_hours"))["total"] or 0
    total_shifts = all_logs.count()

    active_seasons = all_logs.dates("date_logged", "year").count()
    total_seasons = max(user.legacy_years_volunteered + active_seasons, 1)
    if total_seasons <= 5:
        season_badges = "⭐" * total_seasons
    else:
        season_badges = f"{total_seasons}x ⭐"

    total_farms_helped = all_logs.values("farm").distinct().count()

    top_veggie_data = (
        all_logs.exclude(crop__isnull=True)
        .values("crop__crop_name")
        .annotate(total=Sum("duration_hours"))
        .order_by("-total")
        .first()
    )
    top_veggie = top_veggie_data["crop__crop_name"] if top_veggie_data else "N/A"

    activity_map = dict(LogEntry.ACTIVITY_CHOICES)
    top_act_data = (
        all_logs.values("activity")
        .annotate(total=Sum("duration_hours"))
        .order_by("-total")
        .first()
    )
    top_act = (
        activity_map.get(top_act_data["activity"], "N/A") if top_act_data else "N/A"
    )

    # 4. Lifetime Crop Chart (With Expanded Gamified Zero-State)
    lt_crop_names = []
    lt_hours_list = []
    marker_color = "#10b981"

    if lifetime_hours > 0:
        lifetime_crop_data = (
            all_logs.exclude(crop__isnull=True)
            .values("crop__crop_name")
            .annotate(total=Sum("duration_hours"))
            .order_by("total")
        )

        if lifetime_crop_data:
            lt_crop_names = [item["crop__crop_name"] for item in lifetime_crop_data]
            lt_hours_list = [float(item["total"] or 0) for item in lifetime_crop_data]
    else:
        # Expanded Zero-state placeholder data
        lt_crop_names = [
            "Onions",
            "Lettuce",
            "Carrots",
            "Peppers",
            "Tomatoes",
            "Garlic",
            "Cucumbers",
            "Zucchini",
            "Radishes",
            "Peas",
        ]
        lt_hours_list = [0.0] * 10
        marker_color = "#e2e8f0"

    lifetime_crop_chart_html = None
    if lt_crop_names:
        fig_lt = go.Figure(
            data=[
                go.Bar(
                    name="Lifetime Hours",
                    y=lt_crop_names,
                    x=lt_hours_list,
                    orientation="h",
                    marker_color=marker_color,
                    hovertemplate="<b>%{y}</b><br>Lifetime Hours: %{x} hrs<extra></extra>",
                )
            ]
        )
        fig_lt.update_layout(
            plot_bgcolor="rgba(250,250,250,1)",
            paper_bgcolor="white",
            margin=dict(t=30, b=30, l=10, r=20),
            height=max(300, len(lt_crop_names) * 35 + 100),
            showlegend=False,
            hoverlabel=dict(bgcolor="white", font_size=13, font_color="black"),
            xaxis=dict(
                title="Lifetime Hours" if lifetime_hours > 0 else "0 Hours Logged",
                showgrid=True,
                gridcolor="rgba(200,200,200,0.3)",
            ),
            yaxis=dict(title="", tickfont=dict(size=12), automargin=True),
        )

        if lifetime_hours == 0:
            fig_lt.update_xaxes(range=[0, 10])

        lifetime_crop_chart_html = fig_lt.to_html(
            full_html=False, include_plotlyjs=False
        )

    # 5. Lifetime Activity Chart
    lifetime_activity_chart_html = None

    # Safely initialize fallback variables to prevent UnboundLocalErrors
    act_names = ["No Hours Logged"]
    act_hours = [1]
    marker_colors = ["#e2e8f0"]

    if lifetime_hours > 0:
        activity_data = (
            all_logs.values("activity")
            .annotate(total=Sum("duration_hours"))
            .order_by("-total")
        )

        if activity_data:
            activity_map = dict(LogEntry.ACTIVITY_CHOICES)
            color_map = {
                "P": "#10b981",  # Planting
                "T": "#f59e0b",  # Tending
                "H": "#ef4444",  # Harvesting
                "C": "#8b5cf6",  # Cultivating
                "O": "#94a3b8",  # Off Season
                "M": "#78350f",  # Move Dirt
            }

            act_names = [
                activity_map.get(item["activity"], "Other") for item in activity_data
            ]
            act_hours = [float(item["total"] or 0) for item in activity_data]
            # Map the exact color to the specific activity returned
            marker_colors = [
                color_map.get(item["activity"], "#94a3b8") for item in activity_data
            ]

    fig_act = go.Figure(
        data=[
            go.Pie(
                labels=act_names,
                values=act_hours,
                hole=0.5,
                marker_colors=marker_colors,
                sort=False,
            )
        ]
    )

    fig_act.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        height=350,
        showlegend=True if lifetime_hours > 0 else False,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="white", font_size=14, font_color="black"),
    )

    if lifetime_hours > 0:
        fig_act.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value} hrs (%{percent})<extra></extra>",
        )
    else:
        # Hide the hover tooltip for the empty zero-state ring
        fig_act.update_traces(textinfo="none", hoverinfo="skip")

    lifetime_activity_chart_html = fig_act.to_html(
        full_html=False, include_plotlyjs=False
    )

    context = {
        "form": form,
        "signatures": signatures,
        "lifetime_hours": round(lifetime_hours, 1),
        "total_shifts": total_shifts,
        "seasons_volunteered": total_seasons,
        "season_badges": season_badges,
        "total_farms_helped": total_farms_helped,
        "top_veggie": top_veggie,
        "top_act": top_act,
        "lifetime_crop_chart": lifetime_crop_chart_html,
        "lifetime_activity_chart": lifetime_activity_chart_html,
    }
    return render(request, "accounts/profile.html", context)


@login_required
def upload_avatar(request):
    """Handles the base64 image string sent by Cropper.js and saves it to the user's profile."""
    if request.method == "POST":
        avatar_base64 = request.POST.get("avatar_base64")
        if avatar_base64:
            try:
                # Split the header from the raw data
                format_header, img_str = avatar_base64.split(";base64,")

                # THE FIX: Never trust the client-provided MIME type!
                # Hardcode the extension to jpg to prevent Stored XSS attacks.
                filename = f"avatar_{request.user.id}_{uuid.uuid4().hex[:8]}.jpg"

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
        or not request.user.address_line1
        or not request.user.city
        or not request.user.state
        or not request.user.postal_code
    ):
        messages.warning(
            request,
            (
                "⚠️ Legal Requirement: You must provide your First Name, Last Name, "
                "Phone Number, and a complete Physical Address before signing documents."
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
            # --- THE FIX: Prioritize Cloudflare's verified IP to prevent spoofing ---
            cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")

            if cf_ip:
                ip_address = cf_ip
            else:
                # Fallback for local development when not running through Cloudflare
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

    messages.success(
        request, "Your account has been permanently anonymized and deleted."
    )
    return redirect("home")


def signup_gateway_view(request):
    """Displays the choice between Volunteer or Farm Manager registration."""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "accounts/signup_gateway.html")


def verify_turnstile(request):
    """Helper function to validate the Cloudflare Turnstile token."""
    turnstile_response = request.POST.get("cf-turnstile-response")
    if not turnstile_response:
        return False

    verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    data = {
        "secret": settings.TURNSTILE_SECRET_KEY,
        "response": turnstile_response,
        "remoteip": request.META.get("REMOTE_ADDR"),
    }

    try:
        response = requests.post(verify_url, data=data, timeout=5)
        outcome = response.json()
        return outcome.get("success", False)
    except requests.RequestException:
        # If Cloudflare's API is down or times out, fail secure
        return False


def volunteer_signup_view(request):
    """Registers a new volunteer without an attached farm."""
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        # 0. The Honeypot Trap
        if request.POST.get("website_url"):
            # Bot detected: fake a success message and silently drop the request
            messages.success(request, "Welcome! You can now apply to join a farm.")
            return redirect("home")

        # 1. Cloudflare Turnstile Check
        if not verify_turnstile(request):
            messages.error(
                request,
                "Security check failed. Please ensure JavaScript is enabled and try again.",
            )
            return render(
                request,
                "accounts/signup_volunteer.html",
                {"form": VolunteerSignUpForm(request.POST)},
            )

        # 2. Process the Form
        form = VolunteerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = "volunteer"  # Enforce the role
            user.save()

            login(request, user)
            messages.success(request, "Welcome! You can now apply to join a farm.")
            return redirect("home")  # Redirect to their unattached dashboard
    else:
        form = VolunteerSignUpForm()

    return render(request, "accounts/signup_volunteer.html", {"form": form})


def farm_signup_view(request):
    """Registers a manager, provisions a farm, sets the 60-day trial, and links them."""
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        # 0. The Honeypot Trap
        if request.POST.get("website_url"):
            # Bot detected: fake a success message and silently drop the request
            messages.success(request, "Welcome! Your 60-day free trial starts today.")
            return redirect("home")

        # 1. Cloudflare Turnstile Check
        if not verify_turnstile(request):
            messages.error(
                request,
                "Security check failed. Please ensure JavaScript is enabled and try again.",
            )
            return render(
                request,
                "accounts/signup_farm.html",
                {"form": FarmSignUpForm(request.POST)},
            )

        # 2. Process the Form
        form = FarmSignUpForm(request.POST)
        if form.is_valid():
            try:
                # Wrap all three database creations in an atomic transaction
                with transaction.atomic():
                    # 1. Create the Manager Account
                    user = form.save(commit=False)
                    user.role = "farm_manager"
                    user.is_email_verified = True  # Auto-verify the primary admin
                    user.save()

                    # 2. Provision the Farm Workspace & Start the 60-Day Trial
                    new_farm = Farm.objects.create(
                        name=form.cleaned_data["farm_name"],
                        phone_number=form.cleaned_data["farm_phone"],
                        is_paid=False,  # Trial mode active
                        subscription_tier="trial",
                    )

                    # 3. Create the God-Mode Membership Link
                    FarmMembership.objects.create(
                        user=user,
                        farm=new_farm,
                        is_approved=True,  # Managers are auto-approved for their own farm
                    )

                # If we made it here, the transaction was a complete success
                login(request, user)

                # Set the active session so the middleware knows which dashboard to load
                request.session["active_farm_id"] = new_farm.id

                messages.success(
                    request,
                    f"Welcome to {new_farm.name}! Your 60-day free trial starts today.",
                )
                return redirect("manager_dashboard")

            except Exception:
                messages.error(
                    request,
                    "There was a critical error provisioning your farm. Please try again.",
                )
    else:
        form = FarmSignUpForm()

    return render(request, "accounts/signup_farm.html", {"form": form})
