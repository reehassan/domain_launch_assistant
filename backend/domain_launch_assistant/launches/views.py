from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import LaunchProject
from .serializers import LaunchProjectSerializer


class LaunchProjectViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Handles:
        POST /api/v1/projects/
        GET  /api/v1/projects/
        GET  /api/v1/projects/{id}/

    Only Create, List, and Retrieve for Day 1 — Update/Delete come later
    once there's an actual workflow that needs them.
    """

    serializer_class = LaunchProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # This is the ownership enforcement: a user can never see another
        # user's projects because they're never in the queryset to begin
        # with. Don't rely on serializer-level checks alone for this.
        return LaunchProject.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)