import sqlite3
import os
from django.core.management.base import BaseCommand
from farms.models import Farm, Crop
from logs.models import LogEntry
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class Command(BaseCommand):
    help = "Extracts data from legacy SQLite DB and loads it into Django PostgreSQL"

    def handle(self, *args, **kwargs):
        db_path = "/srv/storage_16tb/projects/schuler_log/farm_log_processor/data/processed/processed_logs.db"
        
        if not os.path.exists(db_path):
            self.stderr.write(self.style.ERROR(f"Could not find SQLite DB at: {db_path}"))
            return

        self.stdout.write(self.style.WARNING("Connecting to Legacy SQLite Database..."))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  
        cursor = conn.cursor()

        # --- PHASE 1: Establish the Farm ---
        farm_name = "Schuler Farms (Legacy)"
        farm, created = Farm.objects.get_or_create(
            name=farm_name,
            defaults={
                "season_start": "2024-04-01", 
                "season_end": "2024-11-01"
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created root farm: {farm.name}"))

        # Build in-memory lookup dictionaries
        user_lookup = {u.username: u for u in CustomUser.objects.filter(farm=farm)}
        crop_lookup = {c.crop_name: c for c in Crop.objects.filter(farm=farm)}

        # --- PHASE 2: Granular Logs (with On-the-Fly Generation) ---
        self.stdout.write(self.style.WARNING("Importing Granular Logs and generating missing entities..."))

        activity_map = {
            "planting": "P",
            "tending": "T",
            "harvesting": "H",
            "off season": "O"
        }

        cursor.execute("""
            SELECT "Date", "hours", "Detected Activity", "Individual_Veggie", "StandardizedVolunteerName"
            FROM granular_farm_logs
            WHERE "hours" IS NOT NULL AND "hours" > 0 AND "StandardizedVolunteerName" IS NOT NULL
        """)

        logs_to_create = []
        skipped_logs = 0

        for row in cursor.fetchall():
            # 1. Match or Create User On-The-Fly
            raw_name = row["StandardizedVolunteerName"].strip()
            username = raw_name.lower().replace(" ", "_")
            volunteer = user_lookup.get(username)

            if not volunteer:
                volunteer, _ = CustomUser.objects.get_or_create(
                    username=username,
                    defaults={
                        "first_name": raw_name.split(" ")[0],
                        "last_name": " ".join(raw_name.split(" ")[1:]) if " " in raw_name else "",
                        "role": "volunteer",
                        "farm": farm,
                        "is_active": True
                    }
                )
                volunteer.set_unusable_password()
                volunteer.save()
                user_lookup[username] = volunteer  # Add to dictionary so we don't query again

            # 2. Match or Create Crop On-The-Fly
            raw_crop = row["Individual_Veggie"]
            crop = None
            if raw_crop:
                crop_name = raw_crop.strip()
                crop = crop_lookup.get(crop_name)
                if not crop:
                    crop, _ = Crop.objects.get_or_create(farm=farm, crop_name=crop_name)
                    crop_lookup[crop_name] = crop  # Add to dictionary

            # 3. Translate Activity
            raw_activity = row["Detected Activity"]
            clean_activity = "O" 
            if raw_activity:
                clean_activity = activity_map.get(raw_activity.strip().lower(), "O")

            # 4. Clean Date & Hours
            raw_date = row["Date"]
            date_logged = raw_date[:10] if raw_date else None
            hours = round(float(row["hours"]), 2)

            # 5. Build Log Entry
            if volunteer and date_logged:
                logs_to_create.append(
                    LogEntry(
                        farm=farm,
                        volunteer=volunteer,
                        crop=crop,
                        activity=clean_activity,
                        duration_hours=hours,
                        date_logged=date_logged
                    )
                )
            else:
                skipped_logs += 1

        # Fire them into PostgreSQL all at once
        LogEntry.objects.bulk_create(logs_to_create, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"Successfully imported {len(logs_to_create)} log entries!"))
        if skipped_logs > 0:
            self.stdout.write(self.style.ERROR(f"Skipped {skipped_logs} logs due to missing names/dates."))

        conn.close()
        self.stdout.write(self.style.SUCCESS("ETL Migration Complete!"))