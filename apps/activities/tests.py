from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch, MagicMock
from apps.accounts.models import User
from .models import Activity
from decouple import config

class StravaWebhookTests(APITestCase):
    def setUp(self):
        self.webhook_url = reverse('strava-webhook')
        # Use a consistent token for testing
        self.verify_token = 'test_verify_token'
        self.user = User.objects.create_user(
            username='athlete_1',
            strava_id='123456',
            strava_access_token='access_123',
            strava_refresh_token='refresh_123'
        )

    @patch('apps.activities.views.config')
    def test_webhook_validation_success(self, mock_config):
        """
        Test the GET handshake from Strava.
        """
        mock_config.return_value = self.verify_token
        challenge = 'test_challenge'
        response = self.client.get(self.webhook_url, {
            'hub.mode': 'subscribe',
            'hub.challenge': challenge,
            'hub.verify_token': self.verify_token
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['hub.challenge'], challenge)

    @patch('apps.activities.views.config')
    def test_webhook_validation_failure(self, mock_config):
        """
        Test handshake with wrong verify token.
        """
        mock_config.return_value = self.verify_token
        response = self.client.get(self.webhook_url, {
            'hub.mode': 'subscribe',
            'hub.challenge': 'test_challenge',
            'hub.verify_token': 'wrong_token'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('apps.activities.services.StravaSyncService.sync_activity')
    def test_webhook_activity_create_event(self, mock_sync):
        """
        Test that a POST event for activity creation triggers a sync.
        """
        payload = {
            'object_type': 'activity',
            'aspect_type': 'create',
            'object_id': 987654321,
            'owner_id': 123456,
            'event_time': 1516126040
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify that sync_activity was called (it's called in a thread, but the patch should catch it)
        # We might need to wait or use a different testing strategy for threads, 
        # but let's see if the patch works.
        mock_sync.assert_called_once_with(987654321, 123456)

class ActivityAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_authenticate(user=self.user)
        self.activity = Activity.objects.create(
            athlete=self.user,
            strava_id=123,
            name="Morning Run",
            distance=5000,
            moving_time=1200,
            elapsed_time=1300,
            total_elevation_gain=50,
            type="Run",
            sport_type="Run",
            average_speed=4.5, # Added missing required fields
            max_speed=6.0,
            start_date="2024-01-01T08:00:00Z",
            start_date_local="2024-01-01T08:00:00Z",
            timezone="UTC",
            utc_offset=0,
            raw_data={}
        )

    def test_get_activity_list(self):
        url = reverse('activity-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
