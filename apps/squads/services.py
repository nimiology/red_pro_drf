from django.db.models import Sum, Count, Q, Value, FloatField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta

from apps.activities.models import Activity
from apps.missions.models import Mission


class LeaderboardService:
    """
    Computes a ranked leaderboard for athletes in a squad.

    Scoring formula (per athlete, within the time window):
        score = (distance_km × 10)
              + (moving_time_hours × 5)
              + (elevation_m × 0.02)
              + (completed_missions × 15)
    """

    PERIOD_DAYS = {
        'weekly': 7,
        'monthly': 30,
        'all_time': None,
    }

    VALID_PERIODS = set(PERIOD_DAYS.keys())

    @staticmethod
    def _get_date_threshold(period):
        """Returns the earliest datetime for the given period, or None for all_time."""
        days = LeaderboardService.PERIOD_DAYS.get(period)
        if days is None:
            return None
        return timezone.now() - timedelta(days=days)

    @classmethod
    def get_squad_leaderboard(cls, squad, period='weekly', sort_by='distance'):
        """
        Returns a list of dicts, one per athlete, sorted by distance or pace.

        Each dict contains:
            rank, athlete_id, athlete_username, athlete_full_name,
            total_distance_km, total_moving_time_hours, average_pace, total_elevation_m,
            completed_missions, score
        """
        if period not in cls.VALID_PERIODS:
            period = 'weekly'

        date_threshold = cls._get_date_threshold(period)

        athletes = squad.athletes.all()

        leaderboard = []
        for athlete in athletes:
            # --- Activity aggregation ---
            activity_qs = Activity.objects.filter(athlete=athlete)
            if date_threshold:
                activity_qs = activity_qs.filter(start_date__gte=date_threshold)

            agg = activity_qs.aggregate(
                total_distance=Coalesce(Sum('distance'), Value(0.0), output_field=FloatField()),
                total_moving_time=Coalesce(Sum('moving_time'), Value(0), output_field=FloatField()),
                total_elevation=Coalesce(Sum('total_elevation_gain'), Value(0.0), output_field=FloatField()),
            )

            total_distance_km = agg['total_distance'] / 1000.0  # meters → km
            total_moving_time_hours = agg['total_moving_time'] / 3600.0  # seconds → hours
            total_elevation_m = agg['total_elevation']

            average_pace = 0.0
            if total_distance_km > 0:
                average_pace = (total_moving_time_hours * 60) / total_distance_km


            # --- Mission completion count ---
            mission_filter = Q(
                Q(athlete=athlete) | Q(squad=squad, squad__athletes=athlete),
                status=Mission.Status.COMPLETED,
            )
            if date_threshold:
                mission_filter &= Q(scheduled_date__gte=date_threshold)

            completed_missions = Mission.objects.filter(mission_filter).distinct().count()

            # --- Score ---
            score = (
                (total_distance_km * 10)
                + (total_moving_time_hours * 5)
                + (total_elevation_m * 0.02)
                + (completed_missions * 15)
            )

            leaderboard.append({
                'athlete_id': athlete.id,
                'athlete_username': athlete.username,
                'athlete_full_name': athlete.full_name or athlete.username,
                'total_distance_km': round(total_distance_km, 2),
                'total_moving_time_hours': round(total_moving_time_hours, 2),
                'average_pace': round(average_pace, 2),
                'total_elevation_m': round(total_elevation_m, 2),
                'completed_missions': completed_missions,
                'score': round(score, 2),
            })

        # Sort based on sort_by
        if sort_by == 'pace':
            # For pace, lower is better (faster), but 0 means no distance so it should be last
            leaderboard.sort(key=lambda x: x['average_pace'] if x['average_pace'] > 0 else float('inf'))
        else:
            # Default sort by distance (descending)
            leaderboard.sort(key=lambda x: x['total_distance_km'], reverse=True)


        # Assign ranks
        for idx, entry in enumerate(leaderboard, start=1):
            entry['rank'] = idx

        return leaderboard
