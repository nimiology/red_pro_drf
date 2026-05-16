import time
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import User
from .models import Squad, SquadMembership

class SquadSmashMatrixTests(APITestCase):
    """
    Matrix Smash Tests for Squad Management.
    Matrix: Role (COACH, ATHLETE, NONE) x Action (List, Retrieve, Create, Update, Delete)
    """
    def setUp(self):
        self.coach = User.objects.create_user(username='coach_master', password='password', role='COACH')
        self.athlete = User.objects.create_user(username='athlete_1', password='password', role='ATHLETE')
        self.stranger = User.objects.create_user(username='stranger', password='password', role='NONE')
        
        self.list_url = reverse('squad-list')

    def test_permission_matrix(self):
        """
        Comprehensive Matrix Smash for Squad Permissions.
        """
        # We define a helper to ensure a fresh squad exists for each detail test
        def get_fresh_squad():
            squad = Squad.objects.create(name="Matrix Squad", coach=self.coach)
            squad.athletes.add(self.athlete)
            return squad, reverse('squad-detail', kwargs={'pk': squad.pk})

        matrix = [
            # Coach (Owner) permissions
            {'user': self.coach, 'method': 'get', 'url_type': 'list', 'expected': status.HTTP_200_OK},
            {'user': self.coach, 'method': 'post', 'url_type': 'list', 'expected': status.HTTP_201_CREATED, 'data': {'name': 'New'}},
            {'user': self.coach, 'method': 'get', 'url_type': 'detail', 'expected': status.HTTP_200_OK},
            {'user': self.coach, 'method': 'patch', 'url_type': 'detail', 'expected': status.HTTP_200_OK, 'data': {'name': 'Updated'}},
            {'user': self.coach, 'method': 'delete', 'url_type': 'detail', 'expected': status.HTTP_204_NO_CONTENT},

            # Athlete (Member) permissions
            {'user': self.athlete, 'method': 'get', 'url_type': 'list', 'expected': status.HTTP_200_OK},
            {'user': self.athlete, 'method': 'post', 'url_type': 'list', 'expected': status.HTTP_403_FORBIDDEN, 'data': {'name': 'No'}},
            {'user': self.athlete, 'method': 'get', 'url_type': 'detail', 'expected': status.HTTP_200_OK},
            {'user': self.athlete, 'method': 'patch', 'url_type': 'detail', 'expected': status.HTTP_403_FORBIDDEN, 'data': {'name': 'No'}},
            {'user': self.athlete, 'method': 'delete', 'url_type': 'detail', 'expected': status.HTTP_403_FORBIDDEN},

            # Stranger (None) permissions
            {'user': self.stranger, 'method': 'get', 'url_type': 'list', 'expected': status.HTTP_200_OK},
            {'user': self.stranger, 'method': 'post', 'url_type': 'list', 'expected': status.HTTP_403_FORBIDDEN, 'data': {'name': 'No'}},
            # Should be 404 because stranger is not in the queryset
            {'user': self.stranger, 'method': 'get', 'url_type': 'detail', 'expected': status.HTTP_404_NOT_FOUND},
            {'user': self.stranger, 'method': 'patch', 'url_type': 'detail', 'expected': status.HTTP_403_FORBIDDEN, 'data': {'name': 'No'}},
            {'user': self.stranger, 'method': 'delete', 'url_type': 'detail', 'expected': status.HTTP_403_FORBIDDEN},
        ]

        for case in matrix:
            # Recreate squad if it's a detail test to avoid 404 from previous deletions
            if case['url_type'] == 'detail':
                squad, url = get_fresh_squad()
            else:
                url = self.list_url

            self.client.force_authenticate(user=case['user'])
            method = getattr(self.client, case['method'])
            data = case.get('data', {})
            
            response = method(url, data)
            
            self.assertEqual(
                response.status_code, 
                case['expected'], 
                f"Failed: {case['user'].username} | {case['method'].upper()} {url} | Expected {case['expected']} but got {response.status_code}"
            )

    def test_data_isolation_matrix(self):
        other_coach = User.objects.create_user(username='other_coach', password='password', role='COACH')
        squad = Squad.objects.create(name="Master Squad", coach=self.coach)
        detail_url = reverse('squad-detail', kwargs={'pk': squad.pk})
        
        self.client.force_authenticate(user=other_coach)
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.data), 0)

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class SquadAlgoTests(APITestCase):
    """
    Algo Tests: Verifying the logic of membership synchronization and join date preservation.
    """
    def setUp(self):
        self.coach = User.objects.create_user(username='coach_algo', password='password', role='COACH')
        self.athlete1 = User.objects.create_user(username='a1', password='password', role='ATHLETE')
        self.athlete2 = User.objects.create_user(username='a2', password='password', role='ATHLETE')
        self.athlete3 = User.objects.create_user(username='a3', password='password', role='ATHLETE')
        
        self.client.force_authenticate(user=self.coach)
        self.squad = Squad.objects.create(name="Algo Squad", coach=self.coach)
        self.squad.athletes.add(self.athlete1, self.athlete2)
        
        self.detail_url = reverse('squad-detail', kwargs={'pk': self.squad.pk})

    def test_membership_sync_algorithm(self):
        # 1. Capture initial join dates
        initial_m1 = SquadMembership.objects.get(squad=self.squad, athlete=self.athlete1)
        initial_join_date = initial_m1.joined_at
        
        # Wait a moment to ensure timestamp difference
        time.sleep(0.1)
        
        # 2. Update squad: Remove athlete2, Keep athlete1, Add athlete3
        data = {
            "name": "Updated Squad",
            "athletes": [self.athlete1.id, self.athlete3.id]
        }
        response = self.client.patch(self.detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Verify Algo Results
        self.squad.refresh_from_db()
        athlete_ids = list(self.squad.athletes.values_list('id', flat=True))
        self.assertIn(self.athlete1.id, athlete_ids)
        self.assertIn(self.athlete3.id, athlete_ids)
        self.assertNotIn(self.athlete2.id, athlete_ids)
        
        # 4. CRITICAL ALGO CHECK: Is the join date for athlete1 preserved?
        updated_m1 = SquadMembership.objects.get(squad=self.squad, athlete=self.athlete1)
        self.assertEqual(initial_join_date, updated_m1.joined_at, "ALGO ERROR: Join date was not preserved for existing member!")
        
        # 5. Verify athlete3 has a new join date
        m3 = SquadMembership.objects.get(squad=self.squad, athlete=self.athlete3)
        self.assertGreater(m3.joined_at, initial_join_date)
