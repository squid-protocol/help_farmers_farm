import uuid
from django.db import migrations


def generate_unique_tokens(apps, schema_editor):
    Farm = apps.get_model("farms", "Farm")
    for farm in Farm.objects.all():
        farm.invite_token = uuid.uuid4()
        farm.save(update_fields=["invite_token"])


class Migration(migrations.Migration):

    dependencies = [
        # Leave whatever Django auto-populated here alone!
        ("farms", "0017_farm_invite_token"),
    ]

    operations = [
        migrations.RunPython(
            generate_unique_tokens, reverse_code=migrations.RunPython.noop
        ),
    ]
