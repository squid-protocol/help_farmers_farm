import random
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from farms.models import Farm, Crop, WorkCommitment
from accounts.models import FarmMembership
from logs.models import LogEntry

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds the database with a robust matrix of farms, managers, edge-case users, and a fleet of normal volunteers with randomized historical logs."

    def handle(self, *args, **kwargs):
        self.stdout.write("🌱 Seeding the agricultural matrix...")

        today = timezone.now().date()

        # --- 1. BUILD THE FARMS ---
        farm_a, _ = Farm.objects.get_or_create(
            name="Caledonia Community CSA",
            defaults={
                "subscription_tier": "growth",
                "is_paid": True,
                "season_start": today.replace(month=4, day=1),
                "season_end": today.replace(month=11, day=1),
                "welcome_email_subject": "Welcome to Caledonia!",
            },
        )

        farm_b, _ = Farm.objects.get_or_create(
            name="Alto Micro-Greens",
            defaults={
                "subscription_tier": "trial",
                "is_paid": False,
                "welcome_email_subject": "Welcome to Alto Micro-Greens!",
            },
        )

        farm_c, _ = Farm.objects.get_or_create(
            name="The Rusty Tractor Heritage Farm",
            defaults={
                "subscription_tier": "starter",  # Or whatever triggers your read-only/expired state
                "is_paid": False,
            },
        )

        # --- 2. BUILD THE CROPS ---
        crops_a = [
            Crop.objects.get_or_create(farm=farm_a, crop_name=name)[0]
            for name in [
                "Heirloom Tomatoes",
                "Bell Peppers",
                "Sweet Onions",
                "Garlic",
                "Carrots",
            ]
        ]
        crops_b = [
            Crop.objects.get_or_create(farm=farm_b, crop_name=name)[0]
            for name in ["Micro-Radish", "Pea Shoots", "Sunflower Shoots"]
        ]

        # --- 3. BUILD COMMITMENT TIERS ---
        tier_a, _ = WorkCommitment.objects.get_or_create(
            farm=farm_a, name="Full Share", required_hours=40
        )
        tier_b, _ = WorkCommitment.objects.get_or_create(
            farm=farm_b, name="Standard", required_hours=20
        )

        # --- 4. THE CORE EDGE-CASE USERS ---
        edge_cases = [
            {
                "username": "admin",
                "email": "admin@system.local",
                "role": "account_manager",
                "is_super": True,
            },
            {
                "username": "manager_a",
                "email": "manager_a@caledonia.local",
                "role": "farm_manager",
            },
            {
                "username": "manager_b",
                "email": "manager_b@alto.local",
                "role": "farm_manager",
            },
            {
                "username": "manager_c",
                "email": "manager_c@rusty.local",
                "role": "farm_manager",
            },
            {
                "username": "veteran_vol",
                "email": "rosalyn@vol.local",
                "role": "volunteer",
                "legacy": 5,
            },
            {
                "username": "rookie_vol",
                "email": "lola@vol.local",
                "role": "volunteer",
                "legacy": 0,
            },
            {"username": "lone_wolf", "email": "loner@vol.local", "role": "volunteer"},
            {
                "username": "legacy_ghost",
                "email": "friend@vol.local",
                "role": "friend",
                "legacy": 10,
            },
        ]

        for ec in edge_cases:
            user, created = User.objects.get_or_create(
                username=ec["username"],
                defaults={
                    "email": ec["email"],
                    "first_name": ec["username"].split("_")[0].title(),
                    "last_name": "Test",
                    "role": ec["role"],
                    "legacy_years_volunteered": ec.get("legacy", 0),
                    "is_superuser": ec.get("is_super", False),
                    "is_staff": ec.get("is_super", False),
                    "is_email_verified": True,
                },
            )
            if created:
                user.set_password("password123")
                user.save()

        # Link core users
        mgr_a = User.objects.get(username="manager_a")
        FarmMembership.objects.get_or_create(user=mgr_a, farm=farm_a, is_approved=True)

        mgr_b = User.objects.get(username="manager_b")
        FarmMembership.objects.get_or_create(user=mgr_b, farm=farm_b, is_approved=True)

        mgr_c = User.objects.get(username="manager_c")
        FarmMembership.objects.get_or_create(user=mgr_c, farm=farm_c, is_approved=True)

        vet = User.objects.get(username="veteran_vol")
        FarmMembership.objects.get_or_create(
            user=vet, farm=farm_a, is_approved=True, work_commitment=tier_a
        )

        rookie = User.objects.get(username="rookie_vol")
        FarmMembership.objects.get_or_create(
            user=rookie, farm=farm_a, is_approved=True
        )  # No commitment tier yet

        ghost = User.objects.get(username="legacy_ghost")
        FarmMembership.objects.get_or_create(user=ghost, farm=farm_a, is_approved=True)

        # --- 5. THE "NORMAL" VOLUNTEER FLEET ---
        # Hardcoded list of realistic generic names to flush out the system
        normal_names = [
            ("Elias", "Stone"),
            ("Clara", "Vance"),
            ("Marcus", "Tate"),
            ("Sylvia", "Pond"),
            ("Julian", "Finch"),
            ("Naomi", "Rivers"),
            ("Declan", "Cross"),
            ("Vera", "Hull"),
            ("Silas", "Mercer"),
            ("Iris", "Locke"),
        ]

        # Valid activity choices based on standard farm tasks (Adjust to match your LogEntry choices)
        activities = ["P", "H", "W", "M", "T", "O"]

        for first, last in normal_names:
            username = f"{first.lower()}_{last.lower()}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@example.com",
                    "role": "volunteer",
                    "is_email_verified": True,
                    "farming_motto": random.choice(
                        [
                            "Soil over systems.",
                            "Just happy to be outside.",
                            "Will weed for tomatoes.",
                            "Learning the ropes.",
                            "",
                        ]
                    ),
                },
            )
            if created:
                user.set_password("password123")
                user.save()

            # Cross-Pollination Logic:
            # 60% chance to be at Farm A, 40% chance Farm B, 20% chance to be at BOTH.
            farms_joined = []
            if random.random() < 0.80:
                farms_joined.append((farm_a, crops_a, tier_a))
            if random.random() < 0.40 or not farms_joined:
                farms_joined.append((farm_b, crops_b, tier_b))

            for farm, crops, tier in farms_joined:
                FarmMembership.objects.get_or_create(
                    user=user,
                    farm=farm,
                    is_approved=True,
                    agreed_to_waiver=True,
                    work_commitment=tier,
                )

                # Generate 15 to 45 random logs per user per farm across the last 3 years
                num_logs = random.randint(15, 45)
                for _ in range(num_logs):
                    # Random date between 1000 days ago and today
                    random_days_ago = random.randint(0, 1000)
                    log_date = today - timedelta(days=random_days_ago)

                    # 10% chance it's a generic task (no crop attached)
                    selected_crop = (
                        None if random.random() < 0.10 else random.choice(crops)
                    )

                    # Random duration biased towards normal shift lengths
                    duration = Decimal(str(round(random.uniform(1.0, 6.5), 1)))

                    LogEntry.objects.create(
                        farm=farm,
                        volunteer=user,
                        crop=selected_crop,
                        activity=random.choice(activities),
                        duration_hours=duration,
                        date_logged=log_date,
                    )

        # Seed some data for the Veteran specifically so their chart looks awesome
        for _ in range(30):
            LogEntry.objects.create(
                farm=farm_a,
                volunteer=vet,
                crop=random.choice(crops_a),
                activity=random.choice(activities),
                duration_hours=Decimal(str(round(random.uniform(2.0, 5.0), 1))),
                date_logged=today - timedelta(days=random.randint(0, 800)),
            )

        self.stdout.write(
            self.style.SUCCESS(
                "✅ Matrix seeded successfully. All personas and noise data are live."
            )
        )
