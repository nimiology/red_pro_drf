from django.db.models import Q
from rest_framework import viewsets, permissions
from .models import Mission
from .serializers import MissionSerializer

from apps.accounts.permissions import IsCoachOrReadOnly
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
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

    

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Returns a simple summary of missions by status.
        """
        queryset = self.filter_queryset(self.get_queryset())
        status_counts = queryset.order_by().values('status').annotate(count=Count('id'))
        
        summary_data = {item['status']: item['count'] for item in status_counts}
        summary_data['total'] = sum(summary_data.values())
        
        return Response(summary_data)
