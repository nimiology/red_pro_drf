from django.contrib.auth import get_user_model
from django.db import models

class Activity(models.Model):
    athlete = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='activities')
    
    # Core Identification
    strava_id = models.BigIntegerField(unique=True, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)
    upload_id = models.BigIntegerField(null=True, blank=True)
    
    # Basic Info
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=50)
    sport_type = models.CharField(max_length=50)
    
    # Metrics
    distance = models.FloatField() # Meters
    moving_time = models.PositiveIntegerField() # Seconds
    elapsed_time = models.PositiveIntegerField() # Seconds
    total_elevation_gain = models.FloatField()
    elev_high = models.FloatField(null=True, blank=True)
    elev_low = models.FloatField(null=True, blank=True)
    
    # Performance
    average_speed = models.FloatField()
    max_speed = models.FloatField()
    average_cadence = models.FloatField(null=True, blank=True)
    average_temp = models.IntegerField(null=True, blank=True)
    average_watts = models.FloatField(null=True, blank=True)
    weighted_average_watts = models.FloatField(null=True, blank=True)
    max_watts = models.FloatField(null=True, blank=True)
    kilojoules = models.FloatField(null=True, blank=True)
    device_watts = models.BooleanField(default=False)
    has_heartrate = models.BooleanField(default=False)
    average_heartrate = models.FloatField(null=True, blank=True)
    max_heartrate = models.FloatField(null=True, blank=True)
    suffer_score = models.IntegerField(null=True, blank=True)
    calories = models.FloatField(null=True, blank=True)
    
    # Date & Time
    start_date = models.DateTimeField()

    # Location
    start_latlng = models.JSONField(null=True, blank=True)
    end_latlng = models.JSONField(null=True, blank=True)
    
    # Map & Route
    map_polyline = models.TextField(null=True, blank=True)
    summary_polyline = models.TextField(null=True, blank=True)
    
    # Metadata
    achievement_count = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Activities"
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} - {self.athlete.username}"
