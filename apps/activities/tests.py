from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch, MagicMock
from apps.accounts.models import User
from .models import Activity
from decouple import config
from apps.squads.models import Squad

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

    def test_webhook_validation_success(self):
        """
        Test the GET handshake from Strava.
        """
        from django.test import override_settings
        with override_settings(STRAVA_VERIFY_TOKEN=self.verify_token):
            challenge = 'test_challenge'
            response = self.client.get(self.webhook_url, {
                'hub.mode': 'subscribe',
                'hub.challenge': challenge,
                'hub.verify_token': self.verify_token
            })
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()['hub.challenge'], challenge)

    def test_webhook_validation_failure(self):
        """
        Test handshake with wrong verify token.
        """
        from django.test import override_settings
        with override_settings(STRAVA_VERIFY_TOKEN=self.verify_token):
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

    @patch('apps.activities.views.StravaWebhookView._refresh_athlete_profile')
    def test_webhook_athlete_update_event(self, mock_refresh):
        """
        Test that an athlete.update webhook triggers profile re-fetch.
        """
        payload = {
            'object_type': 'athlete',
            'aspect_type': 'update',
            'object_id': 123456,
            'owner_id': 123456,
            'event_time': 1516126040,
        }
        response = self.client.post(self.webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_refresh.assert_called_once_with(123456)

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
            start_date="2024-01-01T08:00:00Z"
        )

    def test_get_activity_list(self):
        url = reverse('activity-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class ActivityMatrixSmashTests(APITestCase):
    def setUp(self):
        # Roles
        self.coach = User.objects.create_user(username='coach', password='pass', role='COACH')
        self.other_coach = User.objects.create_user(username='other_coach', password='pass', role='COACH')
        self.athlete = User.objects.create_user(username='athlete', password='pass', role='ATHLETE')
        self.other_athlete = User.objects.create_user(username='other_athlete', password='pass', role='ATHLETE')
        self.stranger = User.objects.create_user(username='stranger', password='pass', role='ATHLETE')
        
        # Squad
        self.squad = Squad.objects.create(name="Alpha", coach=self.coach)
        self.squad.athletes.add(self.athlete)
        
        # Activities
        self.activity_athlete = Activity.objects.create(
            athlete=self.athlete, name="Athlete Run", distance=5000, 
            moving_time=1200, elapsed_time=1300, total_elevation_gain=10,
            type="Run", sport_type="Run", average_speed=4, max_speed=5,
            start_date="2024-05-20T08:00:00Z"
        )
        self.activity_other = Activity.objects.create(
            athlete=self.other_athlete, name="Other Run", distance=3000,
            moving_time=800, elapsed_time=900, total_elevation_gain=5,
            type="Run", sport_type="Run", average_speed=4, max_speed=5,
            start_date="2024-05-21T08:00:00Z"
        )
        self.activity_stranger = Activity.objects.create(
            athlete=self.stranger, name="Stranger Run", distance=10000,
            moving_time=3600, elapsed_time=3700, total_elevation_gain=100,
            type="Run", sport_type="Run", average_speed=4, max_speed=5,
            start_date="2024-05-22T08:00:00Z"
        )
        self.activity_other_coach = Activity.objects.create(
            athlete=self.other_coach, name="Coach Run", distance=1000,
            moving_time=300, elapsed_time=350, total_elevation_gain=0,
            type="Run", sport_type="Run", average_speed=4, max_speed=5,
            start_date="2024-05-23T08:00:00Z"
        )

        self.list_url = reverse('activity-list')
        self.detail_url = lambda pk: reverse('activity-detail', kwargs={'pk': pk})

    def test_queryset_isolation_matrix(self):
        """
        Matrix test for GET requests (List and Detail).
        """
        # (User, Visible Activities Count, Detail Access to self.activity_athlete)
        matrix = [
            (self.athlete, 1, 200),       # Sees only own
            (self.coach, 1, 200),         # Sees squad member (athlete)
            (self.other_coach, 1, 404),   # Sees only own
            (self.other_athlete, 1, 404), # Sees only own
            (self.stranger, 1, 404),      # Sees only own
        ]

        for user, expected_count, detail_status in matrix:
            self.client.force_authenticate(user=user)
            
            # List
            resp = self.client.get(self.list_url)
            self.assertEqual(len(resp.data), expected_count, f"User {user.username} list count mismatch")
            
            # Detail
            resp = self.client.get(self.detail_url(self.activity_athlete.pk))
            self.assertEqual(resp.status_code, detail_status, f"User {user.username} detail status mismatch")

    def test_manual_creation(self):
        """
        Test that an athlete can manually create an activity.
        """
        self.client.force_authenticate(user=self.athlete)
        data = {
            "name": "Manual Walk",
            "distance": 2000,
            "moving_time": 1800,
            "elapsed_time": 1900,
            "total_elevation_gain": 0,
            "type": "Walk",
            "sport_type": "Walk",
            "average_speed": 1.1,
            "max_speed": 2.0,
            "start_date": "2024-05-25T10:00:00Z"
        }
        resp = self.client.post(self.list_url, data)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['athlete'], self.athlete.pk)
        self.assertIsNone(resp.data['strava_id'])

    def test_modification_isolation(self):
        """
        Coaches and other athletes should not be able to edit/delete athlete's activities.
        """
        # Coach (who manages this athlete) tries to edit
        self.client.force_authenticate(user=self.coach)
        resp = self.client.patch(self.detail_url(self.activity_athlete.pk), {"name": "Hacked by Coach"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        
        # Other Coach (unrelated) tries to edit
        self.client.force_authenticate(user=self.other_coach)
        resp = self.client.patch(self.detail_url(self.activity_athlete.pk), {"name": "Hacked by Other Coach"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        
        # Other athlete tries to edit
        self.client.force_authenticate(user=self.other_athlete)
        resp = self.client.patch(self.detail_url(self.activity_athlete.pk), {"name": "Hacked by Other"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND) # 404 because not in QS
        
        # Owner tries to edit
        self.client.force_authenticate(user=self.athlete)
        resp = self.client.patch(self.detail_url(self.activity_athlete.pk), {"name": "Updated by Owner"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.activity_athlete.refresh_from_db()
        self.assertEqual(self.activity_athlete.name, "Updated by Owner")

    def test_delete_isolation(self):
        """
        Only the owner should be able to delete.
        """
        # Coach tries to delete
        self.client.force_authenticate(user=self.coach)
        resp = self.client.delete(self.detail_url(self.activity_athlete.pk))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        
        # Other Coach (unrelated) tries to delete
        self.client.force_authenticate(user=self.other_coach)
        resp = self.client.delete(self.detail_url(self.activity_athlete.pk))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        
        # Owner tries to delete
        self.client.force_authenticate(user=self.athlete)
        resp = self.client.delete(self.detail_url(self.activity_athlete.pk))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    @patch('apps.activities.services.StravaSyncService.sync_recent_activities')
    def test_manual_sync(self, mock_sync_recent):
        """
        Test the manual sync endpoint.
        """
        url = reverse('activity-manual-sync')
        
        # Test without strava_id
        self.client.force_authenticate(user=self.stranger)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test with strava_id
        self.athlete.strava_id = '123'
        self.athlete.save()
        self.client.force_authenticate(user=self.athlete)
        mock_sync_recent.return_value = True
        
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_sync_recent.assert_called_once_with(self.athlete)
