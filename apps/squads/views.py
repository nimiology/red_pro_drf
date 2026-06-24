from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Squad
from .serializers import SquadSerializer
from .leaderboard_serializers import LeaderboardEntrySerializer
from .services import LeaderboardService
from apps.accounts.serializers import UserSerializer
from apps.accounts.permissions import IsCoachOrReadOnly

class SquadViewSet(viewsets.ModelViewSet):
    queryset = Squad.objects.all()
    serializer_class = SquadSerializer
    permission_classes = [IsCoachOrReadOnly]
    filterset_fields = {
        'name': ['exact', 'icontains'],
        'coach': ['exact'],
        'created_at': ['exact', 'gt', 'lt'],
    }
    ordering_fields = '__all__'
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Squad.objects.prefetch_related('squadmembership_set', 'squadmembership_set__athlete')
        
        if user.role == 'COACH':
            return qs.filter(coach=user)
        return qs.filter(athletes=user)

    def perform_create(self, serializer):
        serializer.save(coach=self.request.user)

    @action(detail=True, methods=['get'], url_path='leaderboard', url_name='leaderboard')
    def leaderboard(self, request, pk=None):
        """
        Returns the ranked leaderboard for this squad.
        Query params:
            period — 'weekly' (default), 'monthly', or 'all_time'
            sort_by — 'distance' (default), or 'pace'
        """
        squad = self.get_object()
        period = request.query_params.get('period', 'weekly')
        sort_by = request.query_params.get('sort_by', 'distance')
        data = LeaderboardService.get_squad_leaderboard(squad, period=period, sort_by=sort_by)
        serializer = LeaderboardEntrySerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='members', url_name='members')
    def members(self, request, pk=None):
        """
        Returns the athletes (members) of this squad.
        """
        squad = self.get_object()
        serializer = UserSerializer(squad.athletes.all(), many=True, context={'request': request})
        return Response(serializer.data)
