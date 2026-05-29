from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Onboarding', {'fields': ('role', 'onboarding_step', 'is_onboarding_finished', 'full_name', 'birth_date', 'weight')}),
        ('Strava', {'fields': ('strava_id', 'strava_access_token', 'strava_refresh_token', 'strava_token_expires_at')}),
    )
    list_display = ['username', 'email', 'role', 'onboarding_step', 'is_onboarding_finished']
