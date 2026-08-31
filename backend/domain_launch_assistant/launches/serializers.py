# domain_launch_assistant/launches/serializers.py
from rest_framework import serializers

from domain_launch_assistant.brands.serializers import BrandIdeaSerializer
from domain_launch_assistant.domains.serializers import DomainResultSerializer

from .models import LaunchProject


class LaunchProjectSerializer(serializers.ModelSerializer):
    selected_brand = BrandIdeaSerializer(read_only=True)
    selected_domain = DomainResultSerializer(read_only=True)
    class Meta:
        model = LaunchProject
        fields = [
            "id",
            "name",
            "business_description",
            "status",
            "selected_brand",
            "selected_domain",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "selected_brand",
            "selected_domain",
            "created_at",
            "updated_at",
        ]