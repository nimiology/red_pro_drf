import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.accounts.models import User
from apps.activities.services import StravaSyncService

users = User.objects.filter(strava_id__isnull=False)
for user in users:
    print(f"Testing sync for user {user.username} (Strava ID: {user.strava_id})")
    access_token = StravaSyncService.refresh_user_token(user)
    if not access_token:
        print("  -> Failed to refresh token")
    else:
        print("  -> Token refreshed successfully")
        success = StravaSyncService.sync_recent_activities(user)
        print(f"  -> Sync result: {success}")
