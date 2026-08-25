# domain_launch_assistant/tasks/urls.py
from django.urls import path

from domain_launch_assistant.tasks.views import TaskDetailView

urlpatterns = [
    path(
        "tasks/<uuid:task_id>/",
        TaskDetailView.as_view(),
        name="task-detail",
    ),
]