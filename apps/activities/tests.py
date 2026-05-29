from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch, MagicMock
from apps.accounts.models import User
from .models import Activity
from decouple import config
from apps.squads.models import Squad
from .services import StravaSyncService

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


class IncrementalSyncTests(TestCase):
    """Tests for StravaSyncService.sync_recent_activities incremental logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='sync_user',
            password='pass',
            strava_id='999',
            strava_access_token='tok_abc',
            strava_refresh_token='ref_abc',
        )
        # Ensure date_joined is set (AbstractUser does this automatically)
        self.date_joined_epoch = int(self.user.date_joined.timestamp())

    def _make_strava_activity(self, strava_id, name='Run', start_date='2025-06-01T08:00:00Z'):
        """Helper to build a Strava-like activity dict."""
        return {
            'id': strava_id,
            'name': name,
            'type': 'Run',
            'sport_type': 'Run',
            'distance': 5000,
            'moving_time': 1200,
            'elapsed_time': 1300,
            'total_elevation_gain': 50,
            'start_date': start_date,
            'average_speed': 4.0,
            'max_speed': 6.0,
            'has_heartrate': False,
            'average_heartrate': None,
            'max_heartrate': None,
            'calories': 300,
            'elev_high': 100,
            'elev_low': 50,
            'map': {'summary_polyline': 'abc123'},
            'achievement_count': 2,
        }

    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    @patch('apps.activities.services.requests.get')
    def test_sync_uses_latest_activity_date_when_activities_exist(self, mock_get, mock_refresh):
        """
        When the user already has activities, the Strava API should be called
        with 'after' = the latest activity's start_date epoch.
        """
        mock_refresh.return_value = 'fresh_token'

        # Create an existing activity
        existing = Activity.objects.create(
            athlete=self.user, strava_id=100, name='Old Run',
            distance=3000, moving_time=900, elapsed_time=1000,
            total_elevation_gain=20, type='Run', sport_type='Run',
            average_speed=3.5, max_speed=5.0,
            start_date='2025-05-15T10:00:00Z',
        )
        existing.refresh_from_db()
        expected_after = int(existing.start_date.timestamp())

        # Mock Strava API: page 1 returns one activity, page 2 returns empty
        mock_response_page1 = MagicMock()
        mock_response_page1.status_code = 200
        mock_response_page1.json.return_value = [
            self._make_strava_activity(200, 'New Run', '2025-06-01T08:00:00Z')
        ]

        mock_response_page2 = MagicMock()
        mock_response_page2.status_code = 200
        mock_response_page2.json.return_value = []

        mock_get.side_effect = [mock_response_page1, mock_response_page2]

        result = StravaSyncService.sync_recent_activities(self.user)
        self.assertTrue(result)

        # Verify the 'after' param was the latest activity's epoch
        first_call_params = mock_get.call_args_list[0]
        self.assertEqual(first_call_params[1]['params']['after'], expected_after)

        # Verify new activity was created
        self.assertTrue(Activity.objects.filter(strava_id=200).exists())
        # Old activity should still be there
        self.assertTrue(Activity.objects.filter(strava_id=100).exists())
        self.assertEqual(Activity.objects.filter(athlete=self.user).count(), 2)

    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    @patch('apps.activities.services.requests.get')
    def test_sync_uses_date_joined_when_no_activities(self, mock_get, mock_refresh):
        """
        When the user has no activities, the Strava API should be called
        with 'after' = user.date_joined epoch.
        """
        mock_refresh.return_value = 'fresh_token'

        # No existing activities for this user
        self.assertEqual(Activity.objects.filter(athlete=self.user).count(), 0)

        mock_response_page1 = MagicMock()
        mock_response_page1.status_code = 200
        mock_response_page1.json.return_value = [
            self._make_strava_activity(301, 'First Run', '2025-04-10T09:00:00Z'),
            self._make_strava_activity(302, 'Second Run', '2025-04-12T09:00:00Z'),
        ]

        mock_response_page2 = MagicMock()
        mock_response_page2.status_code = 200
        mock_response_page2.json.return_value = []

        mock_get.side_effect = [mock_response_page1, mock_response_page2]

        result = StravaSyncService.sync_recent_activities(self.user)
        self.assertTrue(result)

        # Verify the 'after' param was the user's date_joined epoch
        first_call_params = mock_get.call_args_list[0]
        self.assertEqual(first_call_params[1]['params']['after'], self.date_joined_epoch)

        # Both activities should have been created
        self.assertEqual(Activity.objects.filter(athlete=self.user).count(), 2)

    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    @patch('apps.activities.services.requests.get')
    def test_sync_paginates_through_multiple_pages(self, mock_get, mock_refresh):
        """
        Verify that sync loops through all pages until Strava returns an empty list.
        """
        mock_refresh.return_value = 'fresh_token'

        # Page 1
        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = [
            self._make_strava_activity(401, 'Page1 Run1'),
            self._make_strava_activity(402, 'Page1 Run2'),
        ]

        # Page 2
        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = [
            self._make_strava_activity(403, 'Page2 Run1'),
        ]

        # Page 3 (empty — stops pagination)
        page3 = MagicMock()
        page3.status_code = 200
        page3.json.return_value = []

        mock_get.side_effect = [page1, page2, page3]

        result = StravaSyncService.sync_recent_activities(self.user)
        self.assertTrue(result)

        # All 3 activities across 2 pages should be created
        self.assertEqual(Activity.objects.filter(athlete=self.user).count(), 3)
        # 3 API calls total (page 1, 2, 3)
        self.assertEqual(mock_get.call_count, 3)

    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    @patch('apps.activities.services.requests.get')
    def test_sync_returns_false_on_strava_api_failure(self, mock_get, mock_refresh):
        """
        If Strava API returns a non-200 status, sync should return False.
        """
        mock_refresh.return_value = 'fresh_token'

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = StravaSyncService.sync_recent_activities(self.user)
        self.assertFalse(result)

        # No activities should be created
        self.assertEqual(Activity.objects.filter(athlete=self.user).count(), 0)

    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    def test_sync_returns_false_when_token_refresh_fails(self, mock_refresh):
        """
        If token refresh fails, sync should return False immediately.
        """
        mock_refresh.return_value = None

        result = StravaSyncService.sync_recent_activities(self.user)
        self.assertFalse(result)

    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    @patch('apps.activities.services.requests.get')
    def test_sync_update_or_create_does_not_duplicate(self, mock_get, mock_refresh):
        """
        If a strava_id already exists, it should be updated, not duplicated.
        """
        mock_refresh.return_value = 'fresh_token'

        # Pre-existing activity with strava_id=500
        Activity.objects.create(
            athlete=self.user, strava_id=500, name='Original Name',
            distance=1000, moving_time=600, elapsed_time=700,
            total_elevation_gain=10, type='Run', sport_type='Run',
            average_speed=2.0, max_speed=3.0,
            start_date='2025-03-01T08:00:00Z',
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            self._make_strava_activity(500, 'Updated Name', '2025-03-01T08:00:00Z')
        ]

        mock_empty = MagicMock()
        mock_empty.status_code = 200
        mock_empty.json.return_value = []

        mock_get.side_effect = [mock_response, mock_empty]

        result = StravaSyncService.sync_recent_activities(self.user)
        self.assertTrue(result)

        # Should still be only 1 activity, but with updated name
        self.assertEqual(Activity.objects.filter(strava_id=500).count(), 1)
        updated = Activity.objects.get(strava_id=500)
        self.assertEqual(updated.name, 'Updated Name')

