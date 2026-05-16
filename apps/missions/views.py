from rest_framework import viewsets, permissions
from .models import Mission
from .serializers import MissionSerializer

from apps.accounts.permissions import IsCoachOrReadOnly

class MissionViewSet(viewsets.ModelViewSet):
    queryset = Mission.objects.all()
    serializer_class = MissionSerializer
    permission_classes = [IsCoachOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'COACH':
            return Mission.objects.filter(coach=user)
        return Mission.objects.filter(athlete=user)

    def perform_create(self, serializer):
        # Set the coach as the logged-in user
        serializer.save(coach=self.request.user)
