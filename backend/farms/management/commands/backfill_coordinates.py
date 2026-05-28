import time
from django.core.management.base import BaseCommand
from farms.models import Farm
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


class Command(BaseCommand):
    help = "Backfills missing latitude and longitude coordinates for farms using Geopy."

    def handle(self, *args, **options):
        # Nominatim requires a custom user_agent for their free tier
        geolocator = Nominatim(user_agent="help_farmers_farm_locator")

        farms_to_update = Farm.objects.filter(
            address_line1__isnull=False, latitude__isnull=True
        ).exclude(address_line1="")

        total = farms_to_update.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("All farms already have coordinates!"))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {total} farms to geocode. Starting...")
        )

        success_count = 0
        fail_count = 0

        for farm in farms_to_update:
            try:
                # ATTEMPT 1: Try the strict, exact street address
                location = geolocator.geocode(farm.full_address, timeout=10)

                # ATTEMPT 2: Fallback to just City, State, and ZIP if the exact street isn't mapped
                if not location and farm.city and farm.state:
                    fallback_addr = (
                        f"{farm.city}, {farm.state} {farm.postal_code or ''}".strip()
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️ Strict address failed for {farm.name}. Trying fallback: '{fallback_addr}'"
                        )
                    )

                    time.sleep(1.1)  # Be nice to the free API before asking again
                    location = geolocator.geocode(fallback_addr, timeout=10)

                if location:
                    farm.latitude = location.latitude
                    farm.longitude = location.longitude
                    farm.save(update_fields=["latitude", "longitude"])

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Success: {farm.name} -> [{location.latitude}, {location.longitude}]"
                        )
                    )
                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"❌ Failed completely: {farm.name} (Address not found in database)"
                        )
                    )
                    fail_count += 1

            except (GeocoderTimedOut, GeocoderServiceError) as e:
                self.stdout.write(
                    self.style.ERROR(f"⚠️ API Error for {farm.name}: {e}")
                )
                fail_count += 1

            # CRITICAL: Nominatim's free tier strictly limits you to 1 request per second.
            time.sleep(1.1)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nGeocoding Complete! Success: {success_count} | Failed: {fail_count}"
            )
        )
