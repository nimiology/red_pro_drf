from django.urls import reverse
from django.test import override_settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import User
from apps.accounts.strava_cache import (
    get_strava_raw_profile,
    set_strava_raw_profile,
    delete_strava_raw_profile,
)
import datetime
from unittest.mock import patch, MagicMock


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "profile-pic-test",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class UserMatrixSmashTests(APITestCase):
    """
    Matrix Smash Tests for User Onboarding and Roles.
    Tests every combination of role and onboarding state.
    """
    def setUp(self):
        self.athlete = User.objects.create_user(username='athlete', password='password123', role=User.Role.ATHLETE)
        self.coach = User.objects.create_user(username='coach', password='password123', role=User.Role.COACH)
        self.new_user = User.objects.create_user(username='newbie', password='password123', role=User.Role.NONE)

    def test_onboarding_progression_matrix(self):
        roles = [User.Role.ATHLETE, User.Role.COACH, User.Role.NONE]
        steps = [1, 5, 10]
        
        # We'll use djoser's 'user-me' for checking the current user state
        url = reverse('user-me')
        
        for role in roles:
            user = User.objects.create_user(username=f'user_{role}', password='password', role=role)
            self.client.force_authenticate(user=user)
            
            for step in steps:
                # Update onboarding step
                user.onboarding_step = step
                user.save()
                
                # Verify state via API
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data['onboarding_step'], step)
                self.assertEqual(response.data['role'], role)

    def test_role_and_finished_state_matrix(self):
        # Testing the combination of role and is_onboarding_finished
        url = reverse('user-me')
        
        for role in [User.Role.ATHLETE, User.Role.COACH]:
            for finished in [True, False]:
                user = User.objects.create_user(
                    username=f'u_{role}_{finished}', 
                    password='password', 
                    role=role,
                    is_onboarding_finished=finished
                )
                self.client.force_authenticate(user=user)
                response = self.client.get(url)
                self.assertEqual(response.data['is_onboarding_finished'], finished)

@override_settings(CACHES=LOCMEM_CACHE)
class UserProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_authenticate(user=self.user)

    def test_update_me_profile(self):
        url = reverse('user-me')
        data = {
            "full_name": "Alex Marshall",
            "birth_date": "1995-05-15",
            "weight": 72.5
        }
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['full_name'], "Alex Marshall")
        self.assertEqual(response.data['birth_date'], "1995-05-15")
        # Age should be calculated correctly (approx 29 or 30 or 31 depending on year)
        self.assertIsNotNone(response.data['age'])
        
    def test_age_calculation(self):
        url = reverse('user-me')
        # Set birth_date to 20 years ago
        today = datetime.date.today()
        birth_date = today.replace(year=today.year - 20)
        
        self.user.birth_date = birth_date
        self.user.save()
        
        response = self.client.get(url)
        self.assertEqual(response.data['age'], 20)

