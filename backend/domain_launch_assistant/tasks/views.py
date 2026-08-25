from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domain_launch_assistant.tasks.models import TaskRecord
from domain_launch_assistant.tasks.serializers import TaskRecordSerializer


class TaskDetailView(APIView):
    """
    Corresponds to api-contract.md's task-status endpoint.
    Ownership enforced via project.user, matching every other app.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = get_object_or_404(
            TaskRecord,
            task_id=task_id,
            project__user=request.user,
        )
        serializer = TaskRecordSerializer(task)
        return Response(serializer.data)