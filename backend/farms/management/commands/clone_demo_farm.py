import uuid
import time
import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from farms.models import Farm, Crop, WorkCommitment
from accounts.models import FarmMembership
from logs.models import LogEntry

User = get_user_model()


class Command(BaseCommand):
    help = "Deep-clones a template farm into a new, isolated demo environment for a prospect."

    def add_arguments(self, parser):
        parser.add_argument(
            "--template-account",
            type=str,
            required=True,
            help="Account Number of the Master Template (e.g., FARM-42A25E49)",
        )
        parser.add_argument("--farm-name", type=str, required=True, help="Name of the new Demo Farm")
        parser.add_argument(
            "--manager-email",
            type=str,
            required=True,
            help="Real email of the prospect",
        )

    def handle(self, *args, **options):
        template_account = options["template_account"]
        new_farm_name = options["farm_name"]
        manager_email = options["manager_email"]

        # The dashboard strictly requires the name to START with "test"
        if not new_farm_name.lower().startswith("test"):
            new_farm_name = f"Test - {new_farm_name}"

        try:
            template_farm = Farm.objects.get(account_number=template_account)
        except Farm.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Template Farm Account {template_account} not found."))
            return

        self.stdout.write(f"Cloning '{template_farm.name}' into '{new_farm_name}'...")
        start_time = time.time()

        # Wrap everything in an atomic transaction so if it fails midway, it rolls back cleanly
        with transaction.atomic():
            # 1. Create the new Farm
            new_farm = Farm.objects.create(
                name=new_farm_name,
                season_start=template_farm.season_start,
                season_end=template_farm.season_end,
                is_paid=True,  # Give them premium access for the demo
                subscription_tier="growth",
            )

            # 2. Create the Prospect's Manager Account (Prefix with test_)
            manager_username = f"test_mgr_{uuid.uuid4().hex[:6]}"
            manager = User.objects.create(
                username=manager_username,
                email=manager_email,
                first_name="Demo",
                last_name="Manager",
                role="farm_manager",
                is_email_verified=True,
            )
            manager.set_password("demo2026")  # Give them a standard demo password
            manager.save()

            # Link the manager to the new farm
            FarmMembership.objects.create(user=manager, farm=new_farm, is_approved=True)

            # 3. Clone Crops
            crop_mapping = {}  # Maps old crop ID to new crop ID
            for crop in template_farm.crops.all():
                new_crop = Crop.objects.create(
                    farm=new_farm,
                    crop_name=crop.crop_name,
                    category=crop.category,
                    variety=crop.variety,
                    is_active=crop.is_active,
                )
                crop_mapping[crop.id] = new_crop

            # 4. Clone Work Commitments
            commitment_mapping = {}  # Maps old commitment ID to new commitment ID
            for commitment in template_farm.work_commitments.all():
                new_commitment = WorkCommitment.objects.create(
                    farm=new_farm,
                    name=commitment.name,
                    required_hours=commitment.required_hours,
                    symbol=commitment.symbol,
                )
                commitment_mapping[commitment.id] = new_commitment

            # 5. Clone Volunteers & Memberships
            # We MUST create new isolated User objects so prospects don't edit the master template's users
            vol_mapping = {}  # Maps old user ID to new user ID
            template_memberships = FarmMembership.objects.filter(farm=template_farm).exclude(user__role="farm_manager")

            first_names = [
                "Alex",
                "Jordan",
                "Taylor",
                "Morgan",
                "Casey",
                "Jamie",
                "Skyler",
                "Robin",
                "Pat",
                "Chris",
                "Sam",
                "Dana",
                "Drew",
                "Riley",
                "Avery",
            ]
            last_names = [
                "Smith",
                "Jones",
                "Miller",
                "Davis",
                "Garcia",
                "Rodriguez",
                "Wilson",
                "Martinez",
                "Anderson",
                "Taylor",
                "Thomas",
                "Moore",
                "Jackson",
                "Martin",
                "Lee",
            ]

            for membership in template_memberships:
                old_user = membership.user

                # Generate a completely random identity
                rand_first = random.choice(first_names)
                rand_last = random.choice(last_names)

                # Inject 'test_' to guarantee the dashboard ignores this user
                new_username = f"test_{rand_first.lower()}_{rand_last.lower()}_{uuid.uuid4().hex[:4]}"

                new_user = User.objects.create(
                    username=new_username,
                    email=f"{new_username}@demo.local",  # 100% guarantee no emails will send
                    first_name=rand_first,
                    last_name=rand_last,
                    role=old_user.role,
                    legacy_years_volunteered=old_user.legacy_years_volunteered,
                    is_active=old_user.is_active,
                )
                new_user.set_unusable_password()
                new_user.save()
                vol_mapping[old_user.id] = new_user

                # Link the new cloned volunteer to the new cloned farm, attaching the new cloned commitment tier
                new_commitment = (
                    commitment_mapping.get(membership.work_commitment_id) if membership.work_commitment_id else None
                )
                FarmMembership.objects.create(
                    user=new_user,
                    farm=new_farm,
                    is_approved=membership.is_approved,
                    work_commitment=new_commitment,
                )

            # 6. Clone Log Entries
            # We use bulk_create here because inserting thousands of logs one-by-one would be incredibly slow
            logs_to_create = []
            template_logs = LogEntry.objects.filter(farm=template_farm)

            for log in template_logs:
                new_volunteer = vol_mapping.get(log.volunteer_id)

                # If the volunteer was a manager or someone we didn't clone, skip their logs
                if not new_volunteer:
                    continue

                new_crop = crop_mapping.get(log.crop_id) if log.crop_id else None

                logs_to_create.append(
                    LogEntry(
                        farm=new_farm,
                        volunteer=new_volunteer,
                        crop=new_crop,
                        activity=log.activity,
                        duration_hours=log.duration_hours,
                        notes=log.notes,
                        date_logged=log.date_logged,
                    )
                )

            LogEntry.objects.bulk_create(logs_to_create, batch_size=1000)

        end_time = time.time()
        self.stdout.write(self.style.SUCCESS(f"✅ Deep clone complete in {round(end_time - start_time, 2)} seconds!"))
        self.stdout.write(self.style.SUCCESS(f"Manager Login: {manager_email} | Password: demo2026"))
