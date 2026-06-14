from accounts.models import FarmMembership


class ActiveFarmMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_farm = None
        request.user_farms = []

        # Only process logged-in users
        if request.user.is_authenticated:
            # Fetch all approved memberships for this specific user
            memberships = FarmMembership.objects.filter(user=request.user, is_approved=True).select_related("farm")

            user_farms = [m.farm for m in memberships]
            request.user_farms = user_farms

            if user_farms:
                # Check their browser session for a selected farm
                active_farm_id = request.session.get("active_farm_id")

                if active_farm_id:
                    # Securely grab the farm ONLY if they are a member of it
                    request.active_farm = next((f for f in user_farms if f.id == active_farm_id), None)

                # If they don't have a session yet (first login), default to their first farm
                if not request.active_farm:
                    request.active_farm = user_farms[0]
                    request.session["active_farm_id"] = request.active_farm.id

        return self.get_response(request)
