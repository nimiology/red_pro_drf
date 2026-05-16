from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Mission(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        COMPLETED = 'COMPLETED', _('Completed')
        MISSED = 'MISSED', _('Missed')

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_missions'
    )
    
    # Can be assigned to a single athlete or an entire squad
    athlete = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='assigned_missions',
        null=True, 
        blank=True
    )
    squad = models.ForeignKey(
        'squads.Squad', 
        on_delete=models.CASCADE, 
        related_name='squad_missions',
        null=True, 
        blank=True
    )

    satisfying_activity = models.ForeignKey(
        'activities.Activity',
        on_delete=models.SET_NULL,
        related_name='satisfied_missions',
        null=True,
        blank=True,
        help_text="The activity that successfully completed this mission"
    )

    title = models.CharField(max_length=255)
    
    # Mission Parameters
    pace = models.CharField(max_length=50, help_text="Target pace (e.g. 3:45 /KM)")
    distance = models.FloatField(help_text="Target distance in KM")
    rest_interval = models.CharField(max_length=50, blank=True, help_text="e.g. 2:00 MIN")
    hr_zone = models.PositiveSmallIntegerField(
        choices=[(i, f'Zone {i}') for i in range(1, 6)],
        help_text="Heart Rate Zone Command (1-5)"
    )
    
    # Scheduling
    scheduled_date = models.DateTimeField()
    
    status = models.CharField(
        max_length=20, 
        choices=Status.choices,
        default=Status.PENDING
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.scheduled_date}"
