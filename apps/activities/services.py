import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from .models import Activity
from apps.accounts.models import User

class StravaSyncService:
    @staticmethod
    def refresh_user_token(user):
        """
        Refreshes the Strava access token if it has expired.
        """
        if user.strava_token_expires_at and user.strava_token_expires_at > timezone.now() + timedelta(minutes=5):
            return user.strava_access_token

        url = "https://www.strava.com/oauth/token"
        payload = {
            'client_id': settings.STRAVA_CLIENT_ID,
            'client_secret': settings.STRAVA_CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': user.strava_refresh_token
        }

        response = requests.post(url, data=payload)
        if response.status_code == 200:
            data = response.json()
            user.strava_access_token = data['access_token']
            user.strava_refresh_token = data['refresh_token']
            user.strava_token_expires_at = timezone.now() + timedelta(seconds=data['expires_in'])
            user.save()
            return user.strava_access_token
        return None

    @staticmethod
    def sync_activity(strava_activity_id, strava_athlete_id):
        """
        Fetches a detailed activity from Strava and saves it to the database.
        """
        try:
            user = User.objects.get(strava_id=strava_athlete_id)
        except User.DoesNotExist:
            print(f"User with strava_id {strava_athlete_id} not found.")
            return None

        access_token = StravaSyncService.refresh_user_token(user)
        if not access_token:
            print(f"Could not refresh token for user {user.username}")
            return None

        url = f"https://www.strava.com/api/v3/activities/{strava_activity_id}"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            
            # Prepare mapping for fields that match Strava data keys exactly
            defaults = {
                'athlete': user,
                'description': data.get('description', ''),
                'start_date': parse_datetime(data.get('start_date')),
                'map_polyline': data.get('map', {}).get('polyline'),
                'summary_polyline': data.get('map', {}).get('summary_polyline'),
            }

            # List of fields that map directly from data keys
            direct_fields = [
                'external_id', 'upload_id', 'name', 'type', 'sport_type',
                'distance', 'moving_time', 'elapsed_time', 'total_elevation_gain',
                'elev_high', 'elev_low', 'average_speed', 'max_speed',
                'average_cadence', 'average_temp', 'average_watts',
                'weighted_average_watts', 'max_watts', 'kilojoules',
                'device_watts', 'has_heartrate', 'average_heartrate',
                'max_heartrate', 'suffer_score', 'calories',
                'start_latlng', 'end_latlng', 'achievement_count'
            ]

            for field in direct_fields:
                if field in data:
                    defaults[field] = data[field]

            activity, created = Activity.objects.update_or_create(
                strava_id=data['id'],
                defaults=defaults
            )
            return activity
        else:
            print(f"Failed to fetch activity {strava_activity_id}: {response.status_code}")
            return None

    @staticmethod
    def sync_recent_activities(user, per_page=30):
        """
        Fetches recent activities for a user from Strava and saves them.
        """
        access_token = StravaSyncService.refresh_user_token(user)
        if not access_token:
            return False

        url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'per_page': per_page}
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            activities_data = response.json()
            for data in activities_data:
                # We can reuse sync_activity or just save the summary data here.
                # Since the summary data contains most fields, we'll save it.
                defaults = {
                    'athlete': user,
                    'name': data.get('name'),
                    'type': data.get('type'),
                    'sport_type': data.get('sport_type'),
                    'distance': data.get('distance'),
                    'moving_time': data.get('moving_time'),
                    'elapsed_time': data.get('elapsed_time'),
                    'total_elevation_gain': data.get('total_elevation_gain'),
                    'start_date': parse_datetime(data.get('start_date')) if data.get('start_date') else None,
                    'average_speed': data.get('average_speed'),
                    'max_speed': data.get('max_speed'),
                    'has_heartrate': data.get('has_heartrate', False),
                    'average_heartrate': data.get('average_heartrate'),
                    'max_heartrate': data.get('max_heartrate'),
                }
                Activity.objects.update_or_create(
                    strava_id=data['id'],
                    defaults=defaults
                )
            return True
        return False
