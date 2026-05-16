from django.contrib import admin
from .models import Mission

@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ['title', 'coach', 'athlete', 'squad', 'scheduled_date', 'status']
    list_filter = ['status', 'scheduled_date', 'hr_zone']
    search_fields = ['title', 'coach__username', 'athlete__username', 'squad__name']
