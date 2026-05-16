from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import User
from .models import Mission

class MissionMatrixTests(APITestCase):
    """
    Matrix Smash Tests for Mission CRUD and permissions.
    """
    def setUp(self):
        self.coach = User.objects.create_user(username='coach1', password='password', role='COACH')
        self.athlete = User.objects.create_user(username='athlete1', password='password', role='ATHLETE')
        self.other_athlete = User.objects.create_user(username='athlete2', password='password', role='ATHLETE')
        
        self.mission_url = reverse('mission-list')

    def test_coach_can_create_mission(self):
        self.client.force_authenticate(user=self.coach)
        data = {
            "title": "Threshold Run",
            "pace": "4:00 /KM",
            "distance": 10.0,
            "hr_zone": 4,
            "scheduled_date": "2024-05-20",
            "scheduled_time": "08:00:00",
            "athlete": self.athlete.id
        }
        response = self.client.post(self.mission_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Mission.objects.count(), 1)
        self.assertEqual(Mission.objects.first().coach, self.coach)

    def test_athlete_cannot_create_mission(self):
        self.client.force_authenticate(user=self.athlete)
        data = {
            "title": "Illegal Mission",
            "pace": "4:00",
            "distance": 5.0,
            "hr_zone": 3,
            "scheduled_date": "2024-05-20",
            "scheduled_time": "08:00:00"
        }
        response = self.client.post(self.mission_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_athlete_cannot_update_mission(self):
        mission = Mission.objects.create(
            coach=self.coach, athlete=self.athlete, title="M1", 
            pace="4:00", distance=5, hr_zone=3, scheduled_date="2024-01-01", scheduled_time="00:00"
        )
        self.client.force_authenticate(user=self.athlete)
        url = reverse('mission-detail', kwargs={'pk': mission.pk})
        response = self.client.patch(url, {"title": "Changed"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_athlete_cannot_delete_mission(self):
        mission = Mission.objects.create(
            coach=self.coach, athlete=self.athlete, title="M1", 
            pace="4:00", distance=5, hr_zone=3, scheduled_date="2024-01-01", scheduled_time="00:00"
        )
        self.client.force_authenticate(user=self.athlete)
        url = reverse('mission-detail', kwargs={'pk': mission.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_athlete_sees_only_own_missions(self):
        # Mission for athlete1
        Mission.objects.create(
            coach=self.coach, athlete=self.athlete, title="M1", 
            pace="4:00", distance=5, hr_zone=3, scheduled_date="2024-01-01", scheduled_time="00:00"
        )
        # Mission for athlete2
        Mission.objects.create(
            coach=self.coach, athlete=self.other_athlete, title="M2", 
            pace="4:00", distance=5, hr_zone=3, scheduled_date="2024-01-01", scheduled_time="00:00"
        )
        
        self.client.force_authenticate(user=self.athlete)
        response = self.client.get(self.mission_url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], "M1")
