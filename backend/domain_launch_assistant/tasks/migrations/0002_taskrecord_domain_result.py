from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0001_initial"),
        ("domains", "0002_pricing_claims_recommendation"),
    ]

    operations = [
        migrations.AddField(
            model_name="taskrecord",
            name="domain_result",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tasks",
                to="domains.domainresult",
                help_text=(
                    "Optional: which DomainResult this task is about, for "
                    "actions that only need to lock against tasks on the "
                    "SAME domain (e.g. claims-check) rather than the whole "
                    "project. Left null for project-wide dispatch actions "
                    "(search, recommend), which keep using the project-wide "
                    "lock unchanged."
                ),
            ),
        ),
    ]