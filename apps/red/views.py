from rest_framework import viewsets
from .models import RedItem
from .serializers import RedItemSerializer

class RedItemViewSet(viewsets.ModelViewSet):
    queryset = RedItem.objects.all()
    serializer_class = RedItemSerializer
