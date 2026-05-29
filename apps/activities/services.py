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
    def sync_recent_activities(user, per_page=200):
        """
        Incrementally syncs Strava activities for a user.

        - If the user already has synced activities, fetches only activities
          after the most recent one's start_date.
        - If the user has no activities, fetches everything since their
          account creation date (date_joined).
        - Paginates through all available pages from the Strava API.
        """
        access_token = StravaSyncService.refresh_user_token(user)
        if not access_token:
            return False

        # Determine the "after" epoch timestamp for incremental sync
        latest_activity = (
            Activity.objects.filter(athlete=user)
            .order_by('-start_date')
            .first()
        )
        if latest_activity:
            after_epoch = int(latest_activity.start_date.timestamp())
        else:
            # No existing activities — sync from account creation
            after_epoch = int(user.date_joined.timestamp())

        url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {'Authorization': f'Bearer {access_token}'}
        page = 1

        while True:
            params = {
                'after': after_epoch,
                'per_page': per_page,
                'page': page,
            }

            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                return False

            activities_data = response.json()
            if not activities_data:
                break  # No more pages

            for data in activities_data:
                defaults = {
                    'athlete': user,
                    'name': data.get('name'),
                    'type': data.get('type'),
                    'sport_type': data.get('sport_type'),
                    'distance': data.get('distance'),
                    'moving_time': data.get('moving_time'),
                    'elapsed_time': data.get('elapsed_time'),
                    'total_elevation_gain': data.get('total_elevation_gain'),
                    'start_date': (
                        parse_datetime(data.get('start_date'))
                        if data.get('start_date') else None
                    ),
                    'average_speed': data.get('average_speed'),
                    'max_speed': data.get('max_speed'),
                    'has_heartrate': data.get('has_heartrate', False),
                    'average_heartrate': data.get('average_heartrate'),
                    'max_heartrate': data.get('max_heartrate'),
                    'calories': data.get('calories'),
                    'elev_high': data.get('elev_high'),
                    'elev_low': data.get('elev_low'),
                    'summary_polyline': data.get('map', {}).get('summary_polyline'),
                    'achievement_count': data.get('achievement_count', 0),
                }
                Activity.objects.update_or_create(
                    strava_id=data['id'],
                    defaults=defaults
                )

            page += 1

        return True

    @staticmethod
    def ensure_webhook_subscribed():
        """
        Checks if a push subscription is already active on Strava for this client.
        If not, creates one using settings.STRAVA_WEBHOOK_URL and settings.STRAVA_VERIFY_TOKEN.
        """
        client_id = settings.STRAVA_CLIENT_ID
        client_secret = settings.STRAVA_CLIENT_SECRET
        verify_token = settings.STRAVA_VERIFY_TOKEN
        callback_url = settings.STRAVA_WEBHOOK_URL

        if not client_id or not client_secret or not callback_url or not verify_token:
            print("Strava credentials or webhook configurations are incomplete. Skipping subscription activation.")
            return False

        # 1. Check existing subscriptions
        get_url = "https://www.strava.com/api/v3/push_subscriptions"
        params = {
            'client_id': client_id,
            'client_secret': client_secret,
        }
        try:
            response = requests.get(get_url, params=params)
            if response.status_code == 200:
                subscriptions = response.json()
                # If there's an active subscription with the exact same callback URL, we're good!
                for sub in subscriptions:
                    if sub.get('callback_url') == callback_url:
                        print(f"Webhook already subscribed with ID {sub.get('id')} to {callback_url}")
                        return True
                    else:
                        # If a subscription exists but points to a different callback URL, we should delete it.
                        # Strava only allows 1 subscription per application client.
                        sub_id = sub.get('id')
                        print(f"Deleting outdated/conflicting Strava webhook subscription {sub_id}...")
                        delete_url = f"https://www.strava.com/api/v3/push_subscriptions/{sub_id}"
                        requests.delete(delete_url, data=params)
        except Exception as e:
            print(f"Error checking existing Strava subscriptions: {e}")

        # 2. Create the subscription
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'callback_url': callback_url,
            'verify_token': verify_token
        }
        try:
            print(f"Subscribing to Strava webhooks with callback: {callback_url}...")
            response = requests.post(get_url, data=payload)
            if response.status_code == 201:
                data = response.json()
                print(f"Successfully subscribed! ID: {data.get('id')}")
                return True
            else:
                print(f"Failed to subscribe: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Error creating Strava webhook subscription: {e}")
            return False
