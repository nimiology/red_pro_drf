from django.contrib import admin
from .models import Squad, SquadMembership

class SquadMembershipInline(admin.TabularInline):
    model = SquadMembership
    extra = 1

@admin.register(Squad)
class SquadAdmin(admin.ModelAdmin):
    list_display = ['name', 'coach']
    search_fields = ['name', 'coach__username']
    inlines = [SquadMembershipInline]

@admin.register(SquadMembership)
class SquadMembershipAdmin(admin.ModelAdmin):
    list_display = ['squad', 'athlete', 'joined_at']
    list_filter = ['joined_at', 'squad']
    search_fields = ['athlete__username', 'squad__name']
