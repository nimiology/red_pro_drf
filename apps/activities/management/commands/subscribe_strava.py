import requests
from django.core.management.base import BaseCommand
from decouple import config

class Command(BaseCommand):
    help = 'Subscribe to Strava webhooks'

    def add_arguments(self, parser):
        parser.add_argument('callback_url', type=str, help='The public callback URL for the webhook')

    def handle(self, *args, **options):
        callback_url = options['callback_url']
        client_id = config('STRAVA_CLIENT_ID')
        client_secret = config('STRAVA_CLIENT_SECRET')
        verify_token = config('STRAVA_VERIFY_TOKEN')

        url = "https://www.strava.com/api/v3/push_subscriptions"
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'callback_url': callback_url,
            'verify_token': verify_token
        }

        self.stdout.write(f"Subscribing to Strava webhooks with callback: {callback_url}...")
        response = requests.post(url, data=payload)

        if response.status_code == 201:
            data = response.json()
            self.stdout.write(self.style.SUCCESS(f"Successfully subscribed! ID: {data.get('id')}"))
        else:
            self.stdout.write(self.style.ERROR(f"Failed to subscribe: {response.status_code}"))
            self.stdout.write(self.style.ERROR(response.text))
