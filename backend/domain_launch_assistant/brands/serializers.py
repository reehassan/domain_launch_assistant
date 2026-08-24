# apps/brands/serializers.py

from rest_framework import serializers

from domain_launch_assistant.brands.models import BrandIdea

class BrandIdeaSerializer(serializers.ModelSerializer):
    """
    Serializer for the BrandIdea API representation.

    This serializer is responsible only for representing BrandIdea
    data through the API.
    """

    class Meta:
        model = BrandIdea
        fields = (
            "id",
            "project",
            "name",
            "description",
            "is_selected",
            "created_at",
        )
        read_only_fields = (
            "id",
            "project",
            "created_at",
        )