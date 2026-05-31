import json
import threading
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from decouple import config
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsOwnerOrCoachReadOnly

from .models import Activity
from .serializers import ActivitySerializer
from .services import StravaSyncService
from apps.squads.models import Squad
from rest_framework.decorators import action
from rest_framework.response import Response
import requests as http_requests
from apps.accounts.models import User
from django.db.models import Q

class ActivityViewSet(viewsets.ModelViewSet):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated, IsOwnerOrCoachReadOnly]
    filterset_fields = {
        'type': ['exact', 'in'],
        'sport_type': ['exact', 'in'],
        'start_date': ['exact', 'gt', 'lt', 'gte', 'lte'],
        'athlete': ['exact'],
        'distance': ['exact', 'gt', 'lt'],
    }
    ordering_fields = '__all__'
    ordering = ['-start_date']

    def get_queryset(self):
        # Athletes see their own activities, Coaches see their own + squad activities
        user = self.request.user
        if user.role == 'COACH':
            return Activity.objects.filter(
                Q(athlete=user) | Q(athlete__squads__coach=user)
            ).distinct()
        return Activity.objects.filter(athlete=user)

    def perform_create(self, serializer):
        serializer.save(athlete=self.request.user)



    @action(detail=False, methods=['post'])
    def manual_sync(self, request):
        """
        Manually trigger a sync of recent Strava activities for the authenticated user.
        """
        user = request.user
        if not user.strava_id:
            return Response({'error': 'User is not connected to Strava.'}, status=400)
            
        success = StravaSyncService.sync_recent_activities(user)
        if success:
            return Response({'status': 'Sync completed successfully.'})
        return Response({'error': 'Failed to sync activities.'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class StravaWebhookView(View):
    def get(self, request, *args, **kwargs):
        """
        Handles the validation handshake from Strava.
        """
        hub_mode = request.GET.get('hub.mode')
        hub_challenge = request.GET.get('hub.challenge')
        hub_verify_token = request.GET.get('hub.verify_token')

        if hub_mode == 'subscribe' and hub_verify_token == settings.STRAVA_VERIFY_TOKEN:
            return JsonResponse({'hub.challenge': hub_challenge})
        
        return HttpResponse("Invalid verify token", status=403)

    def post(self, request, *args, **kwargs):
        """
        Handles event notifications from Strava.
        """
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        object_type = data.get('object_type')
        aspect_type = data.get('aspect_type')
        object_id = data.get('object_id')
        owner_id = data.get('owner_id')

        if object_type == 'activity' and aspect_type == 'create':
            # Process the sync in a background thread to respond quickly to Strava
            threading.Thread(
                target=StravaSyncService.sync_activity,
                args=(object_id, owner_id)
            ).start()

        elif object_type == 'athlete' and aspect_type == 'update':
            # Athlete profile changed — re-fetch and update Redis.
            threading.Thread(
                target=self._refresh_athlete_profile,
                args=(owner_id,)
            ).start()

        return HttpResponse(status=200)

    @staticmethod
    def _refresh_athlete_profile(strava_athlete_id):
        """
        Re-fetch the athlete profile from Strava and store in the database.
        Called when a Strava 'athlete.update' webhook is received.
        """


        try:
            user = User.objects.get(strava_id=strava_athlete_id)
        except User.DoesNotExist:
            return

        access_token = StravaSyncService.refresh_user_token(user)
        if not access_token:
            return

        response = http_requests.get(
            "https://www.strava.com/api/v3/athlete",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            user.strava_raw_profile = response.json()
            user.save(update_fields=['strava_raw_profile'])
