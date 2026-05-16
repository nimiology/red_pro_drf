import requests
from django.conf import settings
from django.utils import timezone
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
            'client_id': config('STRAVA_CLIENT_ID'),
            'client_secret': config('STRAVA_CLIENT_SECRET'),
            'grant_type': 'refresh_token',
            'refresh_token': user.strava_refresh_token
        }

        # Note: Using decouple's config here or settings.STRAVA_...
        # For now, let's assume they are in settings or accessible via decouple.
        from decouple import config
        payload['client_id'] = config('STRAVA_CLIENT_ID')
        payload['client_secret'] = config('STRAVA_CLIENT_SECRET')

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
            
            # Map JSON to Model
            activity, created = Activity.objects.update_or_create(
                strava_id=data['id'],
                defaults={
                    'athlete': user,
                    'external_id': data.get('external_id'),
                    'upload_id': data.get('upload_id'),
                    'name': data.get('name'),
                    'description': data.get('description', ''),
                    'type': data.get('type'),
                    'sport_type': data.get('sport_type'),
                    'distance': data.get('distance'),
                    'moving_time': data.get('moving_time'),
                    'elapsed_time': data.get('elapsed_time'),
                    'total_elevation_gain': data.get('total_elevation_gain'),
                    'elev_high': data.get('elev_high'),
                    'elev_low': data.get('elev_low'),
                    'average_speed': data.get('average_speed'),
                    'max_speed': data.get('max_speed'),
                    'average_cadence': data.get('average_cadence'),
                    'average_temp': data.get('average_temp'),
                    'average_watts': data.get('average_watts'),
                    'weighted_average_watts': data.get('weighted_average_watts'),
                    'max_watts': data.get('max_watts'),
                    'kilojoules': data.get('kilojoules'),
                    'device_watts': data.get('device_watts', False),
                    'has_heartrate': data.get('has_heartrate', False),
                    'average_heartrate': data.get('average_heartrate'),
                    'max_heartrate': data.get('max_heartrate'),
                    'suffer_score': data.get('suffer_score'),
                    'calories': data.get('calories'),
                    'start_date': data.get('start_date'),
                    'start_date_local': data.get('start_date_local'),
                    'timezone': data.get('timezone'),
                    'utc_offset': data.get('utc_offset'),
                    'start_latlng': data.get('start_latlng'),
                    'end_latlng': data.get('end_latlng'),
                    'map_polyline': data.get('map', {}).get('polyline'),
                    'summary_polyline': data.get('map', {}).get('summary_polyline'),
                    'achievement_count': data.get('achievement_count', 0),
                    'kudos_count': data.get('kudos_count', 0),
                    'comment_count': data.get('comment_count', 0),
                    'athlete_count': data.get('athlete_count', 1),
                    'photo_count': data.get('photo_count', 0),
                    'total_photo_count': data.get('total_photo_count', 0),
                    'trainer': data.get('trainer', False),
                    'commute': data.get('commute', False),
                    'manual': data.get('manual', False),
                    'private': data.get('private', False),
                    'flagged': data.get('flagged', False),
                    'gear_id': data.get('gear_id'),
                    'raw_data': data # The whole thing
                }
            )
            return activity
        else:
            print(f"Failed to fetch activity {strava_activity_id}: {response.status_code}")
            return None
