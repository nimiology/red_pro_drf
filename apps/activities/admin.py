from django.contrib import admin
from .models import Activity

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['name', 'athlete', 'type', 'distance', 'start_date']
    list_filter = ['type', 'start_date']
    search_fields = ['name', 'athlete__username']
