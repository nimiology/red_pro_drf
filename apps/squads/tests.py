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


class LeaderboardSmashMatrixTests(APITestCase):
    """
    Matrix Smash Tests for Leaderboard.
    Matrix: Role (COACH, ATHLETE, STRANGER) x Period (weekly, monthly, all_time)
    All cases use reverse('squad-leaderboard', kwargs={'pk': ...}).
    """
    def setUp(self):
        self.coach = User.objects.create_user(username='lb_coach', password='password', role='COACH')
        self.athlete = User.objects.create_user(username='lb_athlete', password='password', role='ATHLETE')
        self.stranger = User.objects.create_user(username='lb_stranger', password='password', role='NONE')

        self.squad = Squad.objects.create(name='Leaderboard Squad', coach=self.coach)
        SquadMembership.objects.create(squad=self.squad, athlete=self.athlete)

    def test_permission_and_period_matrix(self):
        url = reverse('squad-leaderboard', kwargs={'pk': self.squad.pk})

        matrix = [
            # Coach (owner) — should see leaderboard for all periods
            {'user': self.coach, 'period': 'weekly', 'expected': status.HTTP_200_OK},
            {'user': self.coach, 'period': 'monthly', 'expected': status.HTTP_200_OK},
            {'user': self.coach, 'period': 'all_time', 'expected': status.HTTP_200_OK},

            # Athlete (member) — read-only access to leaderboard
            {'user': self.athlete, 'period': 'weekly', 'expected': status.HTTP_200_OK},
            {'user': self.athlete, 'period': 'monthly', 'expected': status.HTTP_200_OK},
            {'user': self.athlete, 'period': 'all_time', 'expected': status.HTTP_200_OK},

            # Stranger — gets 404 because squad is not in their queryset
            {'user': self.stranger, 'period': 'weekly', 'expected': status.HTTP_404_NOT_FOUND},
            {'user': self.stranger, 'period': 'monthly', 'expected': status.HTTP_404_NOT_FOUND},
            {'user': self.stranger, 'period': 'all_time', 'expected': status.HTTP_404_NOT_FOUND},
        ]

        for case in matrix:
            self.client.force_authenticate(user=case['user'])
            response = self.client.get(url, {'period': case['period']})
            self.assertEqual(
                response.status_code,
                case['expected'],
                f"Failed: {case['user'].username} | period={case['period']} | "
                f"Expected {case['expected']} but got {response.status_code}"
            )

    def test_leaderboard_url_resolves(self):
        """Verify the reverse URL for leaderboard resolves correctly."""
        url = reverse('squad-leaderboard', kwargs={'pk': self.squad.pk})
        self.assertIn(f'/squads/{self.squad.pk}/leaderboard/', url)

    def test_invalid_period_falls_back_to_weekly(self):
        """Invalid period param should silently fall back to weekly (no error)."""
        self.client.force_authenticate(user=self.coach)
        url = reverse('squad-leaderboard', kwargs={'pk': self.squad.pk})
        response = self.client.get(url, {'period': 'invalid_junk'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_no_period_param_defaults_to_weekly(self):
        """Omitting period should default to weekly."""
        self.client.force_authenticate(user=self.coach)
        url = reverse('squad-leaderboard', kwargs={'pk': self.squad.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class LeaderboardAlgoTests(APITestCase):
    """
    Algo Tests: Verifying the scoring, ranking, and time-window logic of the leaderboard.
    """
    def setUp(self):
        from django.utils import timezone
        from apps.activities.models import Activity
        from apps.missions.models import Mission

        self.coach = User.objects.create_user(username='algo_coach', password='password', role='COACH')
        self.a1 = User.objects.create_user(username='algo_a1', password='password', role='ATHLETE', full_name='Alpha Runner')
        self.a2 = User.objects.create_user(username='algo_a2', password='password', role='ATHLETE', full_name='Beta Runner')
        self.a3 = User.objects.create_user(username='algo_a3', password='password', role='ATHLETE', full_name='Gamma Runner')

        self.squad = Squad.objects.create(name='Algo Squad', coach=self.coach)
        SquadMembership.objects.create(squad=self.squad, athlete=self.a1)
        SquadMembership.objects.create(squad=self.squad, athlete=self.a2)
        SquadMembership.objects.create(squad=self.squad, athlete=self.a3)

        self.now = timezone.now()

        # --- Activities for a1 (recent — within weekly window) ---
        Activity.objects.create(
            athlete=self.a1, name='Morning Run', type='Run', sport_type='Run',
            distance=10000.0, moving_time=3600, elapsed_time=3700,
            total_elevation_gain=100.0, average_speed=2.78, max_speed=3.5,
            start_date=self.now - timezone.timedelta(days=2),
        )

        # --- Activities for a2 (recent — within weekly window, higher metrics) ---
        Activity.objects.create(
            athlete=self.a2, name='Long Run', type='Run', sport_type='Run',
            distance=20000.0, moving_time=7200, elapsed_time=7400,
            total_elevation_gain=300.0, average_speed=2.78, max_speed=3.5,
            start_date=self.now - timezone.timedelta(days=1),
        )

        # --- Activities for a3 (OLD — outside weekly window but inside monthly) ---
        Activity.objects.create(
            athlete=self.a3, name='Old Run', type='Run', sport_type='Run',
            distance=50000.0, moving_time=18000, elapsed_time=18500,
            total_elevation_gain=500.0, average_speed=2.78, max_speed=3.5,
            start_date=self.now - timezone.timedelta(days=20),
        )

        # --- Completed mission for a1 (recent) ---
        Mission.objects.create(
            coach=self.coach, athlete=self.a1,
            title='Tempo Run', pace='4:00 /KM', distance=5.0,
            hr_zone=3, scheduled_date=self.now - timezone.timedelta(days=1),
            status=Mission.Status.COMPLETED,
        )

        self.client.force_authenticate(user=self.coach)
        self.lb_url = reverse('squad-leaderboard', kwargs={'pk': self.squad.pk})

    def test_weekly_ranking_order(self):
        """a2 should rank #1 (more distance/time), a1 #2 (has mission bonus), a3 #3 (old activity excluded)."""
        response = self.client.get(self.lb_url, {'period': 'weekly'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['athlete_username'], 'algo_a2')
        self.assertEqual(data[0]['rank'], 1)
        self.assertEqual(data[1]['athlete_username'], 'algo_a1')
        self.assertEqual(data[1]['rank'], 2)
        self.assertEqual(data[2]['athlete_username'], 'algo_a3')
        self.assertEqual(data[2]['rank'], 3)

    def test_weekly_excludes_old_activities(self):
        """a3's old activity should not contribute to weekly score."""
        response = self.client.get(self.lb_url, {'period': 'weekly'})
        data = response.data

        a3_entry = next(e for e in data if e['athlete_username'] == 'algo_a3')
        self.assertEqual(a3_entry['total_distance_km'], 0.0)
        self.assertEqual(a3_entry['score'], 0.0)

    def test_monthly_includes_old_activities(self):
        """a3's 20-day-old activity should appear in monthly leaderboard."""
        response = self.client.get(self.lb_url, {'period': 'monthly'})
        data = response.data

        a3_entry = next(e for e in data if e['athlete_username'] == 'algo_a3')
        self.assertEqual(a3_entry['total_distance_km'], 50.0)
        self.assertGreater(a3_entry['score'], 0)

    def test_all_time_includes_everything(self):
        """all_time should include all activities regardless of date."""
        response = self.client.get(self.lb_url, {'period': 'all_time'})
        data = response.data

        for entry in data:
            if entry['athlete_username'] == 'algo_a3':
                self.assertEqual(entry['total_distance_km'], 50.0)

    def test_scoring_formula_accuracy(self):
        """
        Verify exact score for a1 (weekly):
        distance = 10000m = 10km → 10 * 10 = 100
        moving_time = 3600s = 1hr → 1 * 5 = 5
        elevation = 100m → 100 * 0.02 = 2
        missions = 1 → 1 * 15 = 15
        total = 122
        """
        response = self.client.get(self.lb_url, {'period': 'weekly'})
        a1_entry = next(e for e in response.data if e['athlete_username'] == 'algo_a1')
        self.assertEqual(a1_entry['score'], 122.0)
        self.assertEqual(a1_entry['total_distance_km'], 10.0)
        self.assertEqual(a1_entry['total_moving_time_hours'], 1.0)
        self.assertEqual(a1_entry['total_elevation_m'], 100.0)
        self.assertEqual(a1_entry['completed_missions'], 1)

    def test_empty_leaderboard_no_activities(self):
        """A squad with members but no activities should return zeroed entries."""
        from apps.activities.models import Activity
        from apps.missions.models import Mission

        empty_squad = Squad.objects.create(name='Empty Squad', coach=self.coach)
        new_athlete = User.objects.create_user(username='empty_a', password='password', role='ATHLETE')
        SquadMembership.objects.create(squad=empty_squad, athlete=new_athlete)

        url = reverse('squad-leaderboard', kwargs={'pk': empty_squad.pk})
        response = self.client.get(url, {'period': 'weekly'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['score'], 0.0)
        self.assertEqual(response.data[0]['rank'], 1)

    def test_response_fields_present(self):
        """Verify all expected fields are in each leaderboard entry."""
        response = self.client.get(self.lb_url, {'period': 'weekly'})
        expected_fields = {
            'rank', 'athlete_id', 'athlete_username', 'athlete_full_name',
            'total_distance_km', 'total_moving_time_hours', 'total_elevation_m',
            'completed_missions', 'score',
        }
        for entry in response.data:
            self.assertEqual(set(entry.keys()), expected_fields)

