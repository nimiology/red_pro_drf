from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ActivityViewSet, StravaWebhookView

router = DefaultRouter()
router.register(r'logs', ActivityViewSet, basename='activity')

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/', StravaWebhookView.as_view(), name='strava-webhook'),
]
