from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings  # <-- ADD THIS IMPORT
from accounts.models import FarmMembership


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
    Intercepts users who have not signed the liability waiver for their active farm
    and forces them to the signature page before they can access the application.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow static CSS and images to pass through
        if request.path.startswith(settings.STATIC_URL) or request.path.startswith(
            settings.MEDIA_URL
        ):
            return self.get_response(request)

        # Only check authenticated users who have an active farm loaded
        if (
            request.user.is_authenticated
            and hasattr(request, "active_farm")
            and request.active_farm
        ):

            # Check if the Farm Manager has actually uploaded a waiver to be signed
            if request.active_farm.liability_waiver_text:

                # Fetch their specific membership to this farm
                membership = FarmMembership.objects.filter(
                    user=request.user, farm=request.active_farm
                ).first()

                if membership and not membership.agreed_to_waiver:
                    # Allowed paths so they don't get stuck in an infinite redirect loop
                    allowed_paths = [
                        reverse("sign_waiver"),
                        reverse("logout"),
                    ]

                    if request.path not in allowed_paths:
                        return redirect("sign_waiver")

        return self.get_response(request)
