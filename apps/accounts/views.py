from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
import requests
from .models import User
from .serializers import UserSerializer
from .strava_cache import set_strava_raw_profile
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta


class UserViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

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
            f"scope={scope}"
        )
        return Response({"url": auth_url})

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny], url_path='strava_callback')
    def strava_callback(self, request):
        """
        Handles the callback from Strava, exchanges code for tokens.
        """

        
        code = request.query_params.get('code')
        if not code:
            return Response({"error": "No code provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Exchange code for tokens
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": settings.STRAVA_CLIENT_ID,
                "client_secret": settings.STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code"
            }
        )

        if response.status_code != 200:
            return Response(response.json(), status=response.status_code)

        data = response.json()
        # Note: In a real callback, we might not have the user authenticated in the session 
        # if they are coming from an external redirect. 
        # We might need a 'state' parameter to link back to the user.
        # For now, I'll assume we can use the authenticated user if the session persists,
        # or we might need to handle this differently for mobile.
        
        user = request.user
        if not user.is_authenticated:
            # If not authenticated (common for OAuth redirects), we'd usually use 'state'
            # to find the user. For now, let's return the data so the frontend can handle it
            # if they are using a webview or similar.
            return Response({
                "message": "Strava tokens received. Please send them to connect_strava endpoint.",
                "strava_data": data
            })

        user.strava_id = str(data['athlete']['id'])
        user.strava_access_token = data['access_token']
        user.strava_refresh_token = data['refresh_token']
   
        user.strava_token_expires_at = now() + timedelta(seconds=data['expires_in'])
        user.save()

        # Store the athlete profile blob in Redis (not in the DB).
        set_strava_raw_profile(user.pk, data['athlete'])

        return Response({"status": "strava connected successfully"})

