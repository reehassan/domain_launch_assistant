import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("launches", "0004_launchproject_selected_domain"),
        ("domains", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainresult",
            name="purchase_price",
            field=models.DecimalField(
                max_digits=10, decimal_places=2, null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name="domainresult",
            name="renewal_price",
            field=models.DecimalField(
                max_digits=10, decimal_places=2, null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name="domainresult",
            name="premium",
            field=models.BooleanField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="domainresult",
            name="purchase_type",
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.CreateModel(
            name="DomainClaim",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("has_claims", models.BooleanField()),
                ("claims_data", models.JSONField(blank=True, null=True)),
                ("checked_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("domain_result", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="claims",
                    to="domains.domainresult",
                )),
            ],
            options={
                "ordering": ["-checked_at"],
            },
        ),
        migrations.CreateModel(
            name="DomainRecommendation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reasoning", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="domain_recommendations",
                    to="launches.launchproject",
                )),
                ("recommended_domain", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="recommendations",
                    to="domains.domainresult",
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="domainclaim",
            index=models.Index(fields=["domain_result", "checked_at"], name="dc_domain_checked_idx"),
        ),
        migrations.AddIndex(
            model_name="domainclaim",
            index=models.Index(fields=["domain_result", "has_claims"], name="dc_domain_hasclaims_idx"),
        ),
        migrations.AddIndex(
            model_name="domainrecommendation",
            index=models.Index(fields=["project", "created_at"], name="drec_project_created_idx"),
        ),
        migrations.AddIndex(
            model_name="domainrecommendation",
            index=models.Index(fields=["recommended_domain"], name="drec_recommended_domain_idx"),
        ),
        migrations.AddConstraint(
            model_name="domainrecommendation",
            constraint=models.CheckConstraint(
                condition=~models.Q(reasoning=""),
                name="domainrecommendation_reasoning_not_empty",
            ),
        ),
    ]