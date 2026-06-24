from rest_framework import serializers


class LeaderboardEntrySerializer(serializers.Serializer):
    """Serializes a single leaderboard entry (computed, not from a model)."""
    rank = serializers.IntegerField()
    athlete_id = serializers.IntegerField()
    athlete_username = serializers.CharField()
    athlete_full_name = serializers.CharField()
    total_distance_km = serializers.FloatField()
    total_moving_time_hours = serializers.FloatField()
    average_pace = serializers.FloatField()
    total_elevation_m = serializers.FloatField()
    completed_missions = serializers.IntegerField()
    score = serializers.FloatField()
