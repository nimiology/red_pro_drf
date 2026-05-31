from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    class Role(models.TextChoices):
        COACH = 'COACH', _('Coach')
        ATHLETE = 'ATHLETE', _('Athlete')
        NONE = 'NONE', _('None')


    # Onboarding Variables
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.NONE)
    onboarding_step = models.PositiveSmallIntegerField(default=1)
    is_onboarding_finished = models.BooleanField(default=False)
    
    # User Data from Onboarding
    full_name = models.CharField(max_length=255, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Strava Integration
    strava_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    strava_access_token = models.TextField(null=True, blank=True)
    strava_refresh_token = models.TextField(null=True, blank=True)
    strava_token_expires_at = models.DateTimeField(null=True, blank=True)
    strava_raw_profile = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.username
