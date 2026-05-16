from django.db import models
from django.conf import settings

class Squad(models.Model):
    name = models.CharField(max_length=255)
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='managed_squads'
    )
    athletes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        through='SquadMembership',
        related_name='squads',
        blank=True
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class SquadMembership(models.Model):
    squad = models.ForeignKey(Squad, on_delete=models.CASCADE)
    athlete = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('squad', 'athlete')

    def __str__(self):
        return f"{self.athlete.username} in {self.squad.name}"