@override_settings(CACHES=LOCMEM_CACHE)
class StravaOAuthTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='stravauser', password='password123')
        self.client.force_authenticate(user=self.user)

    def test_strava_auth_url(self):
        url = reverse('user-strava-auth-url')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('url', response.data)
        self.assertIn('strava.com/oauth/authorize', response.data['url'])

    def test_strava_callback_no_code(self):
        url = reverse('user-strava-callback')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn(b'Connection Failed', response.content)

    @patch('apps.accounts.views.requests.post')
    @patch('apps.activities.services.StravaSyncService.ensure_webhook_subscribed')
    def test_strava_callback_success(self, mock_subscribe, mock_post):
        # Mock the exchange response from Strava token endpoint
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "mock_access",
            "refresh_token": "mock_refresh",
            "expires_in": 3600,
            "athlete": {
                "id": 99999,
                "firstname": "John",
                "lastname": "Doe"
            }
        }
        mock_post.return_value = mock_response

        url = reverse('user-strava-callback')
        # Call GET to the callback endpoint with code and state (user id)
        response = self.client.get(url, {
            'code': 'test_auth_code',
            'state': self.user.id
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn(b'Strava Connected', response.content)

        # Refresh from database and assert tokens and strava_id were saved
        self.user.refresh_from_db()
        self.assertEqual(self.user.strava_id, '99999')
        self.assertEqual(self.user.strava_access_token, 'mock_access')
        self.assertEqual(self.user.strava_refresh_token, 'mock_refresh')
        self.assertIsNotNone(self.user.strava_token_expires_at)

        # Verify that ensure_webhook_subscribed was triggered
        mock_subscribe.assert_called_once()




# ---------------------------------------------------------------------------
# strava_cache helper round-trip tests
# ---------------------------------------------------------------------------
@override_settings(CACHES=LOCMEM_CACHE)
class StravaCacheHelperTests(APITestCase):
    """Unit tests for get/set/delete_strava_raw_profile helpers."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='cache_user', password='password123')
        self.profile_data = {
            "id": 99,
            "profile": "https://cdn.strava.com/pic.jpg",
            "profile_medium": "https://cdn.strava.com/pic_m.jpg",
        }

    def tearDown(self):
        cache.clear()

    def test_set_and_get(self):
        set_strava_raw_profile(self.user.pk, self.profile_data)
        result = get_strava_raw_profile(self.user.pk)
        self.assertEqual(result, self.profile_data)

    def test_get_returns_none_when_empty(self):
        self.assertIsNone(get_strava_raw_profile(self.user.pk))

    def test_delete(self):
        set_strava_raw_profile(self.user.pk, self.profile_data)
        delete_strava_raw_profile(self.user.pk)
        self.assertIsNone(get_strava_raw_profile(self.user.pk))

    def test_set_invalidates_profile_pic_cache(self):
        """Setting a new raw profile should clear the derived pic cache."""
        pic_key = f"profile_pic:{self.user.pk}"
        cache.set(pic_key, "https://old.com/pic.jpg", timeout=3600)
        set_strava_raw_profile(self.user.pk, self.profile_data)
        self.assertIsNone(cache.get(pic_key))


# ---------------------------------------------------------------------------
# ProfilePicURL serializer tests (Redis-backed)
# ---------------------------------------------------------------------------
@override_settings(CACHES=LOCMEM_CACHE)
class ProfilePicURLTests(APITestCase):
    """
    Tests for the profile_pic_url serializer field.
    Raw profile data is now stored in Redis via strava_cache helpers.
    """

    def setUp(self):
        cache.clear()

        self.strava_profile = {
            "id": 12345,
            "firstname": "Jane",
            "lastname": "Doe",
            "profile": "https://dgalywyr863hv.cloudfront.net/pictures/athletes/12345/large.jpg",
            "profile_medium": "https://dgalywyr863hv.cloudfront.net/pictures/athletes/12345/medium.jpg",
        }

        self.user_with_strava = User.objects.create_user(
            username='strava_user',
            password='password123',
            strava_id='12345',
        )
        set_strava_raw_profile(self.user_with_strava.pk, self.strava_profile)

        self.user_no_strava = User.objects.create_user(
            username='no_strava_user',
            password='password123',
        )

        self.user_empty_strava = User.objects.create_user(
            username='empty_strava_user',
            password='password123',
            strava_id='99999',
        )
        set_strava_raw_profile(self.user_empty_strava.pk, {})

    def tearDown(self):
        cache.clear()

    def test_profile_pic_url_with_strava_profile(self):
        """User with strava raw profile in Redis returns the 'profile' URL."""
        self.client.force_authenticate(user=self.user_with_strava)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['profile_pic_url'],
            self.strava_profile['profile'],
        )

    def test_profile_pic_url_without_strava_profile(self):
        """User with no raw profile in Redis returns None."""
        self.client.force_authenticate(user=self.user_no_strava)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['profile_pic_url'])

    def test_profile_pic_url_with_empty_strava_profile(self):
        """User with empty raw profile ({}) in Redis returns None."""
        self.client.force_authenticate(user=self.user_empty_strava)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['profile_pic_url'])

    def test_profile_pic_url_falls_back_to_profile_medium(self):
        """When 'profile' key is missing, falls back to 'profile_medium'."""
        set_strava_raw_profile(self.user_with_strava.pk, {
            "profile_medium": "https://example.com/medium.jpg",
        })
        cache.delete(f"profile_pic:{self.user_with_strava.pk}")

        self.client.force_authenticate(user=self.user_with_strava)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile_pic_url'], "https://example.com/medium.jpg")

    def test_profile_pic_url_is_cached(self):
        """Second request should hit cache — changing Redis won't affect result."""
        self.client.force_authenticate(user=self.user_with_strava)
        url = reverse('user-me')

        # First request — populates pic cache
        response1 = self.client.get(url)
        self.assertEqual(response1.data['profile_pic_url'], self.strava_profile['profile'])

        # Change the Redis value (without using set_strava_raw_profile which
        # would invalidate the pic cache — simulate raw data change only).
        cache.set(
            f"strava_raw_profile:{self.user_with_strava.pk}",
            {"profile": "https://example.com/new.jpg"},
        )

        # Second request — should still return the pic-cache value
        response2 = self.client.get(url)
        self.assertEqual(response2.data['profile_pic_url'], self.strava_profile['profile'])

    def test_profile_pic_url_cache_expiry_returns_fresh_value(self):
        """After pic cache is cleared, fresh Redis value is returned."""
        self.client.force_authenticate(user=self.user_with_strava)
        url = reverse('user-me')

        # First request
        response1 = self.client.get(url)
        self.assertEqual(response1.data['profile_pic_url'], self.strava_profile['profile'])

        # Update Redis and clear pic cache (simulates 3-hour expiry)
        new_url = "https://example.com/updated.jpg"
        set_strava_raw_profile(self.user_with_strava.pk, {"profile": new_url})

        # Should now return the new URL
        response2 = self.client.get(url)
        self.assertEqual(response2.data['profile_pic_url'], new_url)


# ---------------------------------------------------------------------------
# Matrix smash: profile_pic_url across role × strava state
# ---------------------------------------------------------------------------
@override_settings(CACHES=LOCMEM_CACHE)
class ProfilePicURLMatrixTests(APITestCase):
    """
    Matrix smash: profile_pic_url across all role × strava state combinations.
    """

    STRAVA_STATES = {
        'full': {
            "profile": "https://cdn.strava.com/full.jpg",
            "profile_medium": "https://cdn.strava.com/medium.jpg",
        },
        'medium_only': {
            "profile_medium": "https://cdn.strava.com/medium.jpg",
        },
        'empty': {},
        'none': None,
    }

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_role_strava_state_matrix(self):
        """Every combination of role × strava state returns expected pic URL."""
        roles = [User.Role.ATHLETE, User.Role.COACH, User.Role.NONE]

        expected_map = {
            'full': "https://cdn.strava.com/full.jpg",
            'medium_only': "https://cdn.strava.com/medium.jpg",
            'empty': None,
            'none': None,
        }

        url = reverse('user-me')

        for role in roles:
            for state_name, strava_data in self.STRAVA_STATES.items():
                cache.clear()
                user = User.objects.create_user(
                    username=f'u_{role}_{state_name}',
                    password='password',
                    role=role,
                    strava_id=f'sid_{role}_{state_name}' if strava_data is not None else None,
                )
                if strava_data is not None:
                    set_strava_raw_profile(user.pk, strava_data)

                self.client.force_authenticate(user=user)
                response = self.client.get(url)
                self.assertEqual(
                    response.data['profile_pic_url'],
                    expected_map[state_name],
                    msg=f"Failed for role={role}, strava_state={state_name}",
                )


# ---------------------------------------------------------------------------
# Serializer API fallback test
# ---------------------------------------------------------------------------
from unittest.mock import patch, MagicMock


@override_settings(CACHES=LOCMEM_CACHE)
class ProfilePicAPIFallbackTests(APITestCase):
    """
    When Redis has no raw profile AND the user has a strava_id,
    the serializer should fall back to the Strava API to re-fetch the profile.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='fallback_user',
            password='password123',
            strava_id='77777',
            strava_access_token='tok_abc',
            strava_refresh_token='ref_abc',
        )

    def tearDown(self):
        cache.clear()

    @patch('apps.accounts.serializers.requests.get')
    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    def test_fallback_fetches_from_strava_api(self, mock_refresh, mock_get):
        """When Redis is empty, serializer re-fetches from Strava API."""
        mock_refresh.return_value = 'fresh_token'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 77777,
            "profile": "https://cdn.strava.com/fetched.jpg",
        }
        mock_get.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile_pic_url'], "https://cdn.strava.com/fetched.jpg")

        # Verify the profile was persisted in Redis for future requests.
        raw = get_strava_raw_profile(self.user.pk)
        self.assertEqual(raw['profile'], "https://cdn.strava.com/fetched.jpg")

    @patch('apps.accounts.serializers.requests.get')
    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    def test_fallback_api_failure_returns_none(self, mock_refresh, mock_get):
        """When the Strava API call fails, profile_pic_url returns None."""
        mock_refresh.return_value = 'fresh_token'
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['profile_pic_url'])

    @patch('apps.accounts.serializers.requests.get')
    @patch('apps.activities.services.StravaSyncService.refresh_user_token')
    def test_no_fallback_when_no_strava_id(self, mock_refresh, mock_get):
        """Users without strava_id should NOT trigger the API fallback."""
        user_no_strava = User.objects.create_user(
            username='no_strava', password='password123',
        )
        self.client.force_authenticate(user=user_no_strava)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['profile_pic_url'])
        mock_refresh.assert_not_called()
        mock_get.assert_not_called()

# ---------------------------------------------------------------------------
# UserViewSet permissions matrix tests
# ---------------------------------------------------------------------------
from apps.squads.models import Squad, SquadMembership

@override_settings(CACHES=LOCMEM_CACHE)
class UserViewSetPermissionsMatrixTests(APITestCase):
    def setUp(self):
        self.coach1 = User.objects.create_user(username='coach1', role=User.Role.COACH)
        self.athlete1 = User.objects.create_user(username='athlete1', role=User.Role.ATHLETE)
        self.athlete2 = User.objects.create_user(username='athlete2', role=User.Role.ATHLETE)
        
        self.squad1 = Squad.objects.create(name='Squad 1', coach=self.coach1)
        SquadMembership.objects.create(squad=self.squad1, athlete=self.athlete1)
        SquadMembership.objects.create(squad=self.squad1, athlete=self.athlete2)

        self.coach2 = User.objects.create_user(username='coach2', role=User.Role.COACH)
        self.athlete3 = User.objects.create_user(username='athlete3', role=User.Role.ATHLETE)
        
        self.squad2 = Squad.objects.create(name='Squad 2', coach=self.coach2)
        SquadMembership.objects.create(squad=self.squad2, athlete=self.athlete3)

        self.unrelated = User.objects.create_user(username='unrelated', role=User.Role.NONE)

    def test_user_list_and_retrieve_permissions(self):
        # Format: (requesting_user, expected_visible_users)
        matrix = [
            (self.coach1, {self.coach1, self.athlete1, self.athlete2}),
            (self.athlete1, {self.athlete1, self.athlete2, self.coach1}),
            (self.coach2, {self.coach2, self.athlete3}),
            (self.athlete3, {self.athlete3, self.coach2}),
            (self.unrelated, {self.unrelated}),
        ]
        
        list_url = reverse('user-list')
        
        for user, expected_visible in matrix:
            self.client.force_authenticate(user=user)
            
            # Test List
            response = self.client.get(list_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Depending on pagination, response.data might be a dict with 'results' or a list.
            # Assuming no pagination by default or if there is, we check results.
            data = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
            visible_ids = {u['id'] for u in data}
            expected_ids = {u.id for u in expected_visible}
            self.assertEqual(visible_ids, expected_ids, f"List failed for {user.username}")
            
            # Test Retrieve
            all_users = [self.coach1, self.athlete1, self.athlete2, self.coach2, self.athlete3, self.unrelated]
            for target_user in all_users:
                detail_url = reverse('user-detail', kwargs={'pk': target_user.pk})
                response = self.client.get(detail_url)
                if target_user in expected_visible:
                    self.assertEqual(response.status_code, status.HTTP_200_OK, f"Retrieve failed for {user.username} accessing {target_user.username}")
                else:
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, f"Retrieve should fail for {user.username} accessing {target_user.username}")

