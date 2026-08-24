# domain_launch_assistant/launches/serializers.py
from rest_framework import serializers

from domain_launch_assistant.brands.serializers import BrandIdeaSerializer

from .models import LaunchProject


class LaunchProjectSerializer(serializers.ModelSerializer):
    selected_brand = BrandIdeaSerializer(read_only=True)
    # `domains` app doesn't exist yet — always null until it's built.
    selected_domain = serializers.SerializerMethodField()

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

    def get_selected_domain(self, obj):
        return None
