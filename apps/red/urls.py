from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RedItemViewSet

router = DefaultRouter()
router.register(r'items', RedItemViewSet, basename='red-item')

urlpatterns = [
    path('', include(router.urls)),
]
