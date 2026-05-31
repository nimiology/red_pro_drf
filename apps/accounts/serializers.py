from rest_framework import serializers
import requests

from apps.activities.services import StravaSyncService
from .models import User


class UserSerializer(serializers.ModelSerializer):
    age = serializers.SerializerMethodField()
    profile_pic_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role',
            'onboarding_step', 'is_onboarding_finished',
            'full_name', 'birth_date', 'age', 'weight',
            'strava_id', 'strava_access_token', 'strava_refresh_token',
            'strava_token_expires_at',
            'profile_pic_url',
            'strava_raw_profile',
        ]
        read_only_fields = [
            'id', 'username', 'strava_id', 'strava_access_token',
            'strava_refresh_token', 'strava_token_expires_at',
            'profile_pic_url',
            'strava_raw_profile',
        ]

    def get_age(self, obj):
        if obj.birth_date:
            from datetime import date
            today = date.today()
            return today.year - obj.birth_date.year - ((today.month, today.day) < (obj.birth_date.month, obj.birth_date.day))
        return None

    def _fetch_strava_profile_from_api(self, user):
        """
        Fallback: re-fetch the athlete profile from the Strava API
        using the stored access token, then persist in the database.
        Returns the profile dict or None.
        """
        if not user.strava_access_token:
            return None

        access_token = StravaSyncService.refresh_user_token(user)
        if not access_token:
            return None

        response = requests.get(
            "https://www.strava.com/api/v3/athlete",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            profile_data = response.json()
            user.strava_raw_profile = profile_data
            user.save(update_fields=['strava_raw_profile'])
            return profile_data
        return None

    def get_profile_pic_url(self, obj):
        raw = obj.strava_raw_profile
        # Fallback: if DB is empty, re-fetch from Strava API
        if raw is None and obj.strava_id:
            raw = self._fetch_strava_profile_from_api(obj)
        raw = raw or {}
        url = raw.get("profile") or raw.get("profile_medium") or ""
        return url or None

