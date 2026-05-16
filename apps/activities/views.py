import json
import threading
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from decouple import config
from rest_framework import viewsets, permissions
from .models import Activity
from .serializers import ActivitySerializer
from .services import StravaSyncService
from apps.squads.models import Squad


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Athletes see their own activities, Coaches see their squad activities
        user = self.request.user
        if user.role == 'COACH':
            # Simplified: see all activities of athletes in their managed squads
            athlete_ids = Squad.objects.filter(coach=user).values_list('athletes', flat=True)
            return Activity.objects.filter(athlete_id__in=athlete_ids)
        return Activity.objects.filter(athlete=user)

@method_decorator(csrf_exempt, name='dispatch')
class StravaWebhookView(View):
    def get(self, request, *args, **kwargs):
        """
        Handles the validation handshake from Strava.
        """
        hub_mode = request.GET.get('hub.mode')
        hub_challenge = request.GET.get('hub.challenge')
        hub_verify_token = request.GET.get('hub.verify_token')

        if hub_mode == 'subscribe' and hub_verify_token == config('STRAVA_VERIFY_TOKEN', default=''):
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

        # We only care about new activities
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

        return HttpResponse(status=200)
