from rest_framework import serializers

from domain_launch_assistant.tasks.models import TaskRecord


class TaskRecordSerializer(serializers.ModelSerializer):
    error = serializers.SerializerMethodField()

    class Meta:
        model = TaskRecord
        fields = ["task_id", "status", "result", "error"]

    def get_error(self, obj):
        if not obj.error_code:
            return None
        return {"code": obj.error_code, "message": obj.error_message}