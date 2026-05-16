from django.urls import path

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SquadViewSet

router = DefaultRouter()
router.register(r'', SquadViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
