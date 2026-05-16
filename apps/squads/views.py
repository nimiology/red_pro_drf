from rest_framework import viewsets, permissions
from .models import Squad
from .serializers import SquadSerializer

from apps.accounts.permissions import IsCoachOrReadOnly

class SquadViewSet(viewsets.ModelViewSet):
    queryset = Squad.objects.all()
    serializer_class = SquadSerializer
    permission_classes = [IsCoachOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = Squad.objects.prefetch_related('squadmembership_set', 'squadmembership_set__athlete')
        
        if user.role == 'COACH':
            return qs.filter(coach=user)
        return qs.filter(athletes=user)

    def perform_create(self, serializer):
        serializer.save(coach=self.request.user)
