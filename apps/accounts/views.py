from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
import requests
from .models import User
from .serializers import UserSerializer
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta
from django.shortcuts import render as django_render

from django.db.models import Q
import threading
from apps.activities.services import StravaSyncService


def render_strava_status_page(request, success=True, error_message=None):
    """Render a branded HTML status page for the Strava OAuth callback."""
    if success:
        return django_render(request, 'accounts/strava_success.html')
    context = {
        'error_message': error_message or 'An unexpected error occurred during Strava authentication.',
    }
    return django_render(request, 'accounts/strava_error.html', context)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return User.objects.none()
        
        return User.objects.all()

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def strava_auth_url(self, request):
        """
        Returns the Strava authorization URL.
        """
        client_id = settings.STRAVA_CLIENT_ID
        redirect_uri = settings.STRAVA_REDIRECT_URI
        scope = "read,activity:read_all,profile:read_all"
        
        auth_url = (
            f"https://www.strava.com/oauth/authorize?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scope}&"
            f"state={request.user.id}"
        )
        return Response({"url": auth_url})

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny], url_path='strava_callback')
    def strava_callback(self, request):
        """
        Handles the callback from Strava, exchanges code for tokens.
        """
        code = request.query_params.get('code')
        state = request.query_params.get('state')

        if not code:
            return render_strava_status_page(request, success=False, error_message="No authorization code was provided from Strava. Please try again.")

        # Exchange code for tokens
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": settings.STRAVA_CLIENT_ID,
                "client_secret": settings.STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.STRAVA_REDIRECT_URI,
            }
        )

        if response.status_code != 200:
            err_msg = "Failed to exchange authorization code for access tokens. Please try again."
            try:
                err_data = response.json()
                print("STRAVA TOKEN EXCHANGE ERROR:", err_data)
                if 'message' in err_data:
                    err_msg = err_data['message']
            except Exception as e:
                print("STRAVA TOKEN EXCHANGE EXCEPTION:", e)
            return render_strava_status_page(request, success=False, error_message=err_msg)

        data = response.json()
        
        user = request.user
        if not user.is_authenticated and state:
            try:
                user = User.objects.get(pk=state)
            except (User.DoesNotExist, ValueError):
                pass

        if not user.is_authenticated:
            return render_strava_status_page(request, success=False, error_message="Could not identify your Red Pro account. Please make sure you start the connection flow inside the app.")

        user.strava_id = str(data['athlete']['id'])
        user.strava_access_token = data['access_token']
        user.strava_refresh_token = data['refresh_token']
   
        user.strava_token_expires_at = now() + timedelta(seconds=data['expires_in'])
        user.strava_raw_profile = data['athlete']
        user.save()

        # Fetch recent activities immediately
        threading.Thread(
            target=StravaSyncService.sync_recent_activities,
            args=(user,)
        ).start()

        # Ensure that the Strava webhook subscription is active (run in a background thread)
        threading.Thread(
            target=StravaSyncService.ensure_webhook_subscribed
        ).start()

        return render_strava_status_page(request, success=True)
