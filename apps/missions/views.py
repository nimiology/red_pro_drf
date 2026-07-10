from django.db.models import Q
from rest_framework import viewsets, permissions
from .models import Mission
from .serializers import MissionSerializer

from apps.accounts.permissions import IsCoachOrReadOnly
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
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

    def create(self, request, *args, **kwargs):
        # Support creating multiple missions for a list of athletes
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        athletes = data.pop('athletes', None)
        # If it was a QueryDict, pop might return a string or list. For JSON, it's a list.
        if isinstance(athletes, str):
            import json
            try:
                athletes = json.loads(athletes)
            except:
                athletes = [athletes]
                
        if athletes and isinstance(athletes, list):
            created_missions = []
            for athlete_id in athletes:
                athlete_data = data.copy()
                athlete_data['athlete'] = athlete_id
                serializer = self.get_serializer(data=athlete_data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)
                created_missions.append(serializer.data)
            return Response(created_missions, status=status.HTTP_201_CREATED)
            
        return super().create(request, *args, **kwargs)

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
