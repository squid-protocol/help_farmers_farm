import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Anonymizes user names and emails while preserving admin/Joe accounts."

    def handle(self, *args, **options):
        User = get_user_model()

        # Zero-dependency pools for random name generation
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
        ]

        self.stdout.write("Starting database anonymization...")

        users = User.objects.all()
        updated_count = 0

        for user in users:
            username_lower = user.username.lower()
            first_name_lower = user.first_name.lower() if user.first_name else ""

            # Safe-guard filter: Skip any user containing 'joe' or 'joseph'
            if (
                "joe" in username_lower
                or "joseph" in username_lower
                or "joe" in first_name_lower
            ):
                self.stdout.write(
                    self.style.SUCCESS(f"Skipping protected account: {user.username}")
                )
                continue

            # Generate random identities
            new_first = random.choice(first_names)
            new_last = random.choice(last_names)

            # Optional: Anonymize email format to keep local environment clean
            new_email = f"{new_first.lower()}.{new_last.lower()}{random.randint(10, 99)}@example.com"

            # Apply changes
            user.first_name = new_first
            user.last_name = new_last
            user.email = new_email
            user.save()

            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully anonymized {updated_count} user accounts."
            )
        )
