from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("launches", "0004_launchproject_selected_domain"),
    ]

    operations = [
        migrations.AlterField(
            model_name="launchproject",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("GENERATING_BRANDS", "Generating Brands"),
                    ("BRANDS_READY", "Brands Ready"),
                    ("CHECKING_DOMAINS", "Checking Domains"),
                    ("DOMAIN_SELECTED", "Domain Selected"),
                    ("CONFIGURING_DNS", "Configuring DNS"),
                    ("VERIFYING_DNS", "Verifying DNS"),
                    ("READY", "Ready"),
                    ("FAILED", "Failed"),
                ],
                default="DRAFT",
                help_text="Current workflow status.",
                max_length=32,
            ),
        ),
    ]