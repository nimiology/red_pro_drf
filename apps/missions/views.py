from django.db.models import Q
from rest_framework import viewsets, permissions
from .models import Mission
from .serializers import MissionSerializer

from apps.accounts.permissions import IsCoachOrReadOnly

class MissionViewSet(viewsets.ModelViewSet):
    queryset = Mission.objects.all()
    serializer_class = MissionSerializer
    permission_classes = [IsCoachOrReadOnly]
    filterset_fields = {
        'status': ['exact'],
        'athlete': ['exact'],
        'squad': ['exact'],
        'coach': ['exact'],
        'hr_zone': ['exact', 'in'],
        'scheduled_date': ['exact', 'gt', 'lt', 'gte', 'lte'],
    }
    ordering_fields = '__all__'
    ordering = ['-scheduled_date']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'COACH':
            return Mission.objects.filter(coach=user)
        # Athlete sees missions assigned to them OR to their squads
        return Mission.objects.filter(
            Q(athlete=user) | Q(squad__athletes=user)
        ).distinct()

    def perform_create(self, serializer):
        # Set the coach as the logged-in user
        serializer.save(coach=self.request.user)
