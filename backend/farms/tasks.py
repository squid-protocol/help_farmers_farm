from django.core.mail import send_mail, get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth import get_user_model
from farms.models import Farm
from accounts.models import FarmMembership

User = get_user_model()


def send_volunteer_welcome_email(user_id, farm_id, raw_password):
    """Compiles the manager's custom HTML and sends the automated welcome email."""
    try:
        user = User.objects.get(id=user_id)
        farm = Farm.objects.get(id=farm_id)
    except (User.DoesNotExist, Farm.DoesNotExist):
        return "Failed: User or Farm not found."

    if not user.email:
        return "Failed: User has no email."

    # Render the HTML email
    html_message = render_to_string(
        "farms/emails/welcome.html",
        {
            "user": user,
            "farm": farm,
            "raw_password": raw_password,
            # The |safe filter in the template renders the Trix HTML properly
            "custom_body": farm.welcome_email_body,
            "login_url": "https://helpingfarmersfarm.com/accounts/login/",
        },
    )

    # Strip the HTML tags for email clients that only support plain text
    plain_message = strip_tags(html_message)
    subject = farm.welcome_email_subject or f"Welcome to {farm.name}!"

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
    )

    return f"Welcome email sent to {user.email}"


def send_broadcast_email(farm_id, subject, custom_body, audience_value):
    """Compiles and mass-sends a broadcast email to a specific farm audience."""
    try:
        farm = Farm.objects.get(id=farm_id)
    except Farm.DoesNotExist:
        return "Failed: Farm not found."

    # 1. Start with a baseline: All active users who are NOT read-only legacy friends
    memberships = FarmMembership.objects.filter(
        farm=farm, is_approved=True, user__is_active=True
    ).exclude(user__role="friend")

    # 2. Filter down if a specific tier was selected
    if audience_value != "all" and audience_value.startswith("tier_"):
        try:
            tier_id = int(audience_value.split("_")[1])
            memberships = memberships.filter(work_commitment_id=tier_id)
        except ValueError:
            pass

    # 3. Extract just the users who actually have an email address
    users = [m.user for m in memberships if m.user.email]

    if not users:
        return "Failed: No valid email recipients found in that audience."

    # 4. Generate all email objects
    messages = []

    for user in users:
        # Render the custom HTML wrapper
        html_message = render_to_string(
            "farms/emails/broadcast.html",
            {"user": user, "farm": farm, "custom_body": custom_body},
        )
        plain_message = strip_tags(html_message)

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_message, "text/html")
        messages.append(email)

    # 5. Fire them off in batches to prevent SMTP socket timeouts
    connection = get_connection()
    connection.open()
    
    batch_size = 50
    try:
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            connection.send_messages(batch)
    finally:
        connection.close()

    return f"Broadcast sent to {len(messages)} recipients in batches of {batch_size}."
