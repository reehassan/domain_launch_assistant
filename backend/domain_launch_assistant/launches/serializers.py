# domain_launch_assistant/launches/serializers.py
from rest_framework import serializers
from .models import LaunchProject

class LaunchProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaunchProject
        fields = ["id", "name", "business_description", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "created_at", "updated_at"]