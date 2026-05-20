from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from accounts.models import FormSignature
from farms.models import ComplianceForm


class RequireEmailMiddleware:
    """
    Intercepts logged-in users who do not have an email address
    and forces them to the email update page before they can access the app.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # --- NEW: Let static CSS and images pass through freely ---
        if request.path.startswith(settings.STATIC_URL) or request.path.startswith(
            settings.MEDIA_URL
        ):
            return self.get_response(request)

        # Only bother checking if the user is actually logged in
        if request.user.is_authenticated and not request.user.email:

            # We must explicitly allow them to view the update page and the logout page.
            # If we don't, they will get stuck in an infinite redirect loop!
            allowed_paths = [
                reverse("update_email"),
                reverse("logout"),
            ]

            if request.path not in allowed_paths:
                return redirect("update_email")

        response = self.get_response(request)
        return response


class RequireWaiverMiddleware:
    """
    Intercepts users who have not signed all active compliance forms
    for their active farm and forces them to the signature page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(settings.STATIC_URL) or request.path.startswith(
            settings.MEDIA_URL
        ):
            return self.get_response(request)

        if (
            request.user.is_authenticated
            and hasattr(request, "active_farm")
            and request.active_farm
            and request.user.role
            != "friend"  # Legacy friends don't need to sign new waivers
        ):
            today = timezone.now().date()

            # 1. Fetch all currently active, unexpired forms for this farm
            valid_forms = ComplianceForm.objects.filter(
                farm=request.active_farm, is_active=True
            ).exclude(does_expire=True, expiration_date__lt=today)

            if valid_forms.exists():
                # 2. Find which ones the user has ALREADY signed
                signed_form_ids = FormSignature.objects.filter(
                    user=request.user, form__in=valid_forms
                ).values_list("form_id", flat=True)

                # 3. If they are missing any signatures, drop the gate!
                if len(signed_form_ids) < valid_forms.count():
                    allowed_paths = [reverse("sign_waiver"), reverse("logout")]

                    if request.path not in allowed_paths:
                        return redirect("sign_waiver")

        return self.get_response(request)
