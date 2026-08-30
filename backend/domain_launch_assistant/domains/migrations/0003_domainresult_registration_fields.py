from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("domains", "0002_pricing_claims_recommendation"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainresult",
            name="registered_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text=(
                    "When simulate_registration_task last succeeded for this "
                    "domain. Presence (not truthiness) is the 'was this "
                    "registered' signal — null means never registered. "
                    "Previously this fact only lived in an unpersisted Celery "
                    "task result / frontend useState, which reset on every "
                    "navigation or reload."
                ),
            ),
        ),
        migrations.AddField(
            model_name="domainresult",
            name="registration_order_id",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="domainresult",
            name="privacy_enabled",
            field=models.BooleanField(
                null=True,
                blank=True,
                help_text=(
                    "Last known WHOIS privacy state from either registration "
                    "or a subsequent toggle-privacy/ call. Null means never "
                    "set (not yet registered, or registered but privacy never "
                    "touched)."
                ),
            ),
        ),
    ]