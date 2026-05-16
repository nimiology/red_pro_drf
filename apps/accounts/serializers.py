from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    age = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 
            'onboarding_step', 'is_onboarding_finished',
            'full_name', 'birth_date', 'age', 'weight',
            'strava_id', 'strava_access_token', 'strava_refresh_token',
            'strava_token_expires_at', 'strava_raw_profile'
        ]
        read_only_fields = [
            'id', 'username', 'strava_id', 'strava_access_token', 
            'strava_refresh_token', 'strava_token_expires_at', 'strava_raw_profile'
        ]

    def get_age(self, obj):
        if obj.birth_date:
            from datetime import date
            today = date.today()
            return today.year - obj.birth_date.year - ((today.month, today.day) < (obj.birth_date.month, obj.birth_date.day))
        return None
