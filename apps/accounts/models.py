from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator

class CustomUsernameValidator(RegexValidator):
    regex = r'^[^\s]+$'
    message = _('Enter a valid username. This value may not contain spaces.')

class User(AbstractUser):
    username_validator = CustomUsernameValidator()

    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. No spaces allowed.'),
        validators=[username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )

    class Role(models.TextChoices):
        COACH = 'COACH', _('Coach')
        ATHLETE = 'ATHLETE', _('Athlete')
        NONE = 'NONE', _('None')

    def save(self, *args, **kwargs):
        if self.username:
            self.username = self.username.lower()
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

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
