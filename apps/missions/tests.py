from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import User
from apps.squads.models import Squad
from .models import Mission
from apps.activities.models import Activity

class MissionMatrixSmashTests(APITestCase):
    """
    Comprehensive Matrix Smash Tests for Mission API.
    Tests all methods against all roles and validates data isolation.
    """
    def setUp(self):
        # Users
        self.coach = User.objects.create_user(username='coach', password='password', role='COACH')
        self.other_coach = User.objects.create_user(username='other_coach', password='password', role='COACH')
        self.athlete = User.objects.create_user(username='athlete', password='password', role='ATHLETE')
        self.stranger = User.objects.create_user(username='stranger', password='password', role='ATHLETE')
        
        # Squad
        self.squad = Squad.objects.create(name="Alpha Squad", coach=self.coach)
        self.squad.athletes.add(self.athlete)
        
        # Missions
        self.mission_direct = Mission.objects.create(
            coach=self.coach, athlete=self.athlete, title="Direct Mission", 
            pace="4:00", distance=5, hr_zone=3, scheduled_date="2024-05-20T08:00:00Z"
        )
        self.mission_squad = Mission.objects.create(
            coach=self.coach, squad=self.squad, title="Squad Mission", 
            pace="4:30", distance=10, hr_zone=2, scheduled_date="2024-05-21T08:00:00Z"
        )
        self.mission_other = Mission.objects.create(
            coach=self.other_coach, title="Other Coach Mission", 
            pace="5:00", distance=15, hr_zone=1, scheduled_date="2024-05-22T08:00:00Z"
        )

        self.list_url = reverse('mission-list')
        self.detail_url = lambda pk: reverse('mission-detail', kwargs={'pk': pk})

    def test_get_matrix(self):
        matrix = [
            (self.coach, self.mission_direct, 200),
            (self.athlete, self.mission_direct, 200),
            (self.athlete, self.mission_squad, 200),
            (self.stranger, self.mission_direct, 404),
            (self.other_coach, self.mission_direct, 404),
        ]
        for user, mission, status_code in matrix:
            self.client.force_authenticate(user=user)
            resp = self.client.get(self.detail_url(mission.pk))
            self.assertEqual(resp.status_code, status_code, f"User {user.username} GET {mission.title} failed")

    def test_patch_matrix(self):
        matrix = [
            (self.coach, self.mission_direct, 200),
            (self.athlete, self.mission_direct, 403),
            (self.stranger, self.mission_direct, 403), # 403 due to IsCoachOrReadOnly
        ]
        for user, mission, status_code in matrix:
            self.client.force_authenticate(user=user)
            resp = self.client.patch(self.detail_url(mission.pk), {"title": "Edited"})
            self.assertEqual(resp.status_code, status_code, f"User {user.username} PATCH {mission.title} failed")

    def test_delete_matrix(self):
        matrix = [
            (self.athlete, self.mission_direct, 403),
            (self.stranger, self.mission_direct, 403), # 403 due to IsCoachOrReadOnly
            (self.coach, self.mission_direct, 204),
        ]
        for user, mission, status_code in matrix:
            self.client.force_authenticate(user=user)
            resp = self.client.delete(self.detail_url(mission.pk))
            self.assertEqual(resp.status_code, status_code, f"User {user.username} DELETE {mission.title} failed")

    def test_create_permission_matrix(self):
        users = [
            (self.coach, 201),
            (self.athlete, 403),
            (self.stranger, 403),
        ]
        
        for user, expected_status in users:
            self.client.force_authenticate(user=user)
            data = {
                "title": f"New Mission by {user.username}",
                "pace": "4:00",
                "distance": 5.0,
                "hr_zone": 3,
                "scheduled_date": "2024-05-20T08:00:00Z"
            }
            resp = self.client.post(self.list_url, data)
            self.assertEqual(resp.status_code, expected_status)
            
            if expected_status == 201:
                # Test perform_create: coach should be set to the user
                self.assertEqual(resp.data['coach'], user.id)

    def test_queryset_isolation_and_squad_visibility(self):
        """
        Tests that get_queryset correctly filters missions.
        """
        # 1. Coach should see only their 2 missions (direct and squad)
        self.client.force_authenticate(user=self.coach)
        resp = self.client.get(self.list_url)
        self.assertEqual(len(resp.data), 2)
        
        # 2. Athlete should see 2 missions (one direct, one via squad)
        self.client.force_authenticate(user=self.athlete)
        resp = self.client.get(self.list_url)
        self.assertEqual(len(resp.data), 2)
        
        # 3. Stranger should see 0 missions
        self.client.force_authenticate(user=self.stranger)
        resp = self.client.get(self.list_url)
        self.assertEqual(len(resp.data), 0)
        
        # 4. Other coach should see 1 mission
        self.client.force_authenticate(user=self.other_coach)
        resp = self.client.get(self.list_url)
        self.assertEqual(len(resp.data), 1)

    def test_perform_create_coach_assignment(self):
        """
        Verify that the coach is automatically set to the current user on create.
        """
        self.client.force_authenticate(user=self.coach)
        data = {
            "title": "Auto Coach Test",
            "pace": "4:00",
            "distance": 5.0,
            "hr_zone": 3,
            "scheduled_date": "2024-05-20T08:00:00Z"
        }
        # Intentionally don't send coach ID
        resp = self.client.post(self.list_url, data)
        self.assertEqual(resp.status_code, 201)
        mission = Mission.objects.get(id=resp.data['id'])
        self.assertEqual(mission.coach, self.coach)

    def test_summary_endpoint(self):
        """
        Test the summary endpoint returns data for the user's missions.
        """
        self.client.force_authenticate(user=self.coach)
        url = reverse('mission-summary')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # 2 missions, both should be PENDING by default
        self.assertEqual(resp.data.get('PENDING', 0), 2)
        self.assertEqual(resp.data.get('total', 0), 2)

    def test_satisfying_activity_validation(self):
        """
        Test that an activity can only satisfy a mission if it belongs to the assigned athlete.
        """
        
        # Create an activity for the assigned athlete
        activity_athlete = Activity.objects.create(
            athlete=self.athlete, strava_id=1, name="A", distance=5, moving_time=1,
            elapsed_time=1, total_elevation_gain=1, type="Run", sport_type="Run",
            average_speed=1, max_speed=1, start_date="2024-05-20T08:00:00Z"
        )
        
        # Create an activity for a stranger
        activity_stranger = Activity.objects.create(
            athlete=self.stranger, strava_id=2, name="B", distance=5, moving_time=1,
            elapsed_time=1, total_elevation_gain=1, type="Run", sport_type="Run",
            average_speed=1, max_speed=1, start_date="2024-05-20T08:00:00Z"
        )
        
        self.client.force_authenticate(user=self.coach)
        
        # Valid: assigning athlete's activity to their mission
        resp = self.client.patch(self.detail_url(self.mission_direct.pk), {
            "satisfying_activity": activity_athlete.pk
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        # Invalid: assigning stranger's activity to athlete's mission
        resp = self.client.patch(self.detail_url(self.mission_direct.pk), {
            "satisfying_activity": activity_stranger.pk
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('satisfying_activity', resp.data)
