from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import User
import datetime

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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
