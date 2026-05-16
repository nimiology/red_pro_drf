from rest_framework import serializers
from .models import Mission

class MissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mission
        fields = '__all__'
        read_only_fields = ['id', 'coach', 'created_at', 'updated_at']
