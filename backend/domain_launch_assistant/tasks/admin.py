from django.contrib import admin

from domain_launch_assistant.tasks.models import TaskRecord


@admin.register(TaskRecord)
class TaskRecordAdmin(admin.ModelAdmin):
    list_display = ("task_id", "project", "status", "created_at", "updated_at")
    list_filter = ("status",)
    readonly_fields = ("task_id", "created_at", "updated_at")